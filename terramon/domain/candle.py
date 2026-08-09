"""«Зажечь свечу» (Light a Candle) — the emotional monetization ritual.

A 500-sat Lightning zap sent from the player's own browser wallet via
WebLN (Alby extension). NO invoice node required: keysend is a push
payment, so the 2501-sat JIT-channel floor of the Alby Hub node does not
apply. The reward is the creature's NEW WORDS, not cosmetics.

This module is pure Python (no Reflex, no network) so the candle contract
is unit-testable offline: price, lore template, WebLN decision helper and
persistence wiring.

WebLN design decision (honest):
- PRIMARY: webln.keysend({destination, amount, customRecords}) — push
  payment, no BOLT11 invoice, works at 500 sats, one tap in Alby.
- FALLBACK: webln.sendPayment(bolt11) — only used when the provider
  rejects keysend (some wallets implement sendPayment but not keysend).
  The BOLT11 is produced server-side by the existing Alby adapter
  (create_payment at >= 2501 sats), so a 500-sat candle via this path is
  IMPOSSIBLE with the current node — the JS documents that honestly and
  surfaces it as a wallet-capability error, never a fake success.
"""

from __future__ import annotations

from typing import Any

# ── The ritual contract ────────────────────────────────────────────────

CANDLE_PRICE_SATS = 500

# Memo carried inside the keysend custom record (762916001 = TLV "message").
CANDLE_MEMO = "Terramon: candle lit at birthplace"

# Node pubkey of the Terramon Lightning node (Megalith) that receives the
# keysend push. VERIFY against GET /api/info of the Alby Hub node
# ("nodePubkey") when the node is reachable; the value below is the node's
# 66-hex pubkey, hardcoded so the WebLN JS stays a static inline literal.
CANDLE_NODE_PUBKEY = "038a9e56512ec98da2b5789761f7af8f280baf98a09282360cd6ff1381b5e889bf"

# Deterministic template — ZERO LLM calls on the candle path.
CANDLE_LORE_TEMPLATE = "Свеча горит у моего места рождения. Я помню: {final_words}"


def candle_lore_for(final_words: str) -> str:
    """The creature's new line after the candle is lit (deterministic)."""
    words = (final_words or "").strip()
    if not words:
        return "Свеча горит у моего места рождения. Я помню тебя."
    return CANDLE_LORE_TEMPLATE.format(final_words=words)


def candle_js() -> str:
    """Inline WebLN JS literal (same pattern as the HapticFeedback call).

    Returns {ok, reason?, preimage?}:
      {ok:true, preimage}            — keysend or invoice payment settled
      {ok:false, reason:'nowebln'}   — no window.webln (no Alby extension)
      {ok:false, reason:'rejected'}  — user declined the payment prompt
      {ok:false, reason:'unsupported'|error} — wallet/keysend capability issue
    """
    amount = str(CANDLE_PRICE_SATS)
    pubkey = CANDLE_NODE_PUBKEY
    memo_hex = CANDLE_MEMO.encode("utf-8").hex()
    return (
        "(async () => {"
        "if (!window.webln) return {ok:false,reason:'nowebln'};"
        "try {"
        "await window.webln.enable();"
        "const opts = {destination:'" + pubkey + "',amount:" + amount
        + ",customRecords:{762916001:'" + memo_hex + "'}};"
        "let res;"
        "if (window.webln.keysend) {"
        "try { res = await window.webln.keysend(opts); }"
        "catch (e) { res = null; }"
        "}"
        "if (!res && window.webln.sendPayment) {"
        "res = await window.webln.sendPayment(opts);"
        "}"
        "if (!res) return {ok:false,reason:'unsupported'};"
        "return {ok:true,preimage:(res.preimage||'')};"
        "} catch (e) {"
        "return {ok:false,reason:(e && (e.message||'').includes('reject') ? 'rejected' : 'error')};"
        "}"
        "})()"
    )


def candle_outcome(payload: Any) -> dict:
    """Server-side decision helper for the WebLN JS result.

    Pure and deterministic — the piece the offline tests can pin down.
    """
    if not isinstance(payload, dict):
        return {"state": "failed", "lore": "", "reason": "error"}
    if payload.get("ok"):
        return {"state": "lit", "lore": "", "reason": "", "preimage": str(payload.get("preimage", ""))}
    reason = str(payload.get("reason", "error"))
    if reason == "nowebln":
        return {"state": "nowebln", "lore": "", "reason": reason}
    return {"state": "failed", "lore": "", "reason": reason}


def persist_candle_lore(memory: Any, agent: str, thought: str, lore: str) -> bool:
    """Write the creature's new line onto its seed record.

    ``memory`` is the JsonMemory (or a mock) exposing load_all_seeds() and
    update_seed(). Returns True when a matching seed was updated.
    """
    try:
        seeds = memory.load_all_seeds()
    except Exception:
        return False
    if not seeds:
        return False
    try:
        return bool(memory.update_seed(agent, thought, status="released", candle_lore=lore))
    except Exception:
        return False


def seed_is_released(memory: Any, agent: str, thought: str) -> bool:
    """True when the newest matching seed carries status 'released'.

    Powers the "button visible only for released creatures" gate on reloads.
    """
    try:
        seeds = memory.load_all_seeds()
    except Exception:
        return False
    for s in reversed(seeds):
        if getattr(s, "summoned_agent", "") == agent and getattr(s, "raw_input", "") == thought:
            return getattr(s, "status", "") == "released"
    return False
