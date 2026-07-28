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

    def find_nearby(self, lat: float, lon: float, radius_km: float = 1.0) -> list[tuple[ThoughtSeed, float]]:
        """Find seeds within a given radius of (lat, lon), sorted by distance.
        Returns list of (seed, distance_km) tuples.
        """
        ...

    def save_bond(self, agent_id: str, bond_data: dict) -> None:
        """Save bond data for a creature agent."""
        ...

    def load_bond(self, agent_id: str) -> dict:
        """Load bond data for a creature agent. Returns empty dict if none."""
        ...
