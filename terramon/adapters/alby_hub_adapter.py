"""Alby Hub adapter — self-custodial Lightning node (LDK) via REST API.

Funds settle straight to YOUR Alby Hub node (deployed on Railway). The hub
is non-custodial: the JWT/API key only controls invoices — sats stay on your
node until you swap them out on-chain.

Maps to course Phase 13: a concrete Tool implementation behind PaymentPort,
swappable for LNBits/Stripe/on-chain without changing game code.

HTTP layer is injectable so tests run offline with a fake transport.
"""

from __future__ import annotations

import os
import json
import urllib.request

from terramon.ports.payment_port import PaymentMethod, PaymentPort, PaymentRequest


class AlbyHubAdapter(PaymentPort):
    """Creates BOLT11 invoices and checks their settled status via Alby Hub API."""

    def __init__(self, url: str | None = None, api_key: str | None = None, http=None) -> None:
        self.url = (url or os.getenv("ALBY_HUB_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("ALBY_HUB_API_KEY", "")
        self._http = http or _urllib_json

    def _headers(self, extra: dict | None = None) -> dict:
        h = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        if extra:
            h.update(extra)
        return h

    def create_payment(self, amount_sats: int, memo: str) -> PaymentRequest:
        if not self.url or not self.api_key:
            raise RuntimeError(
                "Alby Hub not configured: set ALBY_HUB_URL and ALBY_HUB_API_KEY"
            )
        body = json.dumps(
            {"amount": amount_sats, "description": memo, "expiry": 3600}
        ).encode()
        data = self._http("POST", f"{self.url}/api/invoices", body, self._headers())
        # Alby Hub returns {"invoice": {...}} on success; {"message": ...} on error.
        if "message" in data and "payment_request" not in data:
            raise RuntimeError(f"Alby Hub invoice failed: {data['message']}")
        inv = data.get("invoice", data)
        bolt11 = inv.get("payment_request") or inv.get("invoice") or ""
        inv_id = str(inv.get("invoice_id") or inv.get("id") or inv.get("r_hash") or "")
        if not bolt11:
            raise RuntimeError("Alby Hub invoice response missing payment_request")
        return PaymentRequest(
            id=inv_id,
            method=PaymentMethod.LIGHTNING,
            amount_sats=amount_sats,
            destination=bolt11,
            memo=memo,
            verification_ref=inv_id,
        )

    def verify_payment(self, request: PaymentRequest, proof: str = "") -> bool:
        ref = proof or request.verification_ref
        if not ref:
            return False
        data = self._http("GET", f"{self.url}/api/invoices/{ref}", None, self._headers())
        if data.get("settled") or data.get("paid"):
            request.status = "paid"
            return True
        return False


def _urllib_json(method: str, url: str, body: bytes | None, headers: dict) -> dict:
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())
