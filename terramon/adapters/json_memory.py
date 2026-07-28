"""JSON-file adapter for the MemoryPort + SQLite replacement.

Audit fix (Phase 0): added I/O error handling, per-line corruption resilience,
logging, and fixed dict mutation (record.pop -> record.get) to avoid clobbering
the persisted record before reconstructing the domain object.

SqliteMemory (P4 I01): streaming reads via SQLite, indexed queries, and
proximity searches without loading the entire file into memory.
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
import time
from collections import Counter
from pathlib import Path
from typing import Any

from terramon.domain.insight import Insight, GeoContext
from terramon.domain.thought_seed import ThoughtSeed
from terramon.ports.memory_port import MemoryPort

log = logging.getLogger("terramon.json_memory")

# ---------------------------------------------------------------------------
# SQLite schema constants
# ---------------------------------------------------------------------------

_SCHEMA_SEEDS = """
CREATE TABLE IF NOT EXISTS seeds (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_input        TEXT NOT NULL,
    summoned_agent   TEXT NOT NULL,
    timestamp        TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'summoned',
    rarity           TEXT NOT NULL DEFAULT 'common',
    price_sats       INTEGER NOT NULL DEFAULT 0,
    paid             INTEGER NOT NULL DEFAULT 0,
    owner_id         TEXT NOT NULL DEFAULT 'player',
    for_trade        INTEGER NOT NULL DEFAULT 0,
    trade_price_sats INTEGER NOT NULL DEFAULT 0,
    insight_driver        TEXT,
    insight_barrier       TEXT,
    insight_therefore     TEXT,
    insight_archetype     TEXT,
    insight_nuance        TEXT,
    insight_confidence    INTEGER,
    insight_geo_lat       REAL,
    insight_geo_lon       REAL,
    insight_geo_place_name TEXT,
    insight_embedding     TEXT,
    lat              REAL NOT NULL DEFAULT 0.0,
    lon              REAL NOT NULL DEFAULT 0.0,
    place_name       TEXT NOT NULL DEFAULT ''
)
"""

_SCHEMA_BONDS = """
CREATE TABLE IF NOT EXISTS bonds (
    agent_id               TEXT PRIMARY KEY,
    bond_level             INTEGER NOT NULL DEFAULT 0,
    player_affinity        TEXT NOT NULL DEFAULT '[]',
    milestone_memory       TEXT NOT NULL DEFAULT '[]',
    player_journal         TEXT NOT NULL DEFAULT '',
    interaction_count      INTEGER NOT NULL DEFAULT 0,
    last_interaction_type  TEXT NOT NULL DEFAULT ''
)
"""

# Fast index on summoned_agent for report_stats() GROUP BY queries.
_INDEX_AGENT = "CREATE INDEX IF NOT EXISTS idx_seeds_agent ON seeds(summoned_agent)"
_INDEX_RARITY = "CREATE INDEX IF NOT EXISTS idx_seeds_rarity ON seeds(rarity)"
_INDEX_TS = "CREATE INDEX IF NOT EXISTS idx_seeds_timestamp ON seeds(timestamp)"


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
            "lat": seed.lat,
            "lon": seed.lon,
            "place_name": seed.place_name,
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
            # Persist embedding if present (Lens #33 Triangularity)
            if seed.insight.embedding is not None:
                record["insight"]["embedding"] = seed.insight.embedding
        # I03: Persist birth_embedding when present (first summon's embedding snapshot)
        if seed.birth_embedding is not None:
            # Ensure int keys survive JSON round-trip
            record["birth_embedding"] = {str(k): v for k, v in seed.birth_embedding.items()}
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
                # Lens #33 Triangularity: deserialize embedding (string keys -> int)
                emb_data = insight_kw.pop("embedding", None)
                if emb_data is not None:
                    insight_kw["embedding"] = {int(k): v for k, v in emb_data.items()}
                record["insight"] = Insight(**insight_kw)
            else:
                # Key may be absent OR explicitly null — treat both as no insight.
                # Remove the key so ThoughtSeed(**record) uses its default None.
                record.pop("insight", None)
            # Pop extra storage fields that aren't part of the domain model.
            # `created_at` duplicates `timestamp` for data-versioning queries
            # but is NOT a field on ThoughtSeed.
            record.pop("created_at", None)
            # I03: Deserialize birth_embedding (string keys -> int) if present
            be_data = record.get("birth_embedding")
            if be_data is not None:
                if isinstance(be_data, dict):
                    record["birth_embedding"] = {int(k): v for k, v in be_data.items()}
            seeds.append(ThoughtSeed(**record))
        return seeds

    # ── Proximity search (G03: Haversine-based find_nearby) ─────────────────

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine distance in km between two lat/lon points."""
        R = 6371.0  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def find_nearby(self, lat: float, lon: float, radius_km: float = 1.0) -> list[tuple[ThoughtSeed, float]]:
        """Find all creatures within `radius_km` of (lat, lon), sorted by distance.

        Returns list of (seed, distance_km) tuples, closest first.
        Seeds without geo coordinates (lat=0, lon=0) are skipped.
        """
        seeds = self.load_all_seeds()
        results: list[tuple[ThoughtSeed, float]] = []
        for s in seeds:
            if not s.lat and not s.lon:
                continue  # skip seeds without real geo
            dist = self._haversine_km(lat, lon, s.lat, s.lon)
            if dist <= radius_km:
                results.append((s, dist))
        results.sort(key=lambda x: x[1])
        return results

    # ── Data stats reporter (Phase 9: Pretraining / Data Versioning) ─────

    # ── Bond persistence ──────────────────────────────────────────────

    def save_bond(self, agent_id: str, bond_data: dict) -> None:
        """Save bond data for a creature agent.

        ``bond_data`` should contain bond_level, player_affinity,
        milestone_memory, and player_journal.

        Stored as a single JSON object per agent_id in a sidecar file.
        """
        bond_path = self.path.with_suffix(".bond.jsonl")
        bond_path.parent.mkdir(parents=True, exist_ok=True)

        # Read existing bonds
        bonds = {}
        if bond_path.exists():
            for line in bond_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    bids = rec.get("agent_id", "")
                    if bids:
                        bonds[bids] = rec
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue

        # Upsert this agent's bond data
        bonds[agent_id] = {
            "agent_id": agent_id,
            "bond_level": bond_data.get("bond_level", 0),
            "player_affinity": bond_data.get("player_affinity", [0.0] * 12),
            "milestone_memory": bond_data.get("milestone_memory", []),
            "player_journal": bond_data.get("player_journal", ""),
            "interaction_count": bond_data.get("interaction_count", 0),
            "last_interaction_type": bond_data.get("last_interaction_type", ""),
        }

        # Write all bonds back (full overwrite — small dataset)
        try:
            with bond_path.open("w", encoding="utf-8") as f:
                for rec in bonds.values():
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except (OSError, IOError) as exc:
            log.error("Failed to write bond data to %s: %s", bond_path, exc)
            raise

    def load_bond(self, agent_id: str) -> dict:
        """Load bond data for a creature agent.

        Returns a dict with defaults if no bond data exists yet.
        """
        bond_path = self.path.with_suffix(".bond.jsonl")
        if not bond_path.exists():
            return {}

        for line in bond_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if rec.get("agent_id") == agent_id:
                    return rec
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
        return {}

    # ── Embedding uniqueness (P1 T07: MINT based on rarity of thought) ─────

    def compute_uniqueness_bonus(self, embedding: dict[int, float]) -> float:
        """Compute MINT price multiplier based on nearest-neighbor cosine distance.

        Loads all existing creature embeddings from memory and finds the minimum
        cosine distance between *embedding* and any existing one. Maps distance
        to a bonus multiplier:

            distance 0.0 (identical)   → bonus 1.0× (no uniqueness)
            distance 1.0 (orthogonal)  → bonus 10.0× (one-of-a-kind)

        Cosine distance = 1 - cosine_similarity, measured over L2-normalised
        512-dim sparse vectors.

        Returns a float in [1.0, 10.0].
        """
        if not embedding:
            return 1.0

        seeds = self.load_all_seeds()
        if not seeds:
            return 1.0  # first creature — nothing to compare against

        min_distance = float("inf")
        for seed in seeds:
            if seed.insight is None or seed.insight.embedding is None:
                continue
            existing = seed.insight.embedding
            # Cosine similarity of L2-normalised sparse vectors = dot product
            # over shared keys.
            small, big = (embedding, existing) if len(embedding) < len(existing) else (existing, embedding)
            sim = sum(w * big.get(k, 0.0) for k, w in small.items())
            distance = 1.0 - sim
            if distance < min_distance:
                min_distance = distance

        if min_distance == float("inf"):
            return 1.0  # no existing embeddings to compare

        # Clamp to [0, 1] and map linearly to [1.0, 10.0]
        clamped = max(0.0, min(min_distance, 1.0))
        bonus = 1.0 + 9.0 * clamped
        return round(bonus, 2)

    # ── I03: Embedding drift tracking ───────────────────────────────────

    def compute_embedding_drift(self, agent_id: str) -> float:
        """Compute how much a creature's embedding has drifted since first summon.

        Drift = 1 - cosine_similarity(birth_embedding, latest_embedding)
        expressed as a percentage (0-100). Returns 0.0 if no drift can be computed
        (no seeds, no birth embedding, or no current embedding).

        The birth_embedding is the first seed's embedding snapshot for this agent.
        The latest embedding is the most recent seed's insight.embedding.
        Embeddings are L2-normalised 512-dim sparse vectors.
        """
        seeds = self.load_all_seeds()
        if not seeds:
            return 0.0

        # Filter seeds for this agent
        agent_seeds = [s for s in seeds if s.summoned_agent == agent_id]
        if not agent_seeds:
            return 0.0

        # Find the birth_embedding — first seed that has one, or first seed's insight.embedding
        birth_emb: dict[int, float] | None = None
        for s in agent_seeds:
            if s.birth_embedding is not None:
                birth_emb = s.birth_embedding
                break
        if birth_emb is None:
            # Fallback: use the first seed's insight.embedding as birth
            first = agent_seeds[0]
            if first.insight and first.insight.embedding:
                birth_emb = first.insight.embedding
        if birth_emb is None:
            return 0.0

        # Latest seed's embedding
        latest = agent_seeds[-1]
        current_emb = None
        if latest.insight and latest.insight.embedding:
            current_emb = latest.insight.embedding
        if current_emb is None:
            return 0.0

        # Cosine similarity on L2-normalised sparse vectors = dot product over shared keys
        small, big = (birth_emb, current_emb) if len(birth_emb) < len(current_emb) else (current_emb, birth_emb)
        sim = sum(w * big.get(k, 0.0) for k, w in small.items())
        # Cosine distance = 1 - cosine_similarity
        distance = 1.0 - sim
        # Clamp to [0, 1] and convert to percentage
        clamped = max(0.0, min(distance, 1.0))
        pct = round(clamped * 100, 1)
        return pct

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


# ======================================================================
# SqliteMemory — drop-in SQLite replacement for JsonMemory
# ======================================================================


def _row_to_seed(row: sqlite3.Row) -> ThoughtSeed:
    """Convert a SQLite row (as sqlite3.Row or dict) to a ThoughtSeed."""
    d = dict(row)

    # Build optional Insight from the flat columns.
    if d.get("insight_driver") is not None:
        insight_kw: dict[str, Any] = {
            "driver": d["insight_driver"],
            "barrier": d["insight_barrier"],
            "therefore": d["insight_therefore"],
            "archetype": d.get("insight_archetype", "") or "",
            "nuance": d.get("insight_nuance", "") or "",
            "confidence": d.get("insight_confidence", 0) or 0,
        }
        # Rehydrate GeoContext.
        if d.get("insight_geo_lat") is not None:
            insight_kw["geo"] = GeoContext(
                lat=d["insight_geo_lat"],
                lon=d["insight_geo_lon"],
                place_name=d.get("insight_geo_place_name", "") or "",
            )
        # Rehydrate embedding (JSON text -> dict).
        emb_raw = d.get("insight_embedding")
        if emb_raw:
            try:
                insight_kw["embedding"] = {int(k): v for k, v in json.loads(emb_raw).items()}
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        insight: Insight | None = Insight(**insight_kw)
    else:
        insight = None

    return ThoughtSeed(
        raw_input=d["raw_input"],
        summoned_agent=d["summoned_agent"],
        timestamp=d["timestamp"],
        status=d.get("status", "summoned"),
        rarity=d.get("rarity", "common"),
        price_sats=d.get("price_sats", 0) or 0,
        paid=bool(d.get("paid", False)),
        insight=insight,
        lat=float(d.get("lat", 0.0) or 0.0),
        lon=float(d.get("lon", 0.0) or 0.0),
        place_name=d.get("place_name", "") or "",
    )


class SqliteMemory(MemoryPort):
    """Stores thought seeds in a local SQLite database.

    Drop-in replacement for JsonMemory that uses the same MemoryPort
    interface. Uses streaming SELECT queries with optional pagination
    instead of loading the entire file into memory.

    Bonds are stored in a separate ``bonds`` table.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables and indexes if they don't exist."""
        self._conn.execute(_SCHEMA_SEEDS)
        self._conn.execute(_SCHEMA_BONDS)
        self._conn.execute(_INDEX_AGENT)
        self._conn.execute(_INDEX_RARITY)
        self._conn.execute(_INDEX_TS)
        self._conn.commit()

    def close(self) -> None:
        """Explicitly close the database connection."""
        self._conn.close()

    # ── Seed persistence ──────────────────────────────────────────────

    def save_seed(self, seed: ThoughtSeed) -> None:
        """INSERT one thought seed as a new row."""
        self._conn.execute(
            """INSERT INTO seeds (
                raw_input, summoned_agent, timestamp, status,
                rarity, price_sats, paid, owner_id, for_trade, trade_price_sats,
                insight_driver, insight_barrier, insight_therefore,
                insight_archetype, insight_nuance, insight_confidence,
                insight_geo_lat, insight_geo_lon, insight_geo_place_name,
                insight_embedding, lat, lon, place_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            self._seed_to_row(seed),
        )
        self._conn.commit()

    @staticmethod
    def _seed_to_row(seed: ThoughtSeed) -> tuple:
        """Flatten a ThoughtSeed (and its optional Insight) into a SQL row."""
        insight_driver = insight_barrier = insight_therefore = None
        insight_archetype = insight_nuance = None
        insight_confidence = None
        insight_geo_lat = insight_geo_lon = insight_geo_place_name = None
        insight_embedding = None

        if seed.insight is not None:
            ins = seed.insight
            insight_driver = ins.driver
            insight_barrier = ins.barrier
            insight_therefore = ins.therefore
            insight_archetype = ins.archetype
            insight_nuance = ins.nuance
            insight_confidence = ins.confidence
            if ins.geo is not None:
                insight_geo_lat = ins.geo.lat
                insight_geo_lon = ins.geo.lon
                insight_geo_place_name = ins.geo.place_name
            if ins.embedding is not None:
                # Serialise as JSON text so SQLite can index it.
                insight_embedding = json.dumps(ins.embedding, ensure_ascii=False)

        return (
            seed.raw_input,
            seed.summoned_agent,
            seed.timestamp,
            seed.status,
            seed.rarity,
            seed.price_sats,
            1 if seed.paid else 0,
            seed.owner_id if hasattr(seed, 'owner_id') else 'player',
            1 if getattr(seed, 'for_trade', False) else 0,
            getattr(seed, 'trade_price_sats', 0),
            insight_driver,
            insight_barrier,
            insight_therefore,
            insight_archetype,
            insight_nuance,
            insight_confidence,
            insight_geo_lat,
            insight_geo_lon,
            insight_geo_place_name,
            insight_embedding,
            seed.lat,
            seed.lon,
            seed.place_name,
        )

    def load_all_seeds(self, offset: int | None = None, limit: int | None = None) -> list[ThoughtSeed]:
        """Return every stored thought seed, oldest first.

        Supports optional pagination via ``offset`` and ``limit``.
        When both are None (the default), returns all rows.
        """
        query = (
            "SELECT * FROM seeds ORDER BY id ASC"
            + (" LIMIT ?" if limit is not None else "")
            + (" OFFSET ?" if offset is not None else "")
        )
        params: list[int] = []
        if limit is not None:
            params.append(limit)
        if offset is not None:
            params.append(offset)

        rows = self._conn.execute(query, params).fetchall()
        return [_row_to_seed(r) for r in rows]

    def count_seeds(self) -> int:
        """Return total number of stored seeds (zero-overhead)."""
        row = self._conn.execute("SELECT COUNT(*) AS cnt FROM seeds").fetchone()
        return row["cnt"] if row else 0

    # ── Proximity search (G03: Haversine-based find_nearby) ─────────────────

    def find_nearby(self, lat: float, lon: float, radius_km: float = 1.0) -> list[tuple[ThoughtSeed, float]]:
        """Find all creatures within `radius_km` using SQL-level Haversine.

        Returns list of (seed, distance_km) tuples, closest first.
        Seeds without geo coordinates (lat=0, lon=0) are skipped.
        """
        # Haversine formula in SQL: compute distance for each row, filter, sort.
        query = """
            SELECT *, (
                6371.0 * 2 * ASIN(SQRT(
                    POWER(SIN(RADIANS(lat - ?) / 2), 2) +
                    COS(RADIANS(?)) * COS(RADIANS(lat)) *
                    POWER(SIN(RADIANS(lon - ?) / 2), 2)
                ))
            ) AS dist_km
            FROM seeds
            WHERE lat != 0 AND lon != 0
              AND (
                6371.0 * 2 * ASIN(SQRT(
                    POWER(SIN(RADIANS(lat - ?) / 2), 2) +
                    COS(RADIANS(?)) * COS(RADIANS(lat)) *
                    POWER(SIN(RADIANS(lon - ?) / 2), 2)
                ))
              ) <= ?
            ORDER BY dist_km ASC
        """
        params = (lat, lat, lon, lat, lat, lon, radius_km)
        rows = self._conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            seed = _row_to_seed(row)
            dist = float(row["dist_km"])
            results.append((seed, dist))
        return results

    # ── Bond persistence ──────────────────────────────────────────────

    def save_bond(self, agent_id: str, bond_data: dict) -> None:
        """Upsert bond data for a creature agent."""
        self._conn.execute(
            """INSERT INTO bonds (agent_id, bond_level, player_affinity,
                                  milestone_memory, player_journal,
                                  interaction_count, last_interaction_type)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(agent_id) DO UPDATE SET
                   bond_level            = excluded.bond_level,
                   player_affinity       = excluded.player_affinity,
                   milestone_memory      = excluded.milestone_memory,
                   player_journal        = excluded.player_journal,
                   interaction_count     = excluded.interaction_count,
                   last_interaction_type = excluded.last_interaction_type""",
            (
                agent_id,
                bond_data.get("bond_level", 0),
                json.dumps(bond_data.get("player_affinity", [0.0] * 12)),
                json.dumps(bond_data.get("milestone_memory", [])),
                bond_data.get("player_journal", ""),
                bond_data.get("interaction_count", 0),
                bond_data.get("last_interaction_type", ""),
            ),
        )
        self._conn.commit()

    def load_bond(self, agent_id: str) -> dict:
        """Load bond data for a creature agent.

        Returns a dict with defaults if no bond data exists yet.
        """
        row = self._conn.execute(
            "SELECT * FROM bonds WHERE agent_id = ?", (agent_id,)
        ).fetchone()
        if row is None:
            return {}
        d = dict(row)
        # Deserialise JSON columns.
        affinity = d.get("player_affinity")
        d["player_affinity"] = json.loads(affinity) if affinity else [0.0] * 12
        memories = d.get("milestone_memory")
        d["milestone_memory"] = json.loads(memories) if memories else []
        return d

    # ── Embedding uniqueness (P1 T07) ─────────────────────────────────

    def compute_uniqueness_bonus(self, embedding: dict[int, float]) -> float:
        """Compute MINT price multiplier based on nearest-neighbour cosine distance.

        Streams embeddings from SQLite instead of loading all rows into memory.
        """
        if not embedding:
            return 1.0

        min_distance = float("inf")
        cursor = self._conn.execute(
            "SELECT insight_embedding FROM seeds WHERE insight_embedding IS NOT NULL"
        )
        for row in cursor:
            emb_raw = row["insight_embedding"]
            if not emb_raw:
                continue
            try:
                existing = json.loads(emb_raw)
                existing_int = {int(k): v for k, v in existing.items()}
            except (json.JSONDecodeError, TypeError, ValueError):
                continue

            # Cosine similarity of L2-normalised sparse vectors = dot product
            # over shared keys.
            small, big = (embedding, existing_int) if len(embedding) < len(existing_int) else (existing_int, embedding)
            sim = sum(w * big.get(k, 0.0) for k, w in small.items())
            distance = 1.0 - sim
            if distance < min_distance:
                min_distance = distance

        if min_distance == float("inf"):
            return 1.0

        # Clamp to [0, 1] and map linearly to [1.0, 10.0]
        clamped = max(0.0, min(min_distance, 1.0))
        bonus = 1.0 + 9.0 * clamped
        return round(bonus, 2)

    # ── Data stats reporter ─────────────────────────────────────────────

    def report_stats(self) -> dict:
        """Return aggregate statistics using SQL aggregate functions."""
        total = self._conn.execute("SELECT COUNT(*) AS cnt FROM seeds").fetchone()["cnt"]

        if total == 0:
            return {
                "total_seeds": 0,
                "unique_agents": 0,
                "rarity_distribution": {},
                "time_span_days": 0,
                "oldest_seed": None,
                "newest_seed": None,
            }

        # Unique agents
        unique_row = self._conn.execute(
            "SELECT COUNT(DISTINCT summoned_agent) AS cnt FROM seeds"
        ).fetchone()
        unique_agents = unique_row["cnt"]

        # Rarity distribution via GROUP BY
        rarity_rows = self._conn.execute(
            "SELECT rarity, COUNT(*) AS cnt FROM seeds GROUP BY rarity ORDER BY rarity"
        ).fetchall()
        rarity_distribution = {r["rarity"]: r["cnt"] for r in rarity_rows}

        # Time span
        oldest = self._conn.execute(
            "SELECT timestamp FROM seeds ORDER BY id ASC LIMIT 1"
        ).fetchone()["timestamp"]
        newest = self._conn.execute(
            "SELECT timestamp FROM seeds ORDER BY id DESC LIMIT 1"
        ).fetchone()["timestamp"]

        time_span_days = 0
        if oldest and newest:
            try:
                from datetime import datetime

                t0 = datetime.fromisoformat(oldest)
                t1 = datetime.fromisoformat(newest)
                time_span_days = max(0, (t1 - t0).days)
            except (ValueError, TypeError):
                time_span_days = 0

        return {
            "total_seeds": total,
            "unique_agents": unique_agents,
            "rarity_distribution": rarity_distribution,
            "time_span_days": time_span_days,
            "oldest_seed": oldest,
            "newest_seed": newest,
        }

    # ── P3 M04: Creature trading ──────────────────────────────────────

    def list_for_trade(self, seed_id: int, price_sats: int) -> bool:
        """Mark a creature as available for trade at the given price.

        Returns True if the seed was found and updated, False otherwise.
        """
        cursor = self._conn.execute(
            "UPDATE seeds SET for_trade = 1, trade_price_sats = ? WHERE id = ?",
            (price_sats, seed_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def cancel_trade(self, seed_id: int) -> bool:
        """Remove a creature from the trade listings."""
        cursor = self._conn.execute(
            "UPDATE seeds SET for_trade = 0, trade_price_sats = 0 WHERE id = ?",
            (seed_id,),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def get_trade_listings(self) -> list[dict]:
        """Return all seeds currently listed for trade.

        Each entry is a dict with seed info plus the trade_price_sats.
        """
        rows = self._conn.execute(
            "SELECT * FROM seeds WHERE for_trade = 1 ORDER BY trade_price_sats ASC"
        ).fetchall()
        return [dict(r) for r in rows]

    def transfer_ownership(self, seed_id: int, new_owner: str) -> bool:
        """Transfer a creature to a new owner.

        Resets for_trade flags and updates owner_id.
        Returns True on success.
        """
        cursor = self._conn.execute(
            "UPDATE seeds SET owner_id = ?, for_trade = 0, trade_price_sats = 0 WHERE id = ?",
            (new_owner, seed_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def execute_trade(self, seed_id: int, seller: str, buyer: str, price_sats: int) -> bool:
        """Execute a full trade: transfer ownership and mark as traded.

        Validates the creature is still listed for trade by the seller
        at the expected price before executing.
        Returns True on success.
        """
        row = self._conn.execute(
            "SELECT * FROM seeds WHERE id = ? AND for_trade = 1 AND owner_id = ? AND trade_price_sats = ?",
            (seed_id, seller, price_sats),
        ).fetchone()
        if row is None:
            return False
        return self.transfer_ownership(seed_id, buyer)


# ======================================================================
# Migration helper — copy JSONL data into a SQLite database
# ======================================================================


def migrate(json_path: Path | str, sqlite_path: Path | str) -> SqliteMemory:
    """Migrate a JSONL memory file into a new SQLite database.

    Reads every line from the existing JSONL file, parses it as a
    ThoughtSeed record, and inserts it into a fresh SqliteMemory database.
    The original JSONL file is left untouched.

    Args:
        json_path: Path to the existing ``.jsonl`` memory file.
        sqlite_path: Path for the output ``.db`` file.

    Returns:
        A populated SqliteMemory instance ready for use.
    """
    json_path = Path(json_path)
    sqlite_path = Path(sqlite_path)

    memory = SqliteMemory(sqlite_path)

    if not json_path.exists():
        log.info("No JSONL file at %s — starting with empty SQLite DB", json_path)
        return memory

    raw = json_path.read_text(encoding="utf-8")
    count = 0
    for idx, line in enumerate(raw.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            log.warning("Corrupt line %d in %s: %s — skipping", idx, json_path, exc)
            continue

        # Reconstruct Insight if present.
        insight: Insight | None = None
        insight_data = record.get("insight")
        if insight_data:
            insight_kw = dict(insight_data)
            geo_data = insight_kw.pop("geo", None)
            if geo_data:
                insight_kw["geo"] = GeoContext(**geo_data)
            emb_data = insight_kw.pop("embedding", None)
            if emb_data is not None:
                insight_kw["embedding"] = {int(k): v for k, v in emb_data.items()}
            insight = Insight(**insight_kw)

        seed = ThoughtSeed(
            raw_input=record.get("raw_input", ""),
            summoned_agent=record.get("summoned_agent", ""),
            timestamp=record.get("timestamp", ""),
            status=record.get("status", "summoned"),
            rarity=record.get("rarity", "common"),
            price_sats=record.get("price_sats", 0) or 0,
            paid=bool(record.get("paid", False)),
            insight=insight,
            lat=float(record.get("lat", 0.0) or 0.0),
            lon=float(record.get("lon", 0.0) or 0.0),
            place_name=record.get("place_name", "") or "",
        )
        memory.save_seed(seed)
        count += 1

    log.info("Migrated %d seed(s) from %s to %s", count, json_path, sqlite_path)
    return memory


# ── Auto-migrate on first use (optional convenience) ─────────────────


def migrate_if_exists(json_path: Path | str, sqlite_path: Path | str) -> SqliteMemory:
    """Return a SqliteMemory, migrating old JSONL data on the first run.

    Only migrates when the SQLite DB does not yet exist (idempotent).
    """
    json_path = Path(json_path)
    sqlite_path = Path(sqlite_path)

    if not sqlite_path.exists() and json_path.exists():
        return migrate(json_path, sqlite_path)

    return SqliteMemory(sqlite_path)
