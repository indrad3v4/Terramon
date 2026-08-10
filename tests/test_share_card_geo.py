"""📍 M6 — share card carries GEO IDENTITY + Telegram deep link with share_code.

The share card is the M6 share-loop artifact (kill-condition metric: >= 2% of
sessions share). The KPI gap-table (scripts/kpi/north_star_gap_template.md,
M1 row) flagged that a card without a place 'не несёт идентичность' — so the
card now anchors the creature to its birthplace (self.place → self.geo_place →
agent_lat/agent_lon 2-decimals → omit) and replaces the cosmetic
'🌍 terramon.app' footer with a real Telegram deep link carrying the
creature's 8-char share_code: https://t.me/terrramonBot/terramon?startapp=share_XXXX

Design lock-ins under test:
- _MEMORY.record_share() stays the FIRST statement of share_creature()
  (M6 counter must fire before the clipboard copy).
- The agent_message marker '📤 Creature card copied! Share it anywhere.' is
  byte-locked (KPI probes parse it) — never reword.
- share_code is populated in BOTH seed-known paths (fresh summon in summon()
  after load_all_seeds, and the M4 dedup hydrate _present_existing_creature)
  via _share_code_from_seed — a getattr-guarded pure helper that falls back
  to the timestamp-derived code (same derivation as summon_service's
  AgentSummoned event), so a missing attribute never crashes a summon and
  the deep link never renders empty.
- Never print '0.00, 0.00' — a zero-coordinate place line is omitted.

Offline: no network, no Reflex runtime — the TMA source is read as text and
the pure helper is extracted via ast and executed in isolation (cf.
test_mint_lightning.py / test_gate_regression.py pattern).
"""

import ast
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "terramon_tma" / "terramon_tma.py"

MARKER = "📤 Creature card copied! Share it anywhere."
DEEP_LINK_PREFIX = "https://t.me/terrramonBot/terramon?startapp=share_"
FALLBACK_LINK = "🌍 https://t.me/terrramonBot/terramon"


@pytest.fixture(scope="module")
def source() -> str:
    """The real TMA source, read fresh from disk on every run (read-only)."""
    return SOURCE.read_text(encoding="utf-8")


def _method_body(source: str, name: str) -> str:
    """Body of a 4-space-indented TerramonState method: from its
    ``    def name(`` line up to the next method-level ``def``. Located by
    NAME, never by line number — the file is edited in parallel."""
    lines = source.splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if re.match(rf"^    def {re.escape(name)}\(", ln)),
        None,
    )
    if start is None:
        pytest.fail(f"method 'def {name}(' not found in source")
    end = next(
        (i for i in range(start + 1, len(lines)) if re.match(r"^    def ", lines[i])),
        len(lines),
    )
    return "\n".join(lines[start:end])


def _extract_top_level_func(source: str, name: str) -> str:
    """Source text of a top-level function, extracted via ast so it can be
    exec'd in isolation (pure helper test, no Reflex import needed)."""
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(source, node)
    pytest.fail(f"top-level function 'def {name}(' not found in source")


# ── share_creature() card structure ────────────────────────────────────────


def test_record_share_is_first_statement_before_clipboard(source):
    """M6 counter must fire BEFORE rx.set_clipboard — the very first statement."""
    body = _method_body(source, "share_creature")
    assert body.index("_MEMORY.record_share()") < body.index("rx.set_clipboard")
    assert body.index("_MEMORY.record_share()") < body.index("card =")


def test_card_has_geo_identity_line(source):
    """The card carries a 📍 birthplace line (self.place first)."""
    body = _method_body(source, "share_creature")
    assert "📍 " in body
    assert "self.place or self.geo_place" in body


def test_geo_fallback_chain_and_zero_guard(source):
    """Fallback: place → geo_place → lat/lon 2-decimals only if BOTH non-zero;
    and '0.00, 0.00' must never reach the card."""
    body = _method_body(source, "share_creature")
    assert "f\"{self.agent_lat:.2f}, {self.agent_lon:.2f}\"" in body
    assert "self.agent_lat and self.agent_lon" in body
    assert '"0.00, 0.00"' in body  # the explicit guard
    assert 'f"📍 {_place}\\n"' in body


def test_card_deep_link_with_share_code(source):
    """The footer is a real Telegram deep link with ?startapp=share_<code>,
    falling back to the plain bot link when share_code is empty."""
    body = _method_body(source, "share_creature")
    assert "?startapp=share_" in body
    assert f"startapp=share_{{self.share_code}}" in body
    assert DEEP_LINK_PREFIX in body
    assert FALLBACK_LINK in body
    # The cosmetic placeholder is gone.
    assert "🌍 terramon.app" not in body


def test_marker_stays_byte_identical(source):
    """KPI probes parse this exact marker — byte-locked, never reworded."""
    body = _method_body(source, "share_creature")
    assert MARKER in body
    assert body.count(MARKER) == 1


# ── share_code state wiring ────────────────────────────────────────────────


def test_share_code_state_var_declared(source):
    """TerramonState carries share_code (str, default '') near the geo fields."""
    assert re.search(r"^    share_code: str = \"\"", source, re.M)


def test_share_code_populated_on_fresh_summon(source):
    """summon() sets share_code right after load_all_seeds (fresh-summon path)."""
    body = _method_body(source, "summon")
    assert "seeds = _MEMORY.load_all_seeds()" in body
    assert "_share_code_from_seed(seeds[-1] if seeds else None)" in body
    assert body.index("seeds = _MEMORY.load_all_seeds()") < body.index(
        "_share_code_from_seed"
    )


def test_share_code_populated_on_hydrate(source):
    """M4 dedup hydrate (_present_existing_creature) sets share_code from the seed."""
    body = _method_body(source, "_present_existing_creature")
    assert "_share_code_from_seed(seed)" in body


# ── _share_code_from_seed pure helper ──────────────────────────────────────


@pytest.fixture(scope="module")
def share_code_from_seed(source):
    """The real helper, exec'd in isolation from the extracted source text."""
    ns = {}
    exec(_extract_top_level_func(source, "_share_code_from_seed"), ns)
    return ns["_share_code_from_seed"]


def test_helper_none_seed(share_code_from_seed):
    assert share_code_from_seed(None) == ""


def test_helper_prefers_stored_share_code(share_code_from_seed):
    seed = SimpleNamespace(share_code="ABC12345", timestamp="2026-01-01T00:00:00.000")
    assert share_code_from_seed(seed) == "ABC12345"


def test_helper_derives_from_timestamp(share_code_from_seed):
    """Seeds carry no share_code attr (it lives on the AgentSummoned event),
    so the helper derives the same 8-char code summon_service publishes."""
    ts = "2026-08-10T12:34:56.789"
    expected = ts.replace(":", "").replace("-", "").replace(".", "")[-8:]
    seed = SimpleNamespace(timestamp=ts)  # no share_code attribute at all
    assert share_code_from_seed(seed) == expected
    assert len(expected) == 8


def test_helper_missing_attrs_never_raise(share_code_from_seed):
    """A bare/malformed object degrades to '' instead of crashing a summon."""
    assert share_code_from_seed(SimpleNamespace()) == ""
    assert share_code_from_seed(object()) == ""
    assert share_code_from_seed(SimpleNamespace(timestamp="")) == ""


def test_helper_uses_summon_service_derivation(source, share_code_from_seed):
    """The derivation expression matches summon_service.py's AgentSummoned
    share_code (timestamp without : - . , last 8 chars) — source-level cross-check."""
    svc = (
        Path(__file__).resolve().parents[1]
        / "terramon"
        / "application"
        / "summon_service.py"
    ).read_text(encoding="utf-8")
    assert 'replace(":", "").replace("-", "").replace(".", "")[-8:]' in svc
    seed = SimpleNamespace(timestamp="2026-08-10T12:34:56.789")
    assert share_code_from_seed(seed) == "23456789"


def test_deep_link_format_matches_reference(source):
    """Replicates the Make-TON-Telegram-Mini-App-3 referral pattern:
    https://t.me/<bot>/<app>?startapp=<param> — param passed to the Mini App
    as tgWebAppStartParam."""
    assert "https://t.me/terrramonBot/terramon?startapp=share_" in source
