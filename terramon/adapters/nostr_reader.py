"""Nostr relay reader — reads creature events from relays to build the global map.

I11: Each MINT event carries a "g" tag with lat/lon. This adapter queries
relays for recent terramon-tagged events and returns structured creature
locations so the TMA can render a global heatmap.

Build-via-learn mapping:
- Phase 13 (Protocols): Nostr REQ messages use the same JSON wire format as
  EVENT. This reader issues a REQ for kind 1 events with tag "t" = "terramon",
  parses the "g" geo tags, and returns CreatureLocation records.
"""

from __future__ import annotations

import json
import logging
import socket
import ssl
import base64
import os as _os
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

log = logging.getLogger("terramon.nostr_reader")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class CreatureLocation:
    """A creature located on the global map, read from a Nostr relay.

    Carries everything the TMA needs to render a marker + popup.
    """

    event_id: str
    pubkey: str
    lat: float
    lon: float
    agent: str = ""
    thought: str = ""
    rarity: str = "common"
    timestamp: int = 0

    @property
    def region_key(self) -> str:
        """Rough 5-degree grid cell for heatmap binning, e.g. '45_20'."""
        grid_lat = int(self.lat // 5) * 5
        grid_lon = int(self.lon // 5) * 5
        return f"{grid_lat}_{grid_lon}"


@dataclass
class TradeOffer:
    """A trade offer read from a Nostr relay (kind 40000 event)."""

    event_id: str
    pubkey: str
    creature_id: str
    agent_name: str
    rarity: str
    price_sats: int
    thought: str
    timestamp: int = 0


# ---------------------------------------------------------------------------
# Relay reader
# ---------------------------------------------------------------------------

DEFAULT_READ_RELAYS = [
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://relay.nostr.band",
]


class NostrRelayReader:
    """Reads creature events from Nostr relays to build the global map.

    Usage:
        reader = NostrRelayReader()
        creatures = reader.fetch_global_creatures(max_events=200)
        for c in creatures:
            print(c.lat, c.lon, c.agent)
    """

    def __init__(self, relays: list[str] | None = None, timeout: int = 5) -> None:
        self.relays = relays or DEFAULT_READ_RELAYS
        self.timeout = timeout

    # ── Public API ─────────────────────────────────────────────────────

    def fetch_global_creatures(self, max_events: int = 200) -> list[CreatureLocation]:
        """Fetch recent terramon creature events from all configured relays.

        Queries each relay with a REQ for kind-1 events tagged #terramon.
        Returns deduplicated CreatureLocation list sorted by timestamp desc.
        """
        all_creatures: dict[str, CreatureLocation] = {}
        for relay in self.relays:
            try:
                events = self._query_relay(relay, limit=min(max_events, 100))
                for ev in events:
                    loc = self._parse_event(ev)
                    if loc and loc.event_id not in all_creatures:
                        all_creatures[loc.event_id] = loc
            except Exception as exc:
                log.warning("Relay %s failed: %s", relay, exc)

        result = sorted(all_creatures.values(), key=lambda c: c.timestamp, reverse=True)
        return result[:max_events]

    def fetch_region_creatures(
        self, lat: float, lon: float, radius_deg: float = 2.5
    ) -> list[CreatureLocation]:
        """Fetch creatures near a given lat/lon region.

        Queries all relays and filters by bounding box.
        Returns recent creatures in the region, newest first.
        """
        all_creatures = self.fetch_global_creatures(max_events=300)
        return [
            c
            for c in all_creatures
            if abs(c.lat - lat) <= radius_deg and abs(c.lon - lon) <= radius_deg
        ]

    # ── Internal ───────────────────────────────────────────────────────

    def _query_relay(self, relay: str, limit: int = 50) -> list[dict]:
        """Send a Nostr REQ message to a relay and collect EVENT responses.

        Uses a raw WebSocket connection (same pattern as nostr_publisher's
        _websocket_send) with a REQ filter for kind-1, #terramon tag.
        """
        sub_id = "terramon-global-" + str(int(time.time()))
        # Build a REQ message: {"t": "terramon"}
        req = json.dumps(
            ["REQ", sub_id, {"kinds": [1], "#t": ["terramon"], "limit": limit}],
            ensure_ascii=False,
        )
        raw = self._ws_send_receive(relay, req)
        return self._parse_relay_messages(raw, sub_id)

    def _ws_send_receive(self, relay: str, payload: str) -> str:
        """Open a WebSocket, send a frame, read responses, close.

        Returns the raw received text (which may contain multiple JSON lines
        from EOSE, EVENT, etc.).
        """
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
        sock = socket.create_connection((host, port), timeout=self.timeout)
        if u.scheme == "wss":
            sock = ssl.create_default_context().wrap_socket(
                sock, server_hostname=host
            )

        # Send handshake
        sock.sendall(handshake.encode())
        sock.recv(4096)  # read handshake response

        # Build WebSocket text frame (unmasked for server->client receive)
        frame_bytes = payload.encode()
        # We need to send a masked frame (client -> server)
        header = bytearray([0x81])  # FIN + text frame
        mask = _os.urandom(4)
        n = len(frame_bytes)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header += n.to_bytes(2, "big")
        else:
            header.append(0x80 | 127)
            header += n.to_bytes(8, "big")
        header += mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(frame_bytes))
        sock.sendall(bytes(header) + masked)

        # Read response — collect frames until EOSE or timeout
        received = bytearray()
        sock.settimeout(self.timeout)
        try:
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                received.extend(chunk)
        except socket.timeout:
            pass
        finally:
            sock.close()

        # Unmask server frames (first 2 bytes = header, then masking key or not)
        return self._unmask_response(bytes(received))

    @staticmethod
    def _unmask_response(data: bytes) -> str:
        """Extract text payload from a WebSocket server frame.

        Server frames are unmasked. We just need to skip the frame header
        and read the payload.
        """
        if len(data) < 2:
            return ""
        payload_len = data[1] & 0x7F
        offset = 2
        if payload_len == 126:
            payload_len = int.from_bytes(data[2:4], "big")
            offset = 4
        elif payload_len == 127:
            payload_len = int.from_bytes(data[2:10], "big")
            offset = 10

        payload = data[offset : offset + payload_len]
        try:
            return payload.decode("utf-8")
        except UnicodeDecodeError:
            return ""

    @staticmethod
    def _parse_relay_messages(raw: str, sub_id: str) -> list[dict]:
        """Parse raw relay response into individual EVENT dicts.

        The relay may send multiple newline-delimited JSON messages:
        - ["EVENT", <event>]
        - ["EOSE", <sub_id>]
        - ["NOTICE", <msg>]
        We collect and return all EVENT payloads for the requested sub_id.
        """
        events: list[dict] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if not isinstance(msg, list) or len(msg) < 2:
                continue
            if msg[0] == "EVENT":
                ev = msg[1]
                if isinstance(ev, dict):
                    events.append(ev)
            elif msg[0] == "EOSE":
                break  # End of stored events — no more coming
        return events

    @staticmethod
    def _parse_event(ev: dict) -> CreatureLocation | None:
        """Parse a Nostr event dict into a CreatureLocation.

        Looks for "g" tags with lat/lon. Falls back to content parsing
        for geo hints in the event text.
        """
        lat, lon = 0.0, 0.0

        # Try "g" tag first: ["g", "50.061900", "19.937200"]
        tags = ev.get("tags", [])
        for tag in tags:
            if len(tag) >= 3 and tag[0] == "g":
                try:
                    lat = float(tag[1])
                    lon = float(tag[2])
                except (ValueError, IndexError):
                    continue
                break

        if not lat and not lon:
            return None  # no geo data — skip

        # Extract agent name from tags
        agent = ""
        for tag in tags:
            if len(tag) >= 2 and tag[0] == "t" and tag[1] != "terramon":
                agent = tag[1]
                break

        # Extract content (the thought/description)
        content = ev.get("content", "")

        return CreatureLocation(
            event_id=ev.get("id", ""),
            pubkey=ev.get("pubkey", ""),
            lat=lat,
            lon=lon,
            agent=agent,
            thought=content[:100],
            timestamp=ev.get("created_at", 0),
            rarity="common",
        )

    # ── P3 M04: TradeOffer reading ────────────────────────────────────

    def fetch_trade_offers(self, max_events: int = 50) -> list[TradeOffer]:
        """Fetch trade offer events (kind 40000) from all configured relays.

        Queries each relay with a REQ for kind-40000 events tagged #trade-offer.
        Returns deduplicated TradeOffer list sorted by timestamp desc.
        """
        all_offers: dict[str, TradeOffer] = {}
        for relay in self.relays:
            try:
                events = self._query_trade_relay(relay, limit=min(max_events, 50))
                for ev in events:
                    offer = self._parse_trade_offer(ev)
                    if offer and offer.event_id not in all_offers:
                        all_offers[offer.event_id] = offer
            except Exception as exc:
                log.warning("Relay %s trade query failed: %s", relay, exc)

        result = sorted(all_offers.values(), key=lambda o: o.timestamp, reverse=True)
        return result[:max_events]

    def _query_trade_relay(self, relay: str, limit: int = 50) -> list[dict]:
        """Send a Nostr REQ for kind 40000 events with #trade-offer tag."""
        sub_id = "terramon-trade-" + str(int(time.time()))
        req = json.dumps(
            ["REQ", sub_id, {"kinds": [40000], "#t": ["trade-offer"], "limit": limit}],
            ensure_ascii=False,
        )
        raw = self._ws_send_receive(relay, req)
        return self._parse_relay_messages(raw, sub_id)

    @staticmethod
    def _parse_trade_offer(ev: dict) -> TradeOffer | None:
        """Parse a kind-40000 event dict into a TradeOffer.

        Extracts creature_id (d tag), agent name, rarity, price from tags.
        """
        tags = ev.get("tags", [])
        creature_id = ""
        agent_name = ""
        rarity = "common"
        price_sats = 0

        for tag in tags:
            if len(tag) >= 2:
                if tag[0] == "d":
                    creature_id = tag[1]
                elif tag[0] == "agent":
                    agent_name = tag[1]
                elif tag[0] == "rarity":
                    rarity = tag[1]
                elif tag[0] == "price":
                    try:
                        price_sats = int(tag[1])
                    except (ValueError, IndexError):
                        pass

        if not creature_id:
            return None

        content = ev.get("content", "")
        return TradeOffer(
            event_id=ev.get("id", ""),
            pubkey=ev.get("pubkey", ""),
            creature_id=creature_id,
            agent_name=agent_name,
            rarity=rarity,
            price_sats=price_sats,
            thought=content[:200],
            timestamp=ev.get("created_at", 0),
        )
