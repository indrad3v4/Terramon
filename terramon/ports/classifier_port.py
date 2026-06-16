"""Classifier port — how Terramon decides which agent a thought seed summons."""

from typing import Protocol


class ClassifierPort(Protocol):
    """Primary port for intent classification."""

    def classify(self, thought_seed: str) -> str:
        """Return the name of the agent best suited to handle the input."""
        ...
