"""JSON-file adapter for the MemoryPort."""

import json
from pathlib import Path

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
            seeds.append(ThoughtSeed(**record))
        return seeds
