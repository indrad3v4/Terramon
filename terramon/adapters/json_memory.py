"""JSON-file adapter for the MemoryPort.

Audit fix (Phase 0): added I/O error handling, per-line corruption resilience,
logging, and fixed dict mutation (record.pop -> record.get) to avoid clobbering
the persisted record before reconstructing the domain object.
"""

from __future__ import annotations

import json
import logging
import time
from collections import Counter
from pathlib import Path

from terramon.domain.insight import Insight
from terramon.domain.thought_seed import ThoughtSeed
from terramon.ports.memory_port import MemoryPort

log = logging.getLogger("terramon.json_memory")


class JsonMemory(MemoryPort):
    """Stores thought seeds as newline-delimited JSON records."""

    def __init__(self, path: Path | str) -> None:
        """Open or create the memory file at ``path``."""
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def save_seed(self, seed: ThoughtSeed) -> None:
        """Append one thought seed to the memory file."""
        record = {
            "raw_input": seed.raw_input,
            "summoned_agent": seed.summoned_agent,
            "timestamp": seed.timestamp,
            "created_at": seed.timestamp,  # data versioning: stable creation timestamp
            "status": seed.status,
            "rarity": seed.rarity,
            "price_sats": seed.price_sats,
            "paid": seed.paid,
        }
        # Persist the insight (FIX 2) as a nested json_memory column when present.
        # Old seeds without an insight simply omit the key -> backward compatible.
        if seed.insight is not None:
            record["insight"] = {
                "driver": seed.insight.driver,
                "barrier": seed.insight.barrier,
                "therefore": seed.insight.therefore,
                # v3 fields (Jungian archetype + confidence)
                "archetype": seed.insight.archetype,
                "nuance": seed.insight.nuance,
                "confidence": seed.insight.confidence,
            }
            # Persist geo if present
            if seed.insight.geo is not None:
                record["insight"]["geo"] = {
                    "lat": seed.insight.geo.lat,
                    "lon": seed.insight.geo.lon,
                    "place_name": seed.insight.geo.place_name,
                }
        try:
            with self.path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(record, ensure_ascii=False) + "\n")
        except (OSError, IOError) as exc:
            log.error("Failed to append seed to %s: %s", self.path, exc)
            raise

    def load_all_seeds(self) -> list[ThoughtSeed]:
        """Return every stored thought seed, oldest first.

        Resilient: corrupt or unparseable lines are logged and skipped so a
        single bad record doesn't wipe out the full memory.
        """
        seeds: list[ThoughtSeed] = []
        if not self.path.exists():
            return seeds
        raw = self.path.read_text(encoding="utf-8")
        for idx, line in enumerate(raw.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                log.warning("Corrupt memory line %d in %s: %s — skipping", idx, self.path, exc)
                continue
            # Use .get() instead of .pop() so we don't mutate the record dict
            # before passing it to the domain constructor.
            insight_data = record.get("insight")
            if insight_data:
                # v3: convert geo dict to GeoContext if present; copy first so
                # we don't mutate the dict we just read from the JSON line.
                insight_kw = dict(insight_data)
                geo_data = insight_kw.pop("geo", None)
                if geo_data:
                    from terramon.domain.insight import GeoContext
                    insight_kw["geo"] = GeoContext(**geo_data)
                record["insight"] = Insight(**insight_kw)
            else:
                # Key may be absent OR explicitly null — treat both as no insight.
                # Remove the key so ThoughtSeed(**record) uses its default None.
                record.pop("insight", None)
            # Pop extra storage fields that aren't part of the domain model.
            # `created_at` duplicates `timestamp` for data-versioning queries
            # but is NOT a field on ThoughtSeed.
            record.pop("created_at", None)
            seeds.append(ThoughtSeed(**record))
        return seeds

    # ── Data stats reporter (Phase 9: Pretraining / Data Versioning) ─────

    def report_stats(self) -> dict:
        """Return aggregate statistics about stored thought seeds.

        Returns:
            dict with keys: total_seeds, unique_agents, rarity_distribution,
            time_span_days, oldest_seed, newest_seed.
        """
        seeds = self.load_all_seeds()
        if not seeds:
            return {
                "total_seeds": 0,
                "unique_agents": 0,
                "rarity_distribution": {},
                "time_span_days": 0,
                "oldest_seed": None,
                "newest_seed": None,
            }

        # Rarity distribution
        rarity_counts: Counter = Counter(s.rarity for s in seeds)

        # Unique agents
        agents = {s.summoned_agent for s in seeds}

        # Time span — try both created_at and timestamp
        timestamps = []
        for s in seeds:
            ts = getattr(s, "created_at", s.timestamp) or s.timestamp
            timestamps.append(ts)
        timestamps = sorted(timestamps)

        # Parse ISO-ish timestamps to compute day span
        time_span_days = 0
        if len(timestamps) >= 2:
            try:
                from datetime import datetime
                t0 = datetime.fromisoformat(timestamps[0])
                t1 = datetime.fromisoformat(timestamps[-1])
                time_span_days = max(0, (t1 - t0).days)
            except (ValueError, TypeError):
                time_span_days = 0

        return {
            "total_seeds": len(seeds),
            "unique_agents": len(agents),
            "rarity_distribution": dict(rarity_counts),
            "time_span_days": time_span_days,
            "oldest_seed": timestamps[0] if timestamps else None,
            "newest_seed": timestamps[-1] if timestamps else None,
        }
