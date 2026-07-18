"""Tests for the payment port, adapters, rarity, and gating logic.

All payment tests are OFFLINE: HTTP/lookup layers are injected with fakes.
The three original summon tests must still pass (payment=None -> free).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from terramon.adapters.json_memory import JsonMemory
from terramon.adapters.keyword_classifier import KeywordClassifier
from terramon.adapters.lightning_adapter import LightningAdapter
from terramon.adapters.onchain_adapter import OnChainAdapter
from terramon.adapters.stripe_adapter import StripeAdapter
from terramon.application.summon_service import SummonService
from terramon.application.payment_gate import PaymentGate
from terramon.domain.rarity import classify_rarity, Rarity
from terramon.events.agent_summoned import AgentSummoned
from terramon.events.bus import EventBus
from terramon.ports.payment_port import PaymentMethod, PaymentRequest


# --------------------------------------------------------------------------- #
# Original contract preserved (payment=None keeps everything free)
# --------------------------------------------------------------------------- #
def test_summon_routes_to_ranger(tmp_path: Path) -> None:
    memory = JsonMemory(tmp_path / "memory.jsonl")
    bus = EventBus()
    service = SummonService(KeywordClassifier(), memory, bus, lambda: "now")
    seed = service.summon("scan the north district")
    assert seed.summoned_agent == "Ranger"
    assert seed.status == "summoned"
    assert memory.load_all_seeds() == [seed]


def test_summon_emits_event(tmp_path: Path) -> None:
    memory = JsonMemory(tmp_path / "memory.jsonl")
    bus = EventBus()
    received: list[AgentSummoned] = []
    bus.subscribe(AgentSummoned, received.append)
    service = SummonService(KeywordClassifier(), memory, bus, lambda: "now")
    service.summon("log the history of this place")
    assert len(received) == 1
    assert received[0].agent_name == "Archivist"


def test_summon_defaults_to_scout(tmp_path: Path) -> None:
    memory = JsonMemory(tmp_path / "memory.jsonl")
    bus = EventBus()
    service = SummonService(KeywordClassifier(), memory, bus, lambda: "now")
    seed = service.summon("hello world")
    assert seed.summoned_agent == "Scout"


# --------------------------------------------------------------------------- #
# Rarity
# --------------------------------------------------------------------------- #
def test_common_by_default() -> None:
    r = classify_rarity("scan the ridge")
    assert r.rarity is Rarity.COMMON
    assert r.price_sats == 0


def test_rare_pattern_costs_sats() -> None:
    r = classify_rarity("I feel lost tonight")
    assert r.rarity is Rarity.RARE
    assert r.price_sats == 1000


def test_legendary_pattern() -> None:
    r = classify_rarity("i surrender to the void")
    assert r.rarity is Rarity.LEGENDARY
    assert r.price_sats == 5000


# --------------------------------------------------------------------------- #
# On-chain adapter (watch-only, public address, offline lookup)
# --------------------------------------------------------------------------- #
def _fake_onchain_lookup(address: str) -> list[dict]:
    return [{
        "txid": "abc123",
        "vout": [{"scriptpubkey_address": address, "value": 1200}],
    }]


def test_onchain_create_request_uses_treasury() -> None:
    adapter = OnChainAdapter(address="bc1q5am2mqlnzymv6q3sc5neu0s6ladz8pe588l3nh")
    req = adapter.create_payment(1000, "rare summon")
    assert req.method is PaymentMethod.ONCHAIN
    assert req.destination.startswith("bc1q")
    assert req.amount_sats == 1000


def test_onchain_verify_with_proof() -> None:
    adapter = OnChainAdapter(
        address="bc1q5am2mqlnzymv6q3sc5neu0s6ladz8pe588l3nh",
        lookup_txs=_fake_onchain_lookup,
    )
    req = adapter.create_payment(1000, "rare summon")
    assert adapter.verify_payment(req, "abc123") is True
    assert req.status == "paid"


def test_onchain_rejects_insufficient() -> None:
    def lookup_low(address: str) -> list[dict]:
        return [{"txid": "x", "vout": [{"scriptpubkey_address": address, "value": 500}]}]
    adapter = OnChainAdapter(
        address="bc1q5am2mqlnzymv6q3sc5neu0s6ladz8pe588l3nh",
        lookup_txs=lookup_low,
    )
    req = adapter.create_payment(1000, "rare summon")
    assert adapter.verify_payment(req, "x") is False


# --------------------------------------------------------------------------- #
# Lightning adapter (LNBits, injected fake http)
# --------------------------------------------------------------------------- #
def _fake_ln_http(method: str, url: str, body, headers: dict) -> dict:
    if method == "POST":
        return {"checking_id": "lncheck1", "payment_request": "lnbc1u1p..."}
    return {"paid": True}


def test_lightning_create_and_verify() -> None:
    adapter = LightningAdapter(url="https://ln.example", api_key="k", http=_fake_ln_http)
    req = adapter.create_payment(1000, "rare")
    assert req.method is PaymentMethod.LIGHTNING
    assert req.destination.startswith("lnbc")
    assert adapter.verify_payment(req) is True


# --------------------------------------------------------------------------- #
# Stripe adapter (injected fake http)
# --------------------------------------------------------------------------- #
def _fake_stripe_http(method: str, url: str, body, headers: dict) -> dict:
    if method == "POST":
        return {"id": "cs_1", "url": "https://checkout.stripe.com/c/cs_1"}
    return {"status": "complete"}


def test_stripe_create_and_verify() -> None:
    adapter = StripeAdapter(api_key="sk", price_id="price_x", http=_fake_stripe_http)
    req = adapter.create_payment(0, "SUMMONER monthly")
    assert req.method is PaymentMethod.STRIPE
    assert "checkout.stripe.com" in req.destination
    assert adapter.verify_payment(req) is True


# --------------------------------------------------------------------------- #
# Payment gate + paid summon through SummonService
# --------------------------------------------------------------------------- #
def test_free_summon_never_requires_payment(tmp_path: Path) -> None:
    memory = JsonMemory(tmp_path / "memory.jsonl")
    bus = EventBus()
    # On-chain adapter as the provider, but the thought is common -> no charge.
    adapter = OnChainAdapter(
        address="bc1q5am2mqlnzymv6q3sc5neu0s6ladz8pe588l3nh",
        lookup_txs=_fake_onchain_lookup,
    )
    service = SummonService(KeywordClassifier(), memory, bus, lambda: "now", payment=adapter)
    seed = service.summon("scan the ridge")
    assert seed.paid is True  # common = free = auto-paid
    assert seed.price_sats == 0


def test_paid_summon_flow(tmp_path: Path) -> None:
    memory = JsonMemory(tmp_path / "memory.jsonl")
    bus = EventBus()
    adapter = OnChainAdapter(
        address="bc1q5am2mqlnzymv6q3sc5neu0s6ladz8pe588l3nh",
        lookup_txs=_fake_onchain_lookup,
    )
    service = SummonService(KeywordClassifier(), memory, bus, lambda: "now", payment=adapter)
    seed = service.summon_paid("I feel lost tonight", "abc123")
    assert seed.rarity == "rare"
    assert seed.paid is True
    assert seed.price_sats == 1000


def test_paid_summon_rejects_bad_proof(tmp_path: Path) -> None:
    memory = JsonMemory(tmp_path / "memory.jsonl")
    bus = EventBus()
    adapter = OnChainAdapter(
        address="bc1q5am2mqlnzymv6q3sc5neu0s6ladz8pe588l3nh",
        lookup_txs=_fake_onchain_lookup,
    )
    service = SummonService(KeywordClassifier(), memory, bus, lambda: "now", payment=adapter)
    with pytest.raises(RuntimeError):
        service.summon_paid("I feel lost tonight", "wrongtx")
