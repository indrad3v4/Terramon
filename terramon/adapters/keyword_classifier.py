"""Keyword-based adapter for the ClassifierPort — v3: Jungian archetypes.

Phase 2 enhancements (Classical ML):
  - Weighted scoring: rarer keywords (appearing in fewer archetypes) get higher
    weight, using log( N / df_k ) where N = # archetypes and df_k = # archetypes
    containing keyword k. This makes discriminative keywords matter more.
  - Expanded keyword lists: all 12 Jungian archetypes now have 10 keywords each
    (was 7 archetypes × 6 keywords). Added Orphan, Lover, Jester, Magician,
    and Ruler.
"""

from __future__ import annotations

import math
from collections import defaultdict

from terramon.ports.classifier_port import ClassifierPort


class KeywordClassifier(ClassifierPort):
    """Routes thought seeds to Jungian archetypes via weighted keyword matching."""

    DEFAULT_AGENT = "Innocent"

    # v4: All 12 Jungian archetypes with expanded keyword lists.
    # Keywords chosen to capture the core psychological drive of each archetype.
    KEYWORDS: dict[str, list[str]] = {
        "Innocent": [
            "safe", "trust", "good", "pure", "hope", "faith",
            "innocent", "honest", "kind", "peace",
        ],
        "Orphan": [
            "alone", "lonely", "outsider", "belong", "left out",
            "abandoned", "lost", "nobody", "forgotten", "rejected",
        ],
        "Hero": [
            "overcome", "strong", "challenge", "courage", "battle", "win",
            "brave", "fight", "save", "triumph",
        ],
        "Caregiver": [
            "help", "care", "protect", "nurture", "give", "kind",
            "compassion", "support", "heal", "comfort",
        ],
        "Explorer": [
            "explore", "freedom", "discover", "journey", "wander", "road",
            "adventure", "seek", "travel", "frontier",
        ],
        "Sage": [
            "truth", "wisdom", "knowledge", "understand", "learn", "think",
            "study", "teach", "logic", "reason",
        ],
        "Creator": [
            "create", "build", "make", "imagine", "art", "design",
            "invent", "vision", "craft", "inspire",
        ],
        "Rebel": [
            "rebel", "break", "freedom", "change", "revolution", "fight",
            "defy", "resist", "outsider", "radical",
        ],
        "Lover": [
            "love", "romance", "passion", "intimate", "heart", "beautiful",
            "desire", "connection", "soul", "devotion",
        ],
        "Jester": [
            "funny", "laugh", "joke", "playful", "silly", "humor",
            "joy", "fun", "dance", "absurd",
        ],
        "Magician": [
            "transform", "magic", "dream", "vision", "miracle", "universe",
            "manifest", "energy", "alchemy", "destiny",
        ],
        "Ruler": [
            "lead", "power", "control", "order", "authority", "command",
            "rule", "king", "govern", "discipline",
        ],
    }

    def __init__(self) -> None:
        """Precompute inverse keyword frequency weights.

        Weight = log(N / df_k) where N = #archetypes, df_k = #archetypes
        whose keyword list contains keyword k. Keywords unique to one
        archetype get the highest weight (~2.48). Keywords shared by
        many archetypes get low weight.
        """
        n_archetypes = len(self.KEYWORDS)

        # Count how many archetypes contain each keyword
        kw_df: dict[str, int] = defaultdict(int)
        for agent, kws in self.KEYWORDS.items():
            seen_kw: set[str] = set()
            for kw in kws:
                if kw not in seen_kw:
                    kw_df[kw] += 1
                    seen_kw.add(kw)

        # Build weighted keyword lists
        self._weights: dict[str, list[tuple[str, float]]] = {}
        for agent, kws in self.KEYWORDS.items():
            weighted: list[tuple[str, float]] = []
            for kw in kws:
                df = max(kw_df.get(kw, 1), 1)
                weight = math.log(n_archetypes / df)
                weighted.append((kw, weight))
            self._weights[agent] = weighted

    def classify(self, thought_seed: str) -> str:
        """Classify by weighted keyword matching.

        Each archetype's score = sum of weights of its keywords found in the
        input. Rarer keywords contribute more, so a single unique keyword
        can outweigh several common ones.
        """
        lowered = thought_seed.lower()
        scores: dict[str, float] = {}
        for agent, weighted_kws in self._weights.items():
            total = 0.0
            for kw, w in weighted_kws:
                if kw in lowered:
                    total += w
            scores[agent] = total

        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else self.DEFAULT_AGENT
