"""«Зажечь свечу» (Light a Candle) — offline tests for the WebLN ritual.

Covers the whole candle contract without network, Reflex or LLM:
price constant, deterministic lore template, WebLN decision helper
(keysend-first, honest nowebln failure), seed persistence, the
released-only UI gate, and the ZERO-LLM guarantee.
"""

from pathlib import Path

from terramon.adapters.json_memory import JsonMemory
from terramon.domain.candle import (
    CANDLE_LORE_TEMPLATE,
    CANDLE_NODE_PUBKEY,
    CANDLE_PRICE_SATS,
    candle_js,
    candle_lore_for,
    candle_outcome,
    persist_candle_lore,
    seed_is_released,
)
from terramon.domain.thought_seed import ThoughtSeed


# 1. Price -----------------------------------------------------------------


def test_candle_price_constant():
    """The ritual is exactly 500 sats — a gesture, not a checkout."""
    assert CANDLE_PRICE_SATS == 500
    assert CANDLE_PRICE_SATS > 0
    # 500 sats sits FAR below the Alby Hub JIT-channel invoice floor (2501),
    # which is precisely why keysend (push payment) is the primary route.
    assert CANDLE_PRICE_SATS < 2501


# 2. Deterministic lore template -------------------------------------------


def test_candle_lore_template():
    """Given final_words, the template produces a line containing them."""
    lore = candle_lore_for("Будь свободен")
    assert "Будь свободен" in lore
    assert "Свеча горит" in lore
    # The template is fixed — no LLM, no randomness, no personality lookup.
    assert CANDLE_LORE_TEMPLATE == "Свеча горит у моего места рождения. Я помню: {final_words}"


def test_candle_lore_empty_words_falls_back():
    """No final words → the canonical short line (still deterministic)."""
    assert candle_lore_for("") == "Свеча горит у моего места рождения. Я помню тебя."
    assert candle_lore_for("   ") == candle_lore_for("")


# 3. WebLN decision helper -------------------------------------------------


def test_light_candle_rejects_no_webln():
    """Missing window.webln → {ok:false, reason:'nowebln'} → UI shows Alby hint."""
    payload = {"ok": False, "reason": "nowebln"}
    outcome = candle_outcome(payload)
    assert outcome["state"] == "nowebln"
    assert outcome["reason"] == "nowebln"
    assert outcome["lore"] == ""  # creature never speaks without payment
    # The JS itself must perform the detection and return that contract.
    js = candle_js()
    assert "window.webln" in js
    assert "nowebln" in js
    assert "keysend" in js  # primary route: push payment, no invoice


def test_candle_js_keysend_contract():
    """The inline JS carries the 500-sat keysend push to the node pubkey."""
    js = candle_js()
    assert CANDLE_NODE_PUBKEY in js
    assert "amount:500" in js
    assert "762916001" in js  # TLV message custom record with the memo
    assert js.startswith("(async () => {")
    assert js.endswith("})()")


# 4. Persistence on the creature seed --------------------------------------


def test_candle_persists_on_seed(tmp_path: Path):
    """After lighting, candle_lore + released status survive a memory reload."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    seed = ThoughtSeed(
        raw_input="release me to the wind",
        summoned_agent="Sage",
        timestamp="2026-08-09T00:00:00",
    )
    memory.save_seed(seed)

    lore = candle_lore_for("Будь свободен")
    assert persist_candle_lore(memory, "Sage", "release me to the wind", lore) is True

    reloaded = memory.load_all_seeds()
    assert len(reloaded) == 1  # no duplicate record — in-place update
    assert reloaded[0].candle_lore == lore
    assert reloaded[0].status == "released"
    assert seed_is_released(memory, "Sage", "release me to the wind") is True


def test_candle_persist_no_match_is_false(tmp_path: Path):
    """Unknown creature → no seed touched, no crash."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    memory.save_seed(ThoughtSeed("t", "Hero", "2026-08-09"))
    assert persist_candle_lore(memory, "Ghost", "nope", "lore") is False
    assert memory.load_all_seeds()[0].candle_lore == ""


# 5. Released-only UI gate -------------------------------------------------


def test_candle_button_gated_on_released(tmp_path: Path):
    """The render-cond logic: button only for released creatures."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    memory.save_seed(ThoughtSeed("still with me", "Hero", "2026-08-09T00:00:00"))
    memory.save_seed(ThoughtSeed("gone wild", "Sage", "2026-08-09T01:00:00"))

    # Not released yet — the gate stays closed.
    assert seed_is_released(memory, "Hero", "still with me") is False

    # Release the Sage → gate opens.
    memory.update_seed("Sage", "gone wild", status="released")
    assert seed_is_released(memory, "Sage", "gone wild") is True


# 6. Zero LLM budget -------------------------------------------------------


def test_no_llm_budget():
    """The candle path must never touch an LLM."""
    import inspect

    import terramon.domain.candle as candle_mod

    src = inspect.getsource(candle_mod)
    # No LLM import, no OpenRouter key, no generate_response, no chat call.
    for forbidden in ("llm", "openrouter", "OPENROUTER", "generate_response", "chat"):
        assert forbidden not in src, f"candle module must not reference {forbidden!r}"
    # And the whole module is pure Python — it imports without Reflex.
    assert "reflex" not in src
