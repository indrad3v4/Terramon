"""Stripe adapter — EUR subscriptions (fiat, NOT bitcoin).

Stripe does NOT settle BTC. Use this for the SUMMONER tier (€9.99/mo). The
on-chain / Lightning adapters handle sats; Stripe handles euros. PaymentPort
abstracts all three so the game logic is identical.

Needs STRIPE_SECRET_KEY + STRIPE_PRICE_ID (env). HTTP layer injectable for
offline tests. Real requests are form-encoded per Stripe's API.
"""

from __future__ import annotations

import os
import json
import urllib.parse
import urllib.request

from terramon.ports.payment_port import PaymentMethod, PaymentPort, PaymentRequest

STRIPE_VERSION = "2023-10-16"
DEFAULT_SUCCESS = "https://terramon.example/done"
DEFAULT_CANCEL = "https://terramon.example/cancel"


class StripeAdapter(PaymentPort):
    """Creates a Stripe Checkout session for a recurring EUR subscription."""

    def __init__(
        self,
        api_key: str | None = None,
        price_id: str | None = None,
        http=None,
    ) -> None:
        self.api_key = api_key or os.getenv("STRIPE_SECRET_KEY", "")
        self.price_id = price_id or os.getenv("STRIPE_PRICE_ID", "")
        self._http = http or _urllib_form

    def create_payment(
        self,
        amount_sats: int,
        memo: str,
        success_url: str = "",
        cancel_url: str = "",
    ) -> PaymentRequest:
        # amount_sats is ignored: a subscription has a fixed EUR price in Stripe.
        if not self.api_key or not self.price_id:
            raise RuntimeError("Stripe not configured: set STRIPE_SECRET_KEY and STRIPE_PRICE_ID")
        form = {
            "mode": "subscription",
            "line_items[0][price]": self.price_id,
            "line_items[0][quantity]": "1",
            "success_url": success_url or DEFAULT_SUCCESS,
            "cancel_url": cancel_url or DEFAULT_CANCEL,
            "metadata[memo]": memo,
        }
        body = urllib.parse.urlencode(form).encode()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = self._http("POST", "https://api.stripe.com/v1/checkout/sessions", body, headers)
        return PaymentRequest(
            id=data["id"],
            method=PaymentMethod.STRIPE,
            amount_sats=amount_sats,
            destination=data["url"],
            memo=memo,
            fiat_hint="EUR subscription",
            verification_ref=data["id"],
        )

    def verify_payment(self, request: PaymentRequest, proof: str = "") -> bool:
        sid = proof or request.verification_ref
        if not sid:
            return False
        data = self._http(
            "GET",
            f"https://api.stripe.com/v1/checkout/sessions/{sid}",
            None,
            {"Authorization": f"Bearer {self.api_key}", "Stripe-Version": STRIPE_VERSION},
        )
        if data.get("status") == "complete":
            request.status = "paid"
            return True
        return False


def _urllib_form(method: str, url: str, body: bytes | None, headers: dict) -> dict:
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())
