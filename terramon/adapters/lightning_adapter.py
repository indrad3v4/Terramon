"""Lightning adapter via LNBits — non-custodial.

Funds settle straight to YOUR Lightning node (LNBits is just the API front).
Needs an LNBits instance URL + Admin/Invoice API key (env). The HTTP layer is
injectable so tests run offline with a fake transport.

Maps to course Phase 13: the adapter is a concrete Tool implementation behind
PaymentPort, swappable for Stripe or on-chain without changing game code.
"""

from __future__ import annotations

import os
import json
import urllib.request

from terramon.ports.payment_port import PaymentMethod, PaymentPort, PaymentRequest


class LightningAdapter(PaymentPort):
    """Creates BOLT11 invoices and checks their settled status via LNBits."""

    def __init__(self, url: str | None = None, api_key: str | None = None, http=None) -> None:
        self.url = (url or os.getenv("LNBITS_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("LNBITS_API_KEY", "")
        self._http = http or _urllib_json

    def create_payment(self, amount_sats: int, memo: str) -> PaymentRequest:
        if not self.url or not self.api_key:
            raise RuntimeError("LNBits not configured: set LNBITS_URL and LNBITS_API_KEY")
        body = json.dumps({"out": False, "amount": amount_sats, "memo": memo}).encode()
        headers = {"X-Api-Key": self.api_key, "Content-Type": "application/json"}
        data = self._http("POST", f"{self.url}/api/v1/payments", body, headers)
        return PaymentRequest(
            id=data["checking_id"],
            method=PaymentMethod.LIGHTNING,
            amount_sats=amount_sats,
            destination=data["payment_request"],  # BOLT11 invoice
            memo=memo,
            verification_ref=data["checking_id"],
        )

    def verify_payment(self, request: PaymentRequest, proof: str = "") -> bool:
        checking_id = proof or request.verification_ref
        if not checking_id:
            return False
        data = self._http(
            "GET",
            f"{self.url}/api/v1/payments/{checking_id}",
            None,
            {"X-Api-Key": self.api_key},
        )
        if data.get("paid"):
            request.status = "paid"
            return True
        return False


def _urllib_json(method: str, url: str, body: bytes | None, headers: dict) -> dict:
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())
