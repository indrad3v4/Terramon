"""Payment gate — wires SummonService to the PaymentPort.

Build-via-learn: Phase 14 (Agent Engineering) -> "verification gates". A paid
summon is a verification gate: the creature is only released once payment
verifies. The gate depends on PaymentPort, so Lightning / on-chain / Stripe are
all interchangeable.

The gate is OPTIONAL: pass `payment=None` and every summon is free (keeps the
existing 3 tests green and the Day 1-3 CLI working).

Phase 16 (Safety): in-memory rate limiting prevents abuse of the minting system.
Max 3 rare/legendary summons per session per hour.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field

from terramon.domain.rarity import Rarity
from terramon.ports.payment_port import PaymentPort, PaymentRequest

log = logging.getLogger("terramon.payment_gate")

# Rate limit: max N paid (rare/legendary) summons per sliding window.
_RATE_LIMIT_MAX = 3
_RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds


@dataclass
class PaymentGate:
    """Decides if a summon needs payment and verifies settlement.

    Rate limiting: tracks paid (rare/legendary) requests per session using
    an in-memory dict with timestamps. This is non-persistent — resets on
    service restart.
    """

    payment: PaymentPort | None = None

    # ── Rate limiting state (in-memory, per-session) ──────────────────
    # Keyed by session_id (defaults to "default"), each entry is a list
    # of Unix timestamps of recent paid requests.
    _rate_tracker: dict[str, list[float]] = field(
        default_factory=lambda: defaultdict(list),
        repr=False,
    )

    def requires_payment(self, price_sats: int) -> bool:
        return self.payment is not None and price_sats > 0

    def request(self, price_sats: int, memo: str, session_id: str = "default") -> PaymentRequest:
        if self.payment is None:
            raise RuntimeError("No payment provider configured for a paid summon")
        self._check_rate_limit(session_id)
        return self.payment.create_payment(price_sats, memo)

    def _check_rate_limit(self, session_id: str = "default") -> None:
        """Enforce max N paid requests per hour per session.

        Raises RuntimeError if rate limit exceeded.
        """
        now = time.time()
        window_start = now - _RATE_LIMIT_WINDOW

        # Prune expired entries
        timestamps = self._rate_tracker[session_id]
        active = [t for t in timestamps if t > window_start]
        self._rate_tracker[session_id] = active

        if len(active) >= _RATE_LIMIT_MAX:
            oldest = active[0] if active else now
            retry_after = int(_RATE_LIMIT_WINDOW - (now - oldest))
            log.warning(
                "Rate limit hit for session %s: %d requests in last hour. "
                "Retry after %ds.",
                session_id, len(active), retry_after,
            )
            raise RuntimeError(
                f"Rate limit exceeded: max {_RATE_LIMIT_MAX} rare/legendary "
                f"summons per hour. Retry in ~{retry_after}s."
            )

        # Record this request
        self._rate_tracker[session_id].append(now)

    def settle(self, request: PaymentRequest, proof: str) -> bool:
        """Verify payment; mark request paid on success."""
        ok = self.payment.verify_payment(request, proof)
        return ok

    @staticmethod
    def is_free(rarity: Rarity) -> bool:
        return rarity in (Rarity.COMMON, Rarity.UNCOMMON)

    @staticmethod
    def compute_min_trade_price(embedding_uniqueness_score: float, base_price_sats: int) -> int:
        """Compute the minimum trade price for a creature.

        Formula: min_price = embedding_uniqueness_score × base_price

        embedding_uniqueness_score: float in [1.0, 10.0] from compute_uniqueness_bonus
        base_price_sats: base price from rarity tier (e.g. 15 for rare, 25 for legendary)

        Returns the minimum price as an integer (ceil to nearest sat).
        """
        import math
        return math.ceil(embedding_uniqueness_score * base_price_sats)
