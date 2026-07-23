"""JSON-file adapter for the MemoryPort."""

import json
from pathlib import Path

from terramon.domain.insight import Insight
from terramon.domain.thought_seed import ThoughtSeed
from terramon.ports.memory_port import MemoryPort


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
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    def load_all_seeds(self) -> list[ThoughtSeed]:
        """Return every stored thought seed, oldest first."""
        seeds: list[ThoughtSeed] = []
        if not self.path.exists():
            return seeds
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            # Rehydrate the insight (FIX 2) if the persisted record carries one.
            insight_data = record.pop("insight", None)
            if insight_data:
                # v3: convert geo dict to GeoContext if present
                geo_data = insight_data.pop("geo", None)
                if geo_data:
                    from terramon.domain.insight import GeoContext
                    insight_data["geo"] = GeoContext(**geo_data)
                record["insight"] = Insight(**insight_data)
            seeds.append(ThoughtSeed(**record))
        return seeds
