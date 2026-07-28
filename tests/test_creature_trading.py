"""Tests for P3 M04 — creature trading: MINT → Nostr → trade.

Covers:
  - SqliteMemory trade methods (list, cancel, transfer, execute)
  - TradeOffer event format (kind 40000) on Nostr
  - Minimum price = embedding_uniqueness_score × base_price
  - Nostr publisher trade offer
  - Nostr reader trade offer parsing
  - JsonMemory trade edge cases
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from terramon.adapters.json_memory import SqliteMemory
from terramon.adapters.nostr_publisher import (
    NostrPublisher,
    build_trade_offer_event,
    build_event,
)
from terramon.adapters.nostr_reader import NostrRelayReader, TradeOffer
from terramon.application.payment_gate import PaymentGate
from terramon.domain.rarity import Rarity, RARITY_PRICE
from terramon.domain.thought_seed import ThoughtSeed


# ======================================================================
# SqliteMemory trade methods
# ======================================================================


class TestSqliteMemoryTrading:
    """Tests for SqliteMemory trade CRUD and ownership transfer."""

    @pytest.fixture
    def memory(self, tmp_path: Path) -> SqliteMemory:
        m = SqliteMemory(tmp_path / "test_trade.db")
        # Insert some test seeds with owner_id (persistence concern, not in domain model)
        for i, (agent, rarity) in enumerate([
            ("Hero", "rare"),
            ("Sage", "legendary"),
            ("Scout", "common"),
        ]):
            base_price = RARITY_PRICE.get(Rarity(rarity), 0)
            m._conn.execute(
                """INSERT INTO seeds (raw_input, summoned_agent, timestamp, status,
                   rarity, price_sats, paid, owner_id, for_trade, trade_price_sats)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (f"test thought {i}", agent, "2025-01-01T00:00:00", "summoned",
                 rarity, base_price, 1, "player", 0, 0),
            )
        m._conn.commit()
        return m

    def test_list_for_trade(self, memory: SqliteMemory):
        """List a creature for trade and verify it shows up in listings."""
        assert memory.list_for_trade(1, 50) is True
        listings = memory.get_trade_listings()
        assert len(listings) == 1
        assert listings[0]["id"] == 1
        assert listings[0]["trade_price_sats"] == 50
        assert listings[0]["for_trade"] == 1

    def test_list_for_trade_invalid_id(self, memory: SqliteMemory):
        """Listing a non-existent seed returns False."""
        assert memory.list_for_trade(999, 50) is False

    def test_cancel_trade(self, memory: SqliteMemory):
        """Cancel a trade listing removes it from listings."""
        memory.list_for_trade(1, 50)
        assert len(memory.get_trade_listings()) == 1
        assert memory.cancel_trade(1) is True
        assert len(memory.get_trade_listings()) == 0

    def test_cancel_trade_invalid_id(self, memory: SqliteMemory):
        """Cancelling a non-existent listing returns False."""
        assert memory.cancel_trade(999) is False

    def test_multiple_listings(self, memory: SqliteMemory):
        """Multiple creatures can be listed for trade simultaneously."""
        memory.list_for_trade(1, 100)
        memory.list_for_trade(2, 200)
        listings = memory.get_trade_listings()
        assert len(listings) == 2
        assert listings[0]["trade_price_sats"] == 100
        assert listings[1]["trade_price_sats"] == 200

    def test_get_trade_listings_empty(self, memory: SqliteMemory):
        """get_trade_listings returns empty list when nothing is for trade."""
        assert memory.get_trade_listings() == []

    def test_transfer_ownership(self, memory: SqliteMemory):
        """Transfer ownership changes owner_id and clears trade flags."""
        memory.list_for_trade(1, 50)
        assert memory.transfer_ownership(1, "buyer_123") is True
        rows = memory._conn.execute(
            "SELECT owner_id, for_trade, trade_price_sats FROM seeds WHERE id = 1"
        ).fetchall()
        row = dict(rows[0])
        assert row["owner_id"] == "buyer_123"
        assert row["for_trade"] == 0
        assert row["trade_price_sats"] == 0

    def test_transfer_ownership_invalid_id(self, memory: SqliteMemory):
        """Transferring a non-existent seed returns False."""
        assert memory.transfer_ownership(999, "buyer") is False

    def test_execute_trade_success(self, memory: SqliteMemory):
        """Full trade flow: list -> execute -> ownership transferred."""
        memory.list_for_trade(1, 50)
        assert memory.execute_trade(1, "player", "buyer_456", 50) is True
        rows = memory._conn.execute(
            "SELECT owner_id, for_trade FROM seeds WHERE id = 1"
        ).fetchall()
        row = dict(rows[0])
        assert row["owner_id"] == "buyer_456"
        assert row["for_trade"] == 0

    def test_execute_trade_wrong_seller(self, memory: SqliteMemory):
        """Trade fails if the seller doesn't match."""
        memory.list_for_trade(1, 50)
        assert memory.execute_trade(1, "wrong_seller", "buyer", 50) is False

    def test_execute_trade_wrong_price(self, memory: SqliteMemory):
        """Trade fails if the price doesn't match."""
        memory.list_for_trade(1, 50)
        assert memory.execute_trade(1, "player", "buyer", 99) is False

    def test_execute_trade_not_listed(self, memory: SqliteMemory):
        """Trade fails if the creature is not listed for trade."""
        assert memory.execute_trade(1, "player", "buyer", 50) is False

    def test_execute_trade_already_sold(self, memory: SqliteMemory):
        """Once traded, the creature can't be traded again without re-listing."""
        memory.list_for_trade(1, 50)
        assert memory.execute_trade(1, "player", "buyer", 50) is True
        assert memory.execute_trade(1, "buyer", "third_party", 50) is False

    def test_execute_trade_updates_listings(self, memory: SqliteMemory):
        """After executing a trade, the creature is removed from listings."""
        memory.list_for_trade(1, 50)
        memory.list_for_trade(2, 100)
        assert len(memory.get_trade_listings()) == 2
        memory.execute_trade(1, "player", "buyer", 50)
        listings = memory.get_trade_listings()
        assert len(listings) == 1
        assert listings[0]["id"] == 2

    def test_list_for_trade_zero_price(self, memory: SqliteMemory):
        """A creature can be listed for trade at 0 sats (free transfer)."""
        assert memory.list_for_trade(1, 0) is True
        listings = memory.get_trade_listings()
        assert len(listings) == 1
        assert listings[0]["trade_price_sats"] == 0


# ======================================================================
# TradeOffer Nostr event (kind 40000)
# ======================================================================


class TestTradeOfferNostrEvent:
    """Tests for TradeOffer Nostr event format (kind 40000)."""

    SECKEY = "0000000000000000000000000000000000000000000000000000000000000003"
    CREATURE_ID = "hero-001"
    AGENT = "Hero"
    RARITY = "rare"
    THOUGHT = "test thought"
    PRICE = 50

    def test_trade_offer_event_kind(self):
        """TradeOffer event must be kind 40000."""
        ev = build_trade_offer_event(
            self.SECKEY, self.CREATURE_ID, self.AGENT,
            self.RARITY, self.THOUGHT, self.PRICE,
        )
        assert ev["kind"] == 40000

    def test_trade_offer_event_has_correct_tags(self):
        """TradeOffer event must carry identifier, agent, rarity, price tags."""
        ev = build_trade_offer_event(
            self.SECKEY, self.CREATURE_ID, self.AGENT,
            self.RARITY, self.THOUGHT, self.PRICE,
        )
        tags = ev["tags"]
        tag_dict = {t[0]: t[1] for t in tags if len(t) >= 2}
        assert tag_dict["d"] == self.CREATURE_ID
        assert tag_dict["agent"] == self.AGENT
        assert tag_dict["rarity"] == self.RARITY
        assert tag_dict["price"] == str(self.PRICE)

    def test_trade_offer_event_has_discovery_tags(self):
        """TradeOffer event must include terramon and trade-offer tags."""
        ev = build_trade_offer_event(
            self.SECKEY, self.CREATURE_ID, self.AGENT,
            self.RARITY, self.THOUGHT, self.PRICE,
        )
        t_tags = [t[1] for t in ev["tags"] if t[0] == "t"]
        assert "terramon" in t_tags
        assert "trade-offer" in t_tags

    def test_trade_offer_event_is_valid_signed_event(self):
        """TradeOffer event must be a validly signed Nostr event."""
        ev = build_trade_offer_event(
            self.SECKEY, self.CREATURE_ID, self.AGENT,
            self.RARITY, self.THOUGHT, self.PRICE,
        )
        assert "id" in ev
        assert "pubkey" in ev
        assert "created_at" in ev
        assert "sig" in ev
        assert "content" in ev
        assert len(ev["sig"]) == 128
        assert len(ev["pubkey"]) == 64
        assert len(ev["id"]) == 64

    def test_trade_offer_content_format(self):
        """TradeOffer content should describe the creature and price."""
        ev = build_trade_offer_event(
            self.SECKEY, self.CREATURE_ID, self.AGENT,
            self.RARITY, self.THOUGHT, self.PRICE,
        )
        assert self.AGENT in ev["content"]
        assert self.RARITY.upper() in ev["content"]
        assert str(self.PRICE) in ev["content"]

    def test_trade_offer_event_reproducible_with_created_at(self):
        """TradeOffer event with explicit created_at is deterministic."""
        ev1 = build_trade_offer_event(
            self.SECKEY, self.CREATURE_ID, self.AGENT,
            self.RARITY, self.THOUGHT, self.PRICE,
            created_at=1700000000,
        )
        ev2 = build_trade_offer_event(
            self.SECKEY, self.CREATURE_ID, self.AGENT,
            self.RARITY, self.THOUGHT, self.PRICE,
            created_at=1700000000,
        )
        assert ev1["id"] == ev2["id"]
        assert ev1["sig"] == ev2["sig"]

    def test_different_creatures_have_different_event_ids(self):
        """Different creature data produces different event IDs."""
        ev1 = build_trade_offer_event(
            self.SECKEY, "hero-001", "Hero",
            "rare", "thought A", 50, created_at=1700000000,
        )
        ev2 = build_trade_offer_event(
            self.SECKEY, "sage-002", "Sage",
            "legendary", "thought B", 100, created_at=1700000000,
        )
        assert ev1["id"] != ev2["id"]


class TestNostrPublisherTradeOffer:
    """Tests for NostrPublisher.publish_trade_offer."""

    def test_publish_trade_offer_offline(self):
        """Publish trade offer offline with fake sender records correct data."""
        sent = []

        def fake_sender(relay, frame):
            sent.append((relay, frame))

        pub = NostrPublisher(
            seckey_hex="0000000000000000000000000000000000000000000000000000000000000003",
            relays=["wss://trade.relay"],
            sender=fake_sender,
        )
        result = pub.publish_trade_offer(
            creature_id="hero-001",
            agent_name="Hero",
            rarity="rare",
            thought="test thought",
            price_sats=50,
        )
        assert result.ok
        assert len(sent) == 1
        frame_data = json.loads(sent[0][1])
        assert frame_data[0] == "EVENT"
        assert frame_data[1]["kind"] == 40000
        assert frame_data[1]["tags"][0][1] == "hero-001"

    def test_publish_trade_offer_no_key_raises(self):
        """Publishing a trade offer without a key raises RuntimeError."""
        pub = NostrPublisher(seckey_hex="", sender=lambda r, f: None)
        with pytest.raises(RuntimeError):
            pub.publish_trade_offer(
                creature_id="x", agent_name="Hero",
                rarity="rare", thought="x", price_sats=10,
            )


# ======================================================================
# Nostr reader trade offer parsing
# ======================================================================


class TestNostrReaderTradeOfferParsing:
    """Tests for NostrRelayReader._parse_trade_offer."""

    @staticmethod
    def _make_kind_40000_event(
        creature_id: str, agent: str = "Hero",
        rarity: str = "rare", price: int = 50,
    ) -> dict:
        return {
            "id": f"trade_{creature_id}",
            "pubkey": "abc123",
            "created_at": int(time.time()),
            "kind": 40000,
            "tags": [
                ["d", creature_id],
                ["agent", agent],
                ["rarity", rarity],
                ["price", str(price)],
                ["t", "terramon"],
                ["t", "trade-offer"],
            ],
            "content": f"{rarity.upper()} -- {agent}: \"thought\" -- {price} sats",
            "sig": "00" * 64,
        }

    def test_parse_valid_trade_offer(self):
        """Parse a well-formed kind 40000 event into a TradeOffer."""
        ev = self._make_kind_40000_event("hero-001")
        offer = NostrRelayReader._parse_trade_offer(ev)
        assert offer is not None
        assert isinstance(offer, TradeOffer)
        assert offer.creature_id == "hero-001"
        assert offer.agent_name == "Hero"
        assert offer.rarity == "rare"
        assert offer.price_sats == 50
        assert offer.event_id == "trade_hero-001"

    def test_parse_trade_offer_missing_d_tag(self):
        """A kind 40000 event without a 'd' tag returns None."""
        ev = self._make_kind_40000_event("hero-001")
        ev["tags"] = [t for t in ev["tags"] if t[0] != "d"]
        offer = NostrRelayReader._parse_trade_offer(ev)
        assert offer is None

    def test_parse_trade_offer_invalid_price(self):
        """Invalid price in tag gracefully defaults to 0."""
        ev = self._make_kind_40000_event("hero-001", price=50)
        for i, tag in enumerate(ev["tags"]):
            if tag[0] == "price":
                ev["tags"][i] = ["price", "not-a-number"]
                break
        offer = NostrRelayReader._parse_trade_offer(ev)
        assert offer is not None
        assert offer.price_sats == 0

    def test_parse_trade_offer_missing_price_tag(self):
        """Missing price tag defaults to 0."""
        ev = self._make_kind_40000_event("hero-001")
        ev["tags"] = [t for t in ev["tags"] if t[0] != "price"]
        offer = NostrRelayReader._parse_trade_offer(ev)
        assert offer is not None
        assert offer.price_sats == 0


# ======================================================================
# Minimum price formula
# ======================================================================


class TestMinTradePrice:
    """Tests for minimum trade price = embedding_uniqueness_score x base_price."""

    def test_min_price_with_uniqueness_1x(self):
        """Minimum uniqueness (1.0) gives base price."""
        assert PaymentGate.compute_min_trade_price(1.0, 15) == 15

    def test_min_price_with_high_uniqueness(self):
        """High uniqueness (10.0) gives 10x base price."""
        assert PaymentGate.compute_min_trade_price(10.0, 15) == 150

    def test_min_price_with_mid_uniqueness(self):
        """Mid-range uniqueness (5.5) gives 5.5x base price (ceil)."""
        assert PaymentGate.compute_min_trade_price(5.5, 15) == 83

    def test_min_price_rare_base(self):
        """Rare base price of 15 Stars."""
        assert PaymentGate.compute_min_trade_price(2.0, 15) == 30

    def test_min_price_legendary_base(self):
        """Legendary base price of 25 Stars."""
        assert PaymentGate.compute_min_trade_price(2.0, 25) == 50

    def test_min_price_common_base(self):
        """Common base price of 0 -- min price is 0."""
        assert PaymentGate.compute_min_trade_price(5.0, 0) == 0

    def test_min_price_zero_uniqueness(self):
        """Zero uniqueness score (edge case) gives 0."""
        assert PaymentGate.compute_min_trade_price(0.0, 15) == 0

    def test_min_price_small_values(self):
        """Small uniqueness and base price values."""
        assert PaymentGate.compute_min_trade_price(1.0, 1) == 1

    def test_min_price_large_values(self):
        """Large uniqueness and base price values."""
        assert PaymentGate.compute_min_trade_price(10.0, 1000) == 10000


# ======================================================================
# End-to-end trade scenarios
# ======================================================================


class TestEndToEndTrading:
    """End-to-end trade flows using SqliteMemory."""

    def test_seller_lists_and_buys_trade(self, tmp_path: Path):
        """Full happy path: seller lists creature, buyer trades for it."""
        memory = SqliteMemory(tmp_path / "e2e.db")
        memory._conn.execute(
            """INSERT INTO seeds (raw_input, summoned_agent, timestamp, status,
               rarity, price_sats, paid, owner_id, for_trade, trade_price_sats)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("e2e test", "Hero", "2025-01-01T00:00:00", "summoned",
             "rare", 15, 1, "seller_1", 0, 0),
        )
        memory._conn.commit()

        assert memory.list_for_trade(1, 50) is True
        listings = memory.get_trade_listings()
        assert len(listings) == 1
        assert listings[0]["owner_id"] == "seller_1"

        assert memory.execute_trade(1, "seller_1", "buyer_2", 50) is True
        rows = memory._conn.execute(
            "SELECT owner_id FROM seeds WHERE id = 1"
        ).fetchall()
        assert dict(rows[0])["owner_id"] == "buyer_2"

    def test_multiple_creatures_trade_independently(self, tmp_path: Path):
        """Multiple creatures can be listed and traded independently."""
        memory = SqliteMemory(tmp_path / "multi.db")
        for i, (agent, rarity) in enumerate([
            ("Hero", "rare"), ("Sage", "rare"), ("Scout", "common"),
        ]):
            memory._conn.execute(
                """INSERT INTO seeds (raw_input, summoned_agent, timestamp, status,
                   rarity, price_sats, paid, owner_id, for_trade, trade_price_sats)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (f"multi {i}", agent, "2025-01-01T00:00:00", "summoned",
                 rarity, 15 if rarity == "rare" else 0, 1, "alice", 0, 0),
            )
        memory._conn.commit()

        assert memory.list_for_trade(1, 100) is True
        assert memory.list_for_trade(2, 200) is True
        assert memory.execute_trade(1, "alice", "bob", 100) is True

        listings = memory.get_trade_listings()
        assert len(listings) == 1
        assert listings[0]["id"] == 2
        assert listings[0]["owner_id"] == "alice"

        rows = memory._conn.execute(
            "SELECT owner_id FROM seeds WHERE id = 1"
        ).fetchall()
        assert dict(rows[0])["owner_id"] == "bob"
