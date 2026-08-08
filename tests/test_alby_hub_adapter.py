"""Tests for AlbyHubAdapter — offline (fake HTTP transport).

Payload contract mirrors Alby Hub >= v1.20 (validated against a live
v1.23.0 hub): POST /api/invoices takes amountMsat (uint64 millisats),
returns the invoice object directly (BOLT11 at `invoice`, hash at
`paymentHash`); verification is GET /api/transactions/{paymentHash} with
legacy /api/invoices/{id} fallback.
"""
from __future__ import annotations

import json

import pytest

from terramon.adapters.alby_hub_adapter import AlbyHubAdapter
from terramon.ports.payment_port import PaymentMethod


class FakeHttp:
    def __init__(self, responses: list):
        self.responses = responses
        self.calls: list[tuple] = []

    def __call__(self, method, url, body, headers):
        self.calls.append((method, url, body, headers))
        resp = self.responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


def test_create_payment_builds_bolt11_request_v123_shape():
    """v1.23+ response: invoice object directly, BOLT11 under `invoice`."""
    http = FakeHttp([
        {"id": 1, "type": "incoming", "state": "pending",
         "invoice": "lnbc10u1pterramon", "paymentHash": "ph-123"},
    ])
    a = AlbyHubAdapter(url="https://hub.example", api_key="jwt-test", http=http)
    req = a.create_payment(1000, "terramon test")

    assert req.method == PaymentMethod.LIGHTNING
    assert req.amount_sats == 1000
    assert req.destination == "lnbc10u1pterramon"
    assert req.verification_ref == "ph-123"
    # auth header + json body with MILLISATS (amountMsat), not sats
    method, url, body, headers = http.calls[0]
    assert method == "POST"
    assert url == "https://hub.example/api/invoices"
    assert headers["Authorization"] == "Bearer jwt-test"
    payload = json.loads(body)
    assert payload["amountMsat"] == 1_000_000
    assert payload["description"] == "terramon test"
    assert "amount" not in payload  # deprecated field must not be sent


def test_create_payment_legacy_response_shape():
    """Older hubs wrap the invoice: {"invoice": {"invoice_id", "payment_request"}}."""
    http = FakeHttp([
        {"invoice": {"invoice_id": "inv-123", "payment_request": "lnbc10u1p"}}
    ])
    a = AlbyHubAdapter(url="https://hub.example", api_key="jwt-test", http=http)
    req = a.create_payment(1000, "m")
    assert req.destination == "lnbc10u1p"
    assert req.verification_ref == "inv-123"


def test_create_payment_converts_float_sats_to_whole_msat():
    """Float input must become an integer msat payload (never a float)."""
    http = FakeHttp([
        {"id": 2, "state": "pending", "invoice": "lnbc1p", "paymentHash": "ph-2"}
    ])
    a = AlbyHubAdapter(url="https://hub.example", api_key="jwt-test", http=http)
    req = a.create_payment(15.5, "m")
    assert req.amount_sats == 15.5
    payload = json.loads(http.calls[0][2])
    assert payload["amountMsat"] == 15_500
    assert isinstance(payload["amountMsat"], int)


def test_verify_payment_settled_via_transactions_endpoint():
    http = FakeHttp([
        {"id": 1, "state": "pending", "invoice": "lnbc10u1p", "paymentHash": "ph-123"},
        {"state": "settled", "settledAt": "2026-08-09T00:00:00Z"},
    ])
    a = AlbyHubAdapter(url="https://hub.example", api_key="jwt-test", http=http)
    req = a.create_payment(1000, "m")
    assert a.verify_payment(req) is True
    assert req.status == "paid"
    method, url, _, _ = http.calls[1]
    assert method == "GET"
    assert url == "https://hub.example/api/transactions/ph-123"


def test_verify_payment_unsettled():
    http = FakeHttp([
        {"id": 1, "state": "pending", "invoice": "lnbc10u1p", "paymentHash": "ph-123"},
        {"state": "pending"},
    ])
    a = AlbyHubAdapter(url="https://hub.example", api_key="jwt-test", http=http)
    req = a.create_payment(1000, "m")
    assert a.verify_payment(req) is False


def test_verify_payment_falls_back_to_legacy_invoice_route():
    """Old hubs have no /api/transactions — retry with /api/invoices/{id}."""
    http = FakeHttp([
        {"id": 1, "state": "pending", "invoice": "lnbc10u1p", "paymentHash": "ph-123"},
        RuntimeError("boom: SPA html instead of json"),
        {"settled": True},
    ])
    a = AlbyHubAdapter(url="https://hub.example", api_key="jwt-test", http=http)
    req = a.create_payment(1000, "m")
    assert a.verify_payment(req) is True
    assert req.status == "paid"
    assert http.calls[2][1] == "https://hub.example/api/invoices/ph-123"


def test_create_payment_error_message():
    http = FakeHttp([{"message": "LiquidityRequestFailed"}])
    a = AlbyHubAdapter(url="https://hub.example", api_key="jwt-test", http=http)
    with pytest.raises(RuntimeError, match="LiquidityRequestFailed"):
        a.create_payment(3000, "m")


def test_requires_config():
    a = AlbyHubAdapter(url="", api_key="")
    with pytest.raises(RuntimeError, match="ALBY_HUB_URL"):
        a.create_payment(100, "m")
