"""Nostr publisher adapter — real BIP-340 Schnorr signing, stdlib only.

Implements PublishPort by turning a ShareCard into a signed Nostr event
(kind 1 text note) and broadcasting it to relays over WebSocket.

Why from scratch (no deps): the whole Terramon repo is stdlib-first, and Nostr
is simple enough to build honestly:
  - event id   = sha256(serialize([0, pubkey, created_at, kind, tags, content]))
  - signature  = BIP-340 Schnorr over secp256k1 of that id
  - broadcast  = ["EVENT", <event>] JSON frame to each relay

Build-via-learn: Phase 1 (number theory / modular arithmetic -> finite field
secp256k1), Phase 13 (protocols -> Nostr wire format). This is the cryptography
lesson made concrete: you sign your own thought-creature and no one can forge it.

The WebSocket send is injectable so tests run fully offline.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass

from terramon.ports.publish_port import PublishPort, PublishResult, ShareCard

# ----------------------------------------------------------------------------
# secp256k1 field + curve constants
# ----------------------------------------------------------------------------
_P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_GX = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
_GY = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8


def _mod_inv(a: int, m: int) -> int:
    return pow(a, m - 2, m)


def _point_add(p1, p2):
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2 and (y1 + y2) % _P == 0:
        return None
    if p1 == p2:
        lam = (3 * x1 * x1) * _mod_inv(2 * y1, _P) % _P
    else:
        lam = (y2 - y1) * _mod_inv((x2 - x1) % _P, _P) % _P
    x3 = (lam * lam - x1 - x2) % _P
    y3 = (lam * (x1 - x3) - y1) % _P
    return (x3, y3)


def _point_mul(k: int, point):
    result = None
    addend = point
    while k:
        if k & 1:
            result = _point_add(result, addend)
        addend = _point_add(addend, addend)
        k >>= 1
    return result


def _lift_x(x: int):
    """Recover the even-y point from an x-only pubkey (BIP-340)."""
    y_sq = (pow(x, 3, _P) + 7) % _P
    y = pow(y_sq, (_P + 1) // 4, _P)
    if (y * y) % _P != y_sq:
        raise ValueError("x is not on the curve")
    return (x, y if y % 2 == 0 else _P - y)


def _tagged_hash(tag: str, msg: bytes) -> bytes:
    tag_hash = hashlib.sha256(tag.encode()).digest()
    return hashlib.sha256(tag_hash + tag_hash + msg).digest()


def _bytes(x: int) -> bytes:
    return x.to_bytes(32, "big")


def schnorr_sign(msg32: bytes, seckey: int, aux_rand: bytes) -> bytes:
    """BIP-340 Schnorr signature over the 32-byte message hash."""
    if not (1 <= seckey < _N):
        raise ValueError("secret key out of range")
    P = _point_mul(seckey, (_GX, _GY))
    d = seckey if P[1] % 2 == 0 else _N - seckey
    t = d ^ int.from_bytes(_tagged_hash("BIP0340/aux", aux_rand), "big")
    rand = _tagged_hash("BIP0340/nonce", _bytes(t) + _bytes(P[0]) + msg32)
    k0 = int.from_bytes(rand, "big") % _N
    if k0 == 0:
        raise ValueError("nonce is zero")
    R = _point_mul(k0, (_GX, _GY))
    k = k0 if R[1] % 2 == 0 else _N - k0
    e = int.from_bytes(
        _tagged_hash("BIP0340/challenge", _bytes(R[0]) + _bytes(P[0]) + msg32), "big"
    ) % _N
    sig = _bytes(R[0]) + _bytes((k + e * d) % _N)
    return sig


def pubkey_hex(seckey: int) -> str:
    """x-only public key hex (Nostr npub is bech32 of this)."""
    P = _point_mul(seckey, (_GX, _GY))
    return _bytes(P[0]).hex()


# ----------------------------------------------------------------------------
# Nostr event
# ----------------------------------------------------------------------------
def build_event(seckey_hex: str, content: str, tags: list[list[str]], kind: int = 1,
                created_at: int | None = None, aux_rand: bytes | None = None) -> dict:
    """Create a fully signed Nostr event ready to broadcast."""
    seckey = int(seckey_hex, 16)
    pub = pubkey_hex(seckey)
    ts = created_at if created_at is not None else int(time.time())
    serialized = json.dumps(
        [0, pub, ts, kind, tags, content], separators=(",", ":"), ensure_ascii=False
    )
    eid = hashlib.sha256(serialized.encode()).hexdigest()
    sig = schnorr_sign(bytes.fromhex(eid), seckey, aux_rand or (b"\x00" * 32))
    return {
        "id": eid,
        "pubkey": pub,
        "created_at": ts,
        "kind": kind,
        "tags": tags,
        "content": content,
        "sig": sig.hex(),
    }


DEFAULT_RELAYS = [
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://relay.nostr.band",
]


class NostrPublisher(PublishPort):
    """Publishes a creature card as a signed Nostr note.

    seckey_hex: 32-byte hex private key (env NOSTR_SECKEY). Generate once and
    keep it — it IS your Nostr identity. Never commit it.
    """

    def __init__(self, seckey_hex: str | None = None, relays: list[str] | None = None,
                 sender=None) -> None:
        self.seckey_hex = seckey_hex or os.getenv("NOSTR_SECKEY", "")
        self.relays = relays or DEFAULT_RELAYS
        self._send = sender or _websocket_send

    def publish(self, card: ShareCard) -> PublishResult:
        if not self.seckey_hex:
            raise RuntimeError("Nostr not configured: set NOSTR_SECKEY (32-byte hex)")
        tags = [["t", t] for t in card.tags]
        event = build_event(self.seckey_hex, card.to_note(), tags)
        frame = json.dumps(["EVENT", event], ensure_ascii=False)
        ok, failed = [], []
        for relay in self.relays:
            try:
                self._send(relay, frame)
                ok.append(relay)
            except Exception:
                failed.append(relay)
        return PublishResult(event_id=event["id"], relays_ok=ok, relays_failed=failed)


def _websocket_send(relay: str, frame: str) -> None:
    """Minimal WebSocket client send (stdlib socket + RFC6455 handshake)."""
    import base64
    import os as _os
    import socket
    import ssl
    from urllib.parse import urlparse

    u = urlparse(relay)
    host = u.hostname
    port = u.port or (443 if u.scheme == "wss" else 80)
    path = u.path or "/"
    key = base64.b64encode(_os.urandom(16)).decode()
    handshake = (
        f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\n"
        f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n\r\n"
    )
    sock = socket.create_connection((host, port), timeout=10)
    if u.scheme == "wss":
        sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
    sock.sendall(handshake.encode())
    sock.recv(4096)  # read handshake response
    payload = frame.encode()
    header = bytearray([0x81])  # FIN + text frame
    mask = _os.urandom(4)
    n = len(payload)
    if n < 126:
        header.append(0x80 | n)
    elif n < 65536:
        header.append(0x80 | 126)
        header += n.to_bytes(2, "big")
    else:
        header.append(0x80 | 127)
        header += n.to_bytes(8, "big")
    header += mask
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    sock.sendall(bytes(header) + masked)
    sock.close()
