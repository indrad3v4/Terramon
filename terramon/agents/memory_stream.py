"""Memory stream for Terramon creatures — Generative Agents, adapted.

Park et al. (2023) "Generative Agents: Interactive Simulacra of Human
Behavior", memory stream, adapted to Terramon's constraints: a creature's
memory is a per-creature append-only log of observations, reflections and
plans, persisted as JSONL under data/creatures/<id>/memory.jsonl (the same
data/creatures/ layout the portrait registry uses).

Retrieval scores every entry with three signals:

    score = w_rec * recency + w_imp * importance + w_rel * relevance

  - recency:    exponential decay, half-life 24h (as in Generative Agents);
  - importance: the entry's 0-10 salience, normalized to [0, 1];
  - relevance:  cosine similarity in a 512-dim hashed feature space.

Pure stdlib. Deterministic (blake2b hashing, never Python's salted hash()).
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REFLECTION_EVERY = 5       # reflect once this many observations accumulate
REFLECTION_IMPORTANCE = 8  # reflections are stored with high salience

EMBED_DIM = 512            # matches the repo's hashed feature space width
RECENCY_HALF_LIFE_HOURS = 24.0
RECENCY_WEIGHT = 0.3
IMPORTANCE_WEIGHT = 0.3
RELEVANCE_WEIGHT = 0.4

_KINDS = frozenset({"observation", "reflection", "plan"})


def memory_path(creature_id: str) -> Path:
    """Default per-creature memory file under data/creatures/<id>/.

    The repo stores creature artifacts under data/creatures/ (see the
    data/creatures/images.json portrait registry); a creature's memory
    stream lives in its own subdirectory next to that cache.
    """
    return Path("data/creatures") / creature_id / "memory.jsonl"


@dataclass
class MemoryEntry:
    """One record in a creature's memory stream."""

    text: str
    importance: int = 5          # 0-10 salience
    timestamp: float = 0.0       # unix seconds; 0.0 -> set at add() time
    kind: str = "observation"    # observation | reflection | plan
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timestamp <= 0.0:
            self.timestamp = time.time()
        self.importance = max(0, min(10, int(self.importance)))
        if self.kind not in _KINDS:
            self.kind = "observation"


# ---------------------------------------------------------------------------
# 512-dim hashed embedding (deterministic, pure stdlib)
# ---------------------------------------------------------------------------

def _hash_bucket(token: str) -> int:
    """Deterministic token -> bucket in [0, EMBED_DIM). blake2b, not hash()."""
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % EMBED_DIM


def _char_embed(text: str) -> dict[int, float]:
    """Char n-gram hashing embedding — works for Cyrillic AND ASCII.

    The repo's hashing-trick encoder (adapters/embedding_classifier) is
    word-level and ASCII-only ([a-z']+), so Russian observations — the
    actual content language of creature memory — would encode to the zero
    vector and relevance would always be 0. This is the same family of
    embedding (blake2b -> 512 buckets, L2-normalized) over char trigrams
    and 4-grams, which captures subword similarity in any alphabet.
    """
    norm = "".join(ch for ch in text.lower() if ch.isalnum() or ch.isspace())
    vec: dict[int, float] = defaultdict(float)
    padded = f" {norm} "
    for width in (3, 4):
        for i in range(len(padded) - width + 1):
            gram = padded[i:i + width]
            vec[_hash_bucket(gram)] += 1.0
    norm_len = math.sqrt(sum(v * v for v in vec.values()))
    if norm_len == 0.0:
        return {}
    return {k: v / norm_len for k, v in vec.items()}


def _embed(text: str) -> dict[int, float]:
    """Text -> L2-normalized sparse 512-dim vector.

    Reuses the EXISTING repo encoder (terramon.adapters.embedding_classifier.
    _encode — hashing trick, blake2b, 512 dims) for ASCII text, so English
    memory lives in the same feature space as the summon classifier; falls
    back to the local char-n-gram embedding for non-ASCII (Russian) text
    and whenever the repo module is unavailable.
    """
    if text.isascii():
        try:
            from terramon.adapters.embedding_classifier import _encode
            vec = _encode(text)
            if vec:
                return vec
        except Exception:
            pass
    return _char_embed(text)


def _cosine(a: dict[int, float], b: dict[int, float]) -> float:
    """Cosine of two L2-normalized sparse vectors = dot over shared keys."""
    if not a or not b:
        return 0.0
    small, big = (a, b) if len(a) < len(b) else (b, a)
    return sum(w * big.get(k, 0.0) for k, w in small.items())


class MemoryStream:
    """Append-only per-creature memory with Generative-Agents retrieval."""

    def __init__(self,
                 entries: list[MemoryEntry] | None = None,
                 reflection_every: int = REFLECTION_EVERY) -> None:
        self.reflection_every = reflection_every
        self._entries: list[MemoryEntry] = list(entries or [])
        self._vec_cache: dict[tuple[str, str], dict[int, float]] = {}

    # ── public views ────────────────────────────────────────────────────

    @property
    def entries(self) -> list[MemoryEntry]:
        """All entries in insertion order (observations, reflections, plans)."""
        return list(self._entries)

    @property
    def observations(self) -> list[MemoryEntry]:
        """Entries with kind == 'observation', oldest first."""
        return [e for e in self._entries if e.kind == "observation"]

    @property
    def reflections(self) -> list[MemoryEntry]:
        """Entries with kind == 'reflection', oldest first."""
        return [e for e in self._entries if e.kind == "reflection"]

    # ── writing ─────────────────────────────────────────────────────────

    def add(self,
            text: str,
            importance: int = 5,
            kind: str = "observation",
            **extra) -> MemoryEntry:
        """Append one entry (timestamp = now) and return it."""
        entry = MemoryEntry(
            text=text,
            importance=importance,
            timestamp=time.time(),
            kind=kind,
            extra=extra,
        )
        self._entries.append(entry)
        return entry

    # ── retrieval: recency + importance + relevance ─────────────────────

    def retrieve(self, query: str, k: int = 5) -> list[MemoryEntry]:
        """Top-k entries by score, most relevant first.

        score = w_rec * recency + w_imp * importance/10 + w_rel * relevance.
        Recency decays exponentially with a 24h half-life; relevance is the
        cosine of the query against the entry in the 512-dim hashed space.
        """
        qvec = _embed(query)
        now = time.time()
        scored: list[tuple[float, MemoryEntry]] = []
        for entry in self._entries:
            age_hours = (now - entry.timestamp) / 3600.0
            recency = 0.5 ** (age_hours / RECENCY_HALF_LIFE_HOURS)
            relevance = _cosine(qvec, self._vec(entry))
            score = (
                RECENCY_WEIGHT * recency
                + IMPORTANCE_WEIGHT * (entry.importance / 10.0)
                + RELEVANCE_WEIGHT * relevance
            )
            scored.append((score, entry))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [entry for _, entry in scored[:max(0, k)]]

    def _vec(self, entry: MemoryEntry) -> dict[int, float]:
        key = (entry.text, entry.kind)
        if key not in self._vec_cache:
            self._vec_cache[key] = _embed(entry.text)
        return self._vec_cache[key]

    # ── reflection trigger (generator lives in reflection.py) ───────────

    def maybe_reflect(self,
                      llm_call=None,
                      reflection_every: int | None = None) -> str | None:
        """Generate + store one reflection when due, else None.

        Due when `reflection_every` observations accumulated since the last
        reflection. llm_call(prompt, system) -> str is injected; on failure
        generate_reflection falls back to a deterministic template. The
        stored reflection gets kind='reflection' and importance >= 8.
        """
        every = reflection_every or self.reflection_every
        if self._observations_since_last_reflection() < every:
            return None
        from terramon.agents.reflection import generate_reflection
        text = generate_reflection(self, llm_call)
        if text:
            self.add(text, importance=REFLECTION_IMPORTANCE, kind="reflection")
        return text

    def _observations_since_last_reflection(self) -> int:
        last = -1
        for i, entry in enumerate(self._entries):
            if entry.kind == "reflection":
                last = i
        return sum(1 for e in self._entries[last + 1:] if e.kind == "observation")

    # ── JSONL persistence (matches data/*.jsonl style) ──────────────────

    def persist(self, path: Path | str) -> None:
        """Append all entries as JSONL (ensure_ascii=False, one per line)."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            for entry in self._entries:
                fh.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")

    @classmethod
    def load(cls, path: Path | str) -> "MemoryStream":
        """Load a stream from JSONL; corrupt lines are skipped, never fatal."""
        stream = cls()
        p = Path(path)
        if not p.exists():
            return stream
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                stream._entries.append(MemoryEntry(**record))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue  # one bad record must not wipe the whole memory
        return stream
