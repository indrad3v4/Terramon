"""Rarity — probabilistic rarity distribution (Lesson 06: Probability & Distributions).

v2: Replaced binary keyword-match with Dirichlet-multinomial distribution.

Old system: hardcoded keyword tuples (binary Dirac-delta).
New system: each text gets a PROBABILITY distribution over 4 rarity tiers,
sampled once per summon. Rare/legendary texts have higher probability of
those tiers but are never guaranteed — preserving surprise and expected
value (EV = sum(P(tier) × price(tier)) over many summons).

Pure domain (no I/O).
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from enum import Enum


class Rarity(str, Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    LEGENDARY = "legendary"


RARITY_PRICE_SATS = {
    Rarity.COMMON: 0,
    Rarity.UNCOMMON: 0,
    Rarity.RARE: 1000,
    Rarity.LEGENDARY: 5000,
}

# Dirichlet prior — base probability vector BEFORE seeing thought content.
# [common, uncommon, rare, legendary] — the "default odds" of any summon.
# The thought's rarity-score shifts probability mass toward rarer tiers.
_DIRICHLET_PRIOR = [8.0, 4.0, 2.0, 1.0]  # total = 15.0 → P(common)=53%

# How much the thought content can shift the distribution from the prior.
# Lower = more conservative (slower to move probability to rare).
_CONCENTRATION_STRENGTH = 6.0


@dataclass
class RarityResult:
    rarity: Rarity
    price_sats: int
    probabilities: list[float]  # [P(common), P(uncommon), P(rare), P(legendary)]


def _rarity_logits(text: str) -> list[float]:
    """Score rarity signals in the text as log-odds against the prior.

    Returns a list of 4 logits — one per rarity tier — that get added
    to the Dirichlet prior alphas before softmax sampling.

    Lesson 06 concept: we're computing P(rarity | text) ∝ P(text | rarity) × P(rarity)
    where the prior is the Dirichlet base rate and the text evidence shifts mass.
    """
    lowered = text.lower()

    # Legendary signals (strongest shift — big logit on legendary)
    legendary_terms = ("i am the", "command the", "ascend", "i surrender to the",
                       "the universe", "the void", "ancient truth")
    legendary_score = sum(1 for t in legendary_terms if t in lowered)

    # Rare signals
    rare_terms = ("rare", "lost", "alone", "shadow", "break", "truth",
                  "secret", "hidden", "forbidden")
    rare_score = sum(1 for t in rare_terms if t in lowered)

    # Uncommon signals (mild)
    uncommon_terms = ("search", "journey", "seek", "wonder", "deep", "beyond")
    uncommon_score = sum(1 for t in uncommon_terms if t in lowered)

    # Normalize: stronger signals → bigger shift
    return [
        -legendary_score * 0.5,                     # common logit
        -legendary_score * 0.3 - rare_score * 0.2,  # uncommon logit
        +rare_score * 1.0 + legendary_score * 0.3,  # rare logit
        +legendary_score * 2.0 + rare_score * 0.5,  # legendary logit
    ]


def _softmax(logits: list[float]) -> list[float]:
    m = max(logits)
    e = [math.exp(x - m) for x in logits]
    s = sum(e)
    return [ei / s for ei in e]


def _dirichlet_sample(alphas: list[float], seed_hash: str) -> int:
    """Sample from a Dirichlet-Multinomial distribution.

    Each alpha = prior concentration + evidence. The hash seeds the
    deterministic sample so the same text summons the same rarity
    (for consistency), but different texts sample differently.
    """
    # Convert Dirichlet to flat probabilities via softmax of log-alphas
    log_alphas = [math.log(max(a, 1e-12)) for a in alphas]
    probs = _softmax(log_alphas)

    # Deterministic sample from categorical using blake2b hash
    digest = hashlib.blake2b(seed_hash.encode("utf-8"), digest_size=4).digest()
    r = int.from_bytes(digest, "big") / (2 ** 32)

    cumulative = 0.0
    for i, p in enumerate(probs):
        cumulative += p
        if r <= cumulative:
            return i
    return len(probs) - 1


def classify_rarity(thought_seed: str) -> RarityResult:
    """Map a thought to a probabilistic rarity tier via Dirichlet distribution.

    The same text always summons the same rarity (deterministic sampling).
    Different texts with similar content sample from the same distribution,
    giving graded probability rather than binary matches.

    Returns RarityResult with the sampled tier AND the full probability
    vector (for frontend display: "Rarity odds").
    """
    logits = _rarity_logits(thought_seed)

    # Add logits to the Dirichlet prior alphas (shift probability mass)
    alphas_log = [math.log(a) + l for a, l in zip(_DIRICHLET_PRIOR, logits)]
    # Convert back to alpha space (exponentiate)
    max_log = max(alphas_log)
    alphas = [math.exp(a - max_log) * _CONCENTRATION_STRENGTH for a in alphas_log]

    # Compute the full probability vector (for display)
    probs = _softmax([math.log(a) for a in alphas])

    # Sample
    idx = _dirichlet_sample(alphas, thought_seed)

    rarity = list(Rarity)[idx]
    return RarityResult(
        rarity=rarity,
        price_sats=RARITY_PRICE_SATS[rarity],
        probabilities=[round(p, 4) for p in probs],
    )
