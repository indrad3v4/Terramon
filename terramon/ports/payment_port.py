"""Payment port — how Terramon charges for rare summons.

Build-via-learn mapping (from AI Engineering from Scratch, cloned locally):
- Phase 13 (Tools & Protocols): a port IS a tool interface; adapters are the
  concrete tool implementations. Swap Lightning <-> Stripe <-> on-chain without
  touching game logic.
- Phase 11 (LLM Engineering / cost): payments are the "cost governor" for
  scarce in-game resources (rare creatures).
- Phase 17 (Infrastructure): money movement is a production cross-cutting
  concern, isolated behind a port so the rest of the engine stays pure.

This mirrors the repo's ClassifierPort / MemoryPort design exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class PaymentMethod(str, Enum):
    """Where the sats / euros actually move."""

    ONCHAIN = "onchain"      # bc1q… direct Bitcoin transaction (watch-only)
    LIGHTNING = "lightning"  # BOLT11 invoice, instant sats
    STRIPE = "stripe"        # EUR subscription (fiat, NOT bitcoin)


@dataclass
class PaymentRequest:
    """A concrete charge the player must settle to unlock a rare summon.

    `destination` means different things per method:
      - onchain:   the bc1q… receiving address
      - lightning: the BOLT11 invoice string
      - stripe:    the hosted Checkout URL
    """

    id: str
    method: PaymentMethod
    amount_sats: int
    destination: str
    memo: str
    fiat_hint: str = ""
    status: str = "pending"   # pending | paid | expired
    verification_ref: str = ""  # txid / checking_id / session id


class PaymentPort(Protocol):
    """Secondary port: a pluggable payment provider.

    Any adapter that implements create_payment + verify_payment satisfies this
    port. The SummonService depends on the port, never on a concrete provider.
    """

    def create_payment(self, amount_sats: int, memo: str) -> PaymentRequest:
        """Create a charge and return how the player pays."""
        ...

    def verify_payment(self, request: PaymentRequest, proof: str) -> bool:
        """Return True if `proof` shows `request` was settled."""
        ...
