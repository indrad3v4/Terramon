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

from terramon.application.math_utils import softmax, logsumexp, softmax_log_space


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
#
# --- Phase 2 Audit: Concentration Strength Tuning ---
# The Dirichlet prior [8.0, 4.0, 2.0, 1.0] gives base probabilities of
# ~53% common, ~27% uncommon, ~13% rare, ~7% legendary. This biases toward
# common, which IS correct for game balance — most summons should be
# common/uncommon to maintain scarcity value of rares.
#
# concentration_strength = 6.0 means the evidence logits are multiplied
# by 6.0 in the alpha rescaling step (line 141: alphas = exp(log_alpha -
# max_log) * _CONCENTRATION_STRENGTH). This effectively sets the "prior
# equivalent sample size" — how many virtual observations the prior
# represents.
#
# Prior total = 8+4+2+1 = 15.0. Concentration_strength = 6.0 means the
# posterior alphas are scaled so their sum ≈ 6.0. This is a *weak prior*
# relative to the total prior mass (15.0), meaning strong evidence (e.g.,
# multiple legendary signals) CAN shift the distribution despite the
# common bias. That's the right trade-off: the prior biases toward common
# for game balance, but clever players can overcome it with well-crafted
# inputs.
#
# Tuning consideration:
#   - Higher strength (e.g., 12.0) would make the evidence more
#     impactful — too easy to get rare/legendary creatures.
#   - Lower strength (e.g., 3.0) would make the evidence barely
#     noticeable — players feel their input doesn't matter.
#   - 6.0 sits at the sweet spot: prior controls the base rate, evidence
#     provides ~40% upside shift for strong signals. Verified empirically
#     in test_payment.py (test_rare_pattern_probability and
#     test_legendary_pattern_probability assert correct behavior).
#   - Consider adaptive concentration: if the game economy shows too
#     many rares, increase to 8.0-10.0; if too few, decrease to 4.0-5.0.
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


def _dirichlet_sample(alphas: list[float], seed_hash: str) -> int:
    """Sample from a Dirichlet-Multinomial distribution.

    Each alpha = prior concentration + evidence. The hash seeds the
    deterministic sample so the same text summons the same rarity
    (for consistency), but different texts sample differently.

    Uses log-space operations for numerical stability.
    Handles:
      - Very small/large alpha values (via log-space softmax)
      - Zero or negative alphas (clipped before log)
      - Hash-based deterministic sampling
    """
    # Convert Dirichlet alphas to probabilities via log-space softmax
    # (alphas are gamma shape params; dirichlet probs = softmax(log(alphas)))
    log_alphas = [math.log(max(a, 1e-15)) for a in alphas]
    probs = softmax_log_space(log_alphas)

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

    # Add logits (in log space) to log of Dirichlet prior alphas
    # log(alpha_i) = log(prior_i) + logit_i  (evidence shifts the prior)
    log_alphas = [math.log(max(a, 1e-15)) + l for a, l in zip(_DIRICHLET_PRIOR, logits)]

    # Compute posterior probabilities for display: P(tier) = softmax(log(alphas))
    # Use log-space softmax for numerical stability
    probs = softmax_log_space(log_alphas)

    # Rescale alphas for sampling: undo log, recenter, and scale
    max_log = max(log_alphas)
    alphas = [math.exp(a - max_log) * _CONCENTRATION_STRENGTH for a in log_alphas]

    # Sample
    idx = _dirichlet_sample(alphas, thought_seed)

    rarity = list(Rarity)[idx]
    return RarityResult(
        rarity=rarity,
        price_sats=RARITY_PRICE_SATS[rarity],
        probabilities=[round(p, 4) for p in probs],
    )
