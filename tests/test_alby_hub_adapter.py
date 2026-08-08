"""Tests for AlbyHubAdapter — offline (fake HTTP transport)."""
from __future__ import annotations

import json

from terramon.adapters.alby_hub_adapter import AlbyHubAdapter
from terramon.ports.payment_port import PaymentMethod


class FakeHttp:
    def __init__(self, responses: list[dict]):
        self.responses = responses
        self.calls: list[tuple] = []

    def __call__(self, method, url, body, headers):
        self.calls.append((method, url, body, headers))
        return self.responses.pop(0)


def test_create_payment_builds_bolt11_request():
    http = FakeHttp([
        {"invoice": {
            "invoice_id": "inv-123",
            "payment_request": "lnbc10u1pterramon",
        }}
    ])
    a = AlbyHubAdapter(url="https://hub.example", api_key="jwt-test", http=http)
    req = a.create_payment(1000, "terramon test")

    assert req.method == PaymentMethod.LIGHTNING
    assert req.amount_sats == 1000
    assert req.destination == "lnbc10u1pterramon"
    assert req.verification_ref == "inv-123"
    # auth header + json body
    method, url, body, headers = http.calls[0]
    assert url == "https://hub.example/api/invoices"
    assert headers["Authorization"] == "Bearer jwt-test"
    payload = json.loads(body)
    assert payload["amount"] == 1000


def test_verify_payment_settled():
    http = FakeHttp([
        {"invoice": {"invoice_id": "inv-123", "payment_request": "lnbc10u1p"}},
        {"settled": True},
    ])
    a = AlbyHubAdapter(url="https://hub.example", api_key="jwt-test", http=http)
    req = a.create_payment(1000, "m")
    assert a.verify_payment(req) is True
    assert req.status == "paid"
    method, url, _, _ = http.calls[1]
    assert url == "https://hub.example/api/invoices/inv-123"


def test_verify_payment_unsettled():
    http = FakeHttp([
        {"invoice": {"invoice_id": "inv-123", "payment_request": "lnbc10u1p"}},
        {"settled": False},
    ])
    a = AlbyHubAdapter(url="https://hub.example", api_key="jwt-test", http=http)
    req = a.create_payment(1000, "m")
    assert a.verify_payment(req) is False


def test_create_payment_error_message():
    http = FakeHttp([{"message": "LiquidityRequestFailed"}])
    a = AlbyHubAdapter(url="https://hub.example", api_key="jwt-test", http=http)
    try:
        a.create_payment(3000, "m")
        assert False, "should raise"
    except RuntimeError as e:
        assert "LiquidityRequestFailed" in str(e)


def test_requires_config():
    a = AlbyHubAdapter(url="", api_key="")
    try:
        a.create_payment(100, "m")
        assert False, "should raise"
    except RuntimeError as e:
        assert "ALBY_HUB_URL" in str(e)
