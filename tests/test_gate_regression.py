"""Gate + dead-code regression traps (offline, source-level).

Bug class #1 — "dead unlocked" in the gate condition:
    TerramonState.summon_count > 0 & ~TerramonState.unlocked
Bitwise ``&`` binds tighter than ``>`` in Python (and in the compiled
JS), so this parses as ``summon_count > (0 & ~unlocked)`` ==
``summon_count > 0``: the ``~TerramonState.unlocked`` term is dead and
the F3 payment gate leaks after the free summon even when the player
already unlocked.

Fix under test: the condition is parenthesized as
    (TerramonState.summon_count > 0) & ~TerramonState.unlocked
so ``unlocked`` is live again.

Bug class #2 — UI features in tree-shaken dead code:
creature_card() was never called, so Reflex tree-shook it out of the
production bundle and the 💠 MINTED badge, the ⚡ MINT button and the
📤 Share button silently vanished from the UI.
Fix under test: those features moved into the LIVE creature_care_panel()
and the dead creature_card() definition was removed.

These traps read the SOURCE as text (pathlib, read-only): rx.cond
compiles to JS, so the gate cannot be unit-tested through Python — the
source is the only place this bug class is observable offline. The tests
locate functions by NAME (never by line number): the file is being
edited in parallel and offsets may shift.
"""

import re
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "terramon_tma" / "terramon_tma.py"


@pytest.fixture(scope="module")
def source() -> str:
    """The real TMA source, read fresh from disk on every run (read-only)."""
    return SOURCE.read_text(encoding="utf-8")


def _top_level_func_lines(source: str, name: str) -> list[str]:
    """Lines of a top-level function body: from its ``def name(`` (column 0)
    up to the next top-level ``def``. Function names, not line numbers."""
    lines = source.splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if ln.startswith(f"def {name}(")),
        None,
    )
    if start is None:
        pytest.fail(f"top-level function 'def {name}(' not found in source")
    end = next(
        (i for i in range(start + 1, len(lines)) if re.match(r"^def ", lines[i])),
        len(lines),
    )
    return lines[start:end]


def test_gate_condition_is_parenthesized(source):
    """The gate condition MUST be parenthesized; the unparenthesized form
    (dead `unlocked`) MUST NOT appear anywhere."""
    # Fixed form present...
    assert (
        "(TerramonState.summon_count > 0) & ~TerramonState.unlocked" in source
    ), "parenthesized gate condition not found"
    # ...and the buggy form gone (parses as `summon_count > (0 & ~unlocked)`).
    assert "summon_count > 0 & ~" not in source, (
        "unparenthesized gate condition found — `~TerramonState.unlocked` is dead"
    )


def test_gate_condition_semantics_python():
    """Pure-Python lock-in of the gate truth table.

    `&` binds tighter than `>`: only the parenthesized form lets
    `unlocked` override `summon_count`. sc=1 & unlocked=True MUST hide
    the gate — otherwise the payment gate leaks to already-unlocked
    players.
    """

    # The exact shape of the fixed condition on the gate line.
    def gate(sc, unlocked):
        return (sc > 0) & ~unlocked

    # Literal expression from the fixed source line: gate hidden at
    # unlocked=True even though sc > 0.
    assert bool((1 > 0) & ~True) is False

    # Expected truth table (locked in):
    #   sc=0, unlocked=False -> hidden (no summon yet, no gate)
    #   sc=1, unlocked=False -> shown (free summon used, pay to unlock)
    #   sc=1, unlocked=True  -> hidden (unlocked is LIVE)
    table = [
        (0, False, False),
        (1, False, True),
        (1, True, False),
    ]
    for sc, unlocked, expected in table:
        assert bool(gate(sc, unlocked)) is expected, (sc, unlocked, expected)

    # Contrast: the OLD unparenthesized form makes `unlocked` dead —
    # both sc=1 rows are truthy regardless of `unlocked` (the bug).
    def buggy_gate(sc, unlocked):
        return sc > 0 & ~unlocked  # parses as sc > (0 & ~unlocked)

    assert bool(buggy_gate(1, True)) is True  # WRONG: leaks past unlocked
    assert bool(buggy_gate(1, False)) is True


def test_mint_button_lives_in_care_panel(source):
    """MINT / Share buttons + their handlers must live inside the LIVE
    creature_care_panel(), not in a dead function."""
    panel = "\n".join(_top_level_func_lines(source, "creature_care_panel"))
    assert "⚡ MINT" in panel, "MINT button not inside creature_care_panel()"
    assert "mint_creature" in panel, "mint_creature handler not inside creature_care_panel()"
    assert "📤 Share" in panel, "Share button not inside creature_care_panel()"
    assert "share_creature" in panel, "share_creature handler not inside creature_care_panel()"


def test_dead_creature_card_removed(source):
    """The tree-shaken dead function creature_card() must be GONE as a
    definition. Mentions of 'creature_card' in comments are allowed."""
    assert "def creature_card" not in source, "dead def creature_card() still present"
    assert not any(
        re.match(r"^def\s+creature_card\b", ln) for ln in source.splitlines()
    ), "dead top-level def creature_card() still present"


def test_minted_badge_in_care_panel(source):
    """The 💠 MINTED badge must live inside creature_care_panel()."""
    panel = "\n".join(_top_level_func_lines(source, "creature_care_panel"))
    assert any("MINTED" in ln for ln in panel.splitlines()), (
        "MINTED badge not found inside creature_care_panel()"
    )


def test_health_mint_counter_source(source):
    """The health KPI endpoint must still read `mint_count` from seeds
    (the counter's source of truth after the mint loop fix)."""
    lines = source.splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if ln.startswith("def health(")),
        None,
    )
    assert start is not None, "top-level 'def health(' not found in source"
    tail = "\n".join(lines[start:])
    assert "mint_count" in tail, "mint_count not read in health endpoint"


def test_health_share_counter_source(source):
    """The health KPI endpoint must expose the M6 share counter fields:
    `share_count` / `shares_7d` from the persisted JsonMemory share
    registry, plus `alby_configured` from the Alby adapter config."""
    lines = source.splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if ln.startswith("def health(")),
        None,
    )
    assert start is not None, "top-level 'def health(' not found in source"
    tail = "\n".join(lines[start:])
    assert "share_count" in tail, "share_count not exposed in health endpoint"
    assert "alby_configured" in tail, "alby_configured not exposed in health endpoint"
    assert "count_shares" in tail, (
        "share counter not read from _MEMORY in health endpoint"
    )


def test_share_creature_records_share_source(source):
    """share_creature() must record every share attempt on the persisted
    registry (_MEMORY.record_share) — the M6 KPI counter's source of
    truth. Must fire AFTER the has_summoned guard, before the clipboard
    copy so unsummoned no-ops never inflate the count."""
    lines = source.splitlines()
    start = next(
        (
            i
            for i, ln in enumerate(lines)
            if ln.lstrip().startswith("def share_creature(")
        ),
        None,
    )
    assert start is not None, "def share_creature( not found in source"
    tail = "\n".join(lines[start:])
    assert "_MEMORY.record_share()" in tail, (
        "share not recorded via _MEMORY.record_share() in share_creature()"
    )
    # Ordering lock-in: guard -> record_share -> set_clipboard.
    guard_idx = tail.index("if not self.has_summoned:")
    record_idx = tail.index("_MEMORY.record_share()")
    clip_idx = tail.index("rx.set_clipboard")
    assert guard_idx < record_idx < clip_idx, (
        "record_share must run after the has_summoned guard and before "
        "the clipboard copy"
    )
