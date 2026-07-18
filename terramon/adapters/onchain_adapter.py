"""On-chain Bitcoin adapter — WATCH-ONLY.

CRITICAL SECURITY MODEL
-----------------------
This adapter NEVER holds a private key. It only knows the PUBLIC receiving
address (bc1q…, like an IBAN). It builds a payment request and verifies
settlement by looking up transactions to that address.

Default address is the project treasury address supplied by the owner. Point
TERRAMON_BTC_ADDRESS at a dedicated donation wallet to keep personal funds
separate. Publishing a receiving address is safe — only the private key is
secret.

Network lookup is injectable (`lookup_txs`) so tests run fully offline.
"""

from __future__ import annotations

import os
import uuid

from terramon.ports.payment_port import PaymentMethod, PaymentPort, PaymentRequest

# Public receiving address (watch-only). Safe to publish, like an IBAN.
# Override with TERRAMON_BTC_ADDRESS to use a dedicated donation wallet.
DEFAULT_TREASURY_ADDRESS = "bc1q5am2mqlnzymv6q3sc5neu0s6ladz8pe588l3nh"


class OnChainAdapter(PaymentPort):
    """Creates on-chain payment requests and verifies them via a tx lookup."""

    def __init__(self, address: str | None = None, lookup_txs=None) -> None:
        self.address = address or os.getenv("TERRAMON_BTC_ADDRESS") or DEFAULT_TREASURY_ADDRESS
        self._lookup_txs = lookup_txs or _blockstream_lookup

    def create_payment(self, amount_sats: int, memo: str) -> PaymentRequest:
        ref = f"terramon:{uuid.uuid4().hex[:12]}"
        return PaymentRequest(
            id=ref,
            method=PaymentMethod.ONCHAIN,
            amount_sats=amount_sats,
            destination=self.address,
            memo=f"{memo} [{ref}]",
        )

    def verify_payment(self, request: PaymentRequest, proof: str) -> bool:
        """`proof` is a txid. Confirm it pays this address with enough sats."""
        txs = self._lookup_txs(self.address)
        for tx in txs:
            if tx.get("txid") != proof:
                continue
            if _tx_pays_address(tx, self.address, request.amount_sats):
                request.status = "paid"
                request.verification_ref = proof
                return True
        return False


def _blockstream_lookup(address: str) -> list[dict]:
    """Real lookup against the public Blockstream API (no API key needed)."""
    import json
    import urllib.request

    url = f"https://blockstream.info/api/address/{address}/txs"
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode())


def _tx_pays_address(tx: dict, address: str, min_sats: int) -> bool:
    """Blockstream tx.vout entries carry `scriptpubkey_address` + `value` (sats)."""
    for out in tx.get("vout", []):
        if out.get("scriptpubkey_address") == address and out.get("value", 0) >= min_sats:
            return True
    return False
