"""Alby Hub adapter — self-custodial Lightning node (LDK) via REST API.

Funds settle straight to YOUR Alby Hub node (deployed on Railway). The hub
is non-custodial: the JWT/API key only controls invoices — sats stay on your
node until you swap them out on-chain.

Maps to course Phase 13: a concrete Tool implementation behind PaymentPort,
swappable for LNBits/Stripe/on-chain without changing game code.

HTTP layer is injectable so tests run offline with a fake transport.

API contract (validated against a live Alby Hub v1.23.0, 2026-08-09):
- POST /api/invoices body: {"amountMsat": <uint64 msat>, "description": str}
  The old `amount` field is deprecated and now interpreted as MILLISATS with
  a "whole number of satoshis" validation — sending sats there fails with
  "the amount must be a whole number of satoshis".
- POST /api/invoices response (v1.23+): the invoice object directly, with
  BOLT11 at `invoice`, hub id at `id`, payment hash at `paymentHash`.
  Legacy response was {"invoice": {"invoice_id": ..., "payment_request": ...}}.
- Verify: GET /api/transactions/{paymentHash} → {"state": "pending"|"settled", ...}.
  The old GET /api/invoices/{invoice_id} route was removed in v1.23 (serves SPA
  HTML); kept as a fallback for older hubs.
- Liquidity: a fresh node with no channels rejects invoice creation below the
  JIT-channel minimum (jitChannelsMinPaymentSizeMsat, default ~2501 sats) with
  "LiquidityRequestFailed: Failed to request inbound liquidity". That is a
  node/liquidity issue, not an API-format issue.
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
        # Hub >= v1.20 wants millisatoshis (MakeInvoiceRequest.amountMsat, uint64).
        # Guard against float input: round to whole msat, never send a float.
        amount_msat = int(round(float(amount_sats) * 1000))
        body = json.dumps({"amountMsat": amount_msat, "description": memo}).encode()
        data = self._http("POST", f"{self.url}/api/invoices", body, self._headers())
        if not isinstance(data, dict):
            raise RuntimeError(f"Alby Hub invoice failed: unexpected response {str(data)[:120]!r}")
        # Alby Hub returns {"message": ...} on error; success never carries it.
        if "message" in data and "payment_request" not in data:
            raise RuntimeError(f"Alby Hub invoice failed: {data['message']}")
        # v1.23+ returns the invoice object directly with the BOLT11 as a string
        # under `invoice`; legacy wrapped it as {"invoice": {..., "payment_request": ...}}.
        inv = data.get("invoice", data)
        if isinstance(inv, str):
            bolt11 = inv
            inv_id = data.get("paymentHash") or data.get("id")
        else:
            bolt11 = inv.get("payment_request") or inv.get("invoice") or ""
            inv_id = inv.get("invoice_id") or inv.get("id") or inv.get("r_hash")
        if not bolt11:
            raise RuntimeError("Alby Hub invoice response missing payment_request")
        return PaymentRequest(
            id=str(inv_id or ""),
            method=PaymentMethod.LIGHTNING,
            amount_sats=amount_sats,
            destination=bolt11,
            memo=memo,
            verification_ref=str(inv_id or ""),
        )

    def verify_payment(self, request: PaymentRequest, proof: str = "") -> bool:
        ref = proof or request.verification_ref
        if not ref:
            return False
        # v1.23+: GET /api/transactions/{paymentHash}; legacy hubs: GET /api/invoices/{id}.
        try:
            data = self._http("GET", f"{self.url}/api/transactions/{ref}", None, self._headers())
        except Exception:
            data = self._http("GET", f"{self.url}/api/invoices/{ref}", None, self._headers())
        settled = data.get("state") == "settled" or bool(data.get("settled") or data.get("paid"))
        if settled:
            request.status = "paid"
            return True
        return False


def _urllib_json(method: str, url: str, body: bytes | None, headers: dict) -> dict:
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())
