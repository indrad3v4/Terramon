"""Memory port — how Terramon stores and recalls thought seeds."""

from typing import Protocol

from terramon.domain.thought_seed import ThoughtSeed


class MemoryPort(Protocol):
    """Secondary port for persistent agent memory."""

    def save_seed(self, seed: ThoughtSeed) -> None:
        """Persist a thought seed."""
        ...

    def load_all_seeds(self) -> list[ThoughtSeed]:
        """Return every stored thought seed, newest last."""
        ...
