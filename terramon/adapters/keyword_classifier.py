"""Keyword-based adapter for the ClassifierPort — v3: Jungian archetypes."""

from terramon.ports.classifier_port import ClassifierPort


class KeywordClassifier(ClassifierPort):
    """Routes thought seeds to Jungian archetypes using simple keyword maps."""

    DEFAULT_AGENT = "Innocent"

    KEYWORDS: dict[str, list[str]] = {
        "Innocent": ["safe", "trust", "good", "pure", "hope", "faith"],
        "Hero": ["overcome", "strong", "challenge", "courage", "battle", "win"],
        "Caregiver": ["help", "care", "protect", "nurture", "give", "kind"],
        "Explorer": ["explore", "freedom", "discover", "journey", "wander", "road"],
        "Sage": ["truth", "wisdom", "knowledge", "understand", "learn", "think"],
        "Creator": ["create", "build", "make", "imagine", "art", "design"],
        "Rebel": ["rebel", "break", "freedom", "change", "revolution", "fight"],
    }

    def classify(self, thought_seed: str) -> str:
        lowered = thought_seed.lower()
        scores = {
            agent: sum(1 for keyword in keywords if keyword in lowered)
            for agent, keywords in self.KEYWORDS.items()
        }
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else self.DEFAULT_AGENT
