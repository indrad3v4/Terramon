"""KPI geo/mint-honesty regression traps (offline, source-level).

Same style as test_iter6_regression.py / test_gate_regression.py: the KPI
script is read as TEXT (pathlib, read-only). The Playwright app is
deliberately NOT imported — importing it would launch a browser and hit
production. These guards lock the KPI honesty contract so a future
refactor cannot silently revert it.

Contract 1 — geo_ok_from_map_url:
    Real geo evidence must come from the static-map img URL's own query
    params (non-zero lat & lon), parsed with parse_qs/urlparse — not from
    trusting rendered body text. Map-URL coordinates are the ground truth
    the North Star metric is built on.

Contract 2 — m7_gate_probe:
    The payment-gate probe (round 1 only) records that the 'Pay with
    Lightning' button was actually clicked once, so the M7 loop's gate
    visibility is observable instead of assumed. Probe only — no payment.

Contract 3 — presence-only mint policy:
    The KPI NEVER clicks any mint button ('Mint (1 Star)' / '⚡ MINT') —
    since ae3a162 the mint button is buy_stars with an optimistic
    _record_mint, so a click here would FABRICATE mint_count on
    production and poison the North Star metric. Presence-only logging:
    count, never click. The policy must stay documented in the source.

Contract 4 — THOUGHTS round list:
    Exactly 12 archetype thoughts — one summon round per archetype, each
    in a fresh browser context with a fresh player identity.
"""

import re
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "kpi" / "play_to_win.py"

# The 12 archetype thoughts that drive the 12 summon rounds.
_KPI_ARCHETYPES = [
    "Hero",
    "Rebel",
    "Sage",
    "Jester",
    "Creator",
    "Magician",
    "Lover",
    "Caregiver",
    "Explorer",
    "Innocent",
    "Ruler",
    "Orphan",
]

_MINT_LABELS = ("'Mint (1 Star)'", "'⚡ MINT'")


@pytest.fixture(scope="module")
def source() -> str:
    """The real KPI script, read fresh from disk on every run (read-only)."""
    if not SOURCE.is_file():
        pytest.fail(f"KPI script not found: {SOURCE}")
    return SOURCE.read_text(encoding="utf-8")


# ── Contract 1: map-URL geo evidence ───────────────────────────────────


def test_geo_ok_from_map_url_helper(source):
    """Map-URL coordinates must be the geo-evidence source.

    geo_ok_from_map_url must exist: it returns True only when a static-map
    img URL carries non-zero lat & lon query params. That is REAL geo
    evidence — the map tile only renders at real coordinates, so trusting
    the URL is honest measurement for the North Star metric. It must also
    actually parse the query string (parse_qs / urlparse), not just
    string-match for 'lat'.
    """
    assert "geo_ok_from_map_url" in source, (
        "geo_ok_from_map_url helper missing — map-URL geo evidence reverted?"
    )
    assert "parse_qs" in source or "urlparse" in source, (
        "no query-param parsing (parse_qs/urlparse) in the script — "
        "geo_ok_from_map_url cannot actually extract lat/lon from the map URL"
    )


# ── Contract 2: M7 payment-gate probe ──────────────────────────────────


def test_m7_gate_probe(source):
    """The M7 payment-gate probe (round 1 only) must exist and click the gate.

    m7_gate_probe records that the 'Pay with Lightning' button was actually
    clicked once (probe only, no payment), so the M7 loop's gate visibility
    is observable in the KPI report instead of assumed. Locks: the probe
    record key exists, the gate selector is still targeted, and the file
    still performs clicks (the probe is the gate's click).
    """
    assert "m7_gate_probe" in source, (
        "m7_gate_probe record key missing — payment-gate probe reverted?"
    )
    assert "button:has-text('Pay with Lightning')" in source, (
        "payment-gate selector button:has-text('Pay with Lightning') missing"
    )
    assert ".click(" in source, (
        "no .click( anywhere in the script — the gate probe's click was removed?"
    )


# ── Contract 3: presence-only mint policy ──────────────────────────────


def test_never_clicks_mint_button(source):
    """The KPI must NEVER click any mint button (presence-only logging).

    Since ae3a162 the 'Mint (1 Star)' button is buy_stars with an
    optimistic _record_mint — a click on production would FABRICATE
    mint_count and poison the North Star metric. No '.click(' may share a
    line with either mint label ('Mint (1 Star)' or '⚡ MINT'); counting
    them ('.count()') is allowed and required.
    """
    for lineno, line in enumerate(source.splitlines(), start=1):
        if ".click(" not in line:
            continue
        for label in _MINT_LABELS:
            assert label not in line, (
                f"line {lineno}: mint click detected — '.click(' on the same "
                f"line as {label}: {line.strip()!r}"
            )


def test_mint_policy_documented(source):
    """The presence-only policy must stay documented in the source.

    The honesty rule must be visible to future editors as a comment, not
    only enforced by the absence of a click — so a refactor that adds a
    mint click has to actively delete the policy note too.
    """
    assert ("presence only" in source) or ("never clicked" in source), (
        "presence-only mint policy not documented — the header comment must "
        "state 'presence only' or 'never clicked'"
    )


# ── Contract 4: THOUGHTS round list ────────────────────────────────────


def test_thoughts_has_all_12_archetypes(source):
    """THOUGHTS must carry one thought per archetype (12 summon rounds).

    Each of the 12 archetypes gets its own summon round in a fresh browser
    context with a fresh player identity. Dropping one would silently
    shrink the run to 11 rounds and skew collection coverage.
    """
    missing = [name for name in _KPI_ARCHETYPES if name not in source]
    assert not missing, (
        f"THOUGHTS missing archetype(s): {missing} — 12-round coverage broken?"
    )
    # The THOUGHTS block itself holds exactly 12 entries (4-space indented
    # tuple lines) — guards against a name living only in ARCHETYPES.
    # Scoped to the THOUGHTS [...] literal so other code can't skew the count.
    block = re.search(r"THOUGHTS = \[(.*?)\n\]", source, re.S)
    assert block is not None, "THOUGHTS list literal not found"
    entries = [
        line for line in block.group(1).splitlines() if line.strip().startswith("(")
    ]
    assert len(entries) == 12, (
        f"THOUGHTS block has {len(entries)} entries, expected 12 — "
        "summon-round coverage changed?"
    )
