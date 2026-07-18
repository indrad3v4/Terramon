"""Payment gate — wires SummonService to the PaymentPort.

Build-via-learn: Phase 14 (Agent Engineering) -> "verification gates". A paid
summon is a verification gate: the creature is only released once payment
verifies. The gate depends on PaymentPort, so Lightning / on-chain / Stripe are
all interchangeable.

The gate is OPTIONAL: pass `payment=None` and every summon is free (keeps the
existing 3 tests green and the Day 1-3 CLI working).
"""

from __future__ import annotations

from terramon.domain.rarity import Rarity
from terramon.ports.payment_port import PaymentPort, PaymentRequest


class PaymentGate:
    """Decides if a summon needs payment and verifies settlement."""

    def __init__(self, payment: PaymentPort | None = None) -> None:
        self.payment = payment

    def requires_payment(self, price_sats: int) -> bool:
        return self.payment is not None and price_sats > 0

    def request(self, price_sats: int, memo: str) -> PaymentRequest:
        if self.payment is None:
            raise RuntimeError("No payment provider configured for a paid summon")
        return self.payment.create_payment(price_sats, memo)

    def settle(self, request: PaymentRequest, proof: str) -> bool:
        """Verify payment; mark request paid on success."""
        ok = self.payment.verify_payment(request, proof)
        return ok

    @staticmethod
    def is_free(rarity: Rarity) -> bool:
        return rarity in (Rarity.COMMON, Rarity.UNCOMMON)
