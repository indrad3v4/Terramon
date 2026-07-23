"""Eval tests for Nostr publisher — proves real BIP-340 crypto, offline.

Each test = one failure mode:
  - crypto is fake -> BIP-340 official test vector MUST pass
  - event id wrong -> recompute sha256 of serialization
  - publish not isolated -> offline fake sender, no network
"""

from terramon.adapters.nostr_publisher import (
    build_event,
    pubkey_hex,
    schnorr_sign,
)
from terramon.adapters.nostr_publisher import NostrPublisher
from terramon.ports.publish_port import ShareCard


def test_bip340_official_vector():
    """BIP-340 test vector #0 — the ground truth for Schnorr signing."""
    seckey = 0x0000000000000000000000000000000000000000000000000000000000000003
    aux = bytes.fromhex(
        "0000000000000000000000000000000000000000000000000000000000000000"
    )
    msg = bytes.fromhex(
        "0000000000000000000000000000000000000000000000000000000000000000"
    )
    expected_pub = "F9308A019258C31049344F85F89D5229B531C845836F99B08601F113BCE036F9"
    expected_sig = (
        "E907831F80848D1069A5371B402410364BDF1C5F8307B0084C55F1CE2DCA8215"
        "25F66A4A85EA8B71E482A74F382D2CE5EBEEE8FDB2172F477DF4900D310536C0"
    )
    assert pubkey_hex(seckey).upper() == expected_pub
    sig = schnorr_sign(msg, seckey, aux)
    assert sig.hex().upper() == expected_sig


def test_event_id_is_sha256_of_serialization():
    import hashlib
    import json

    sk = "0000000000000000000000000000000000000000000000000000000000000003"
    ev = build_event(sk, "hello terra", [["t", "terramon"]], created_at=1700000000)
    serialized = json.dumps(
        [0, ev["pubkey"], ev["created_at"], ev["kind"], ev["tags"], ev["content"]],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    assert ev["id"] == hashlib.sha256(serialized.encode()).hexdigest()
    assert len(ev["sig"]) == 128  # 64 bytes hex


def test_share_card_note_render():
    card = ShareCard(
        thought="i'm afraid of the interview",
        agent="Courage",
        rarity="legendary",
        lore="Born shaking. Came anyway.",
    )
    note = card.to_note()
    assert "LEGENDARY" in note
    assert "Courage" in note
    assert "i'm afraid" in note
    assert "#terramon" in note


def test_publish_offline_with_fake_sender():
    sent = []

    def fake_sender(relay, frame):
        sent.append((relay, frame))

    pub = NostrPublisher(
        seckey_hex="0000000000000000000000000000000000000000000000000000000000000003",
        relays=["wss://a.relay", "wss://b.relay"],
        sender=fake_sender,
    )
    card = ShareCard(thought="calm morning", agent="Wanderer", rarity="common")
    result = pub.publish(card)
    assert result.ok
    assert len(result.relays_ok) == 2
    assert len(sent) == 2
    assert '"EVENT"' in sent[0][1]


def test_publish_records_relay_failures():
    def flaky_sender(relay, frame):
        if "bad" in relay:
            raise ConnectionError("relay down")

    pub = NostrPublisher(
        seckey_hex="0000000000000000000000000000000000000000000000000000000000000003",
        relays=["wss://good.relay", "wss://bad.relay"],
        sender=flaky_sender,
    )
    result = pub.publish(ShareCard(thought="x", agent="Innocent", rarity="common"))
    assert result.relays_ok == ["wss://good.relay"]
    assert result.relays_failed == ["wss://bad.relay"]


def test_missing_key_raises():
    import pytest

    pub = NostrPublisher(seckey_hex="", sender=lambda r, f: None)
    with pytest.raises(RuntimeError):
        pub.publish(ShareCard(thought="x", agent="Innocent", rarity="common"))
