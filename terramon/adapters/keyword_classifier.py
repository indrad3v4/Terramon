"""Keyword-based adapter for the ClassifierPort."""

from terramon.ports.classifier_port import ClassifierPort


class KeywordClassifier(ClassifierPort):
    """Routes thought seeds to agents using simple keyword maps."""

    DEFAULT_AGENT = "Scout"

    KEYWORDS: dict[str, list[str]] = {
        "Ranger": ["scan", "image", "photo", "camera", "visual", "see", "look"],
        "Archivist": ["log", "history", "record", "memory", "past", "archive"],
        "Strategist": ["plan", "attack", "defend", "strategy", "move", "territory"],
    }

    def classify(self, thought_seed: str) -> str:
        """Return the agent whose keywords appear most in the input."""
        lowered = thought_seed.lower()
        scores = {
            agent: sum(1 for keyword in keywords if keyword in lowered)
            for agent, keywords in self.KEYWORDS.items()
        }
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else self.DEFAULT_AGENT
