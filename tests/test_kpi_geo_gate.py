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

Contract 2 — m7_probe (the REAL mint loop, not the dead F3 gate):
    Structural finding: hydrate_from_memory() derives has_summoned from
    ALL seeds globally (15 already exist on prod), and load_terra sets
    unlocked=True for any returning player, so payment_gate() — which
    renders only when summon_count > 0 AND ~unlocked — NEVER renders for
    anyone, forever. The old 'Pay with Lightning' gate probe could never
    succeed. The real mint loop is the creature-card MINT area ('⚡ MINT ·
    N sats', rendered only on a FRESH summon where price_sats > 0 AND
    can_mint) plus the '⚡ Mint via Lightning' invoice button. The pre-loop
    probe summons a run-unique thought (real fresh summon, dedup cannot
    match it) and clicks '⚡ Mint via Lightning' EXACTLY ONCE — invoice
    CREATION only (minting happens only on settle via verify_lightning, so
    no mint record is created, no payment is made).

Contract 3 — presence-only mint policy:
    The KPI NEVER clicks any mint button that creates a mint record
    ('Mint (1 Star)' / '⚡ MINT ·') — since ae3a162 the Stars mint button
    is buy_stars with an optimistic _record_mint, so a click here would
    FABRICATE mint_count on production and poison the North Star metric.
    Presence-only logging: count, never click. The policy must stay
    documented in the source.

Contract 4 — THOUGHTS round list:
    Exactly 12 archetype thoughts — one summon round per archetype, each
    in a fresh browser context with a fresh player identity.

Contract 5 — run-unique probe thought (M7 pre-loop mint-loop probe):
    All 12 THOUGHTS are already seeded on prod, so summoning any of them
    hits the dedup guard (find_seed -> _present_existing_creature) and
    never reaches the fresh-summon path where can_mint is computed — the
    creature-card MINT area never renders on a dedup round. The pre-loop
    probe summons a RUN-UNIQUE thought (millisecond time.time() stamp,
    'мысль странника ...' — a plausible Russian player thought, so the
    creature born is real and presentable) so dedup cannot match it: a
    REAL new summon happens, can_mint is computed, and the MINT area
    renders if price_sats > 0. invoice_ok/invoice_msg are parsed from the
    pay_lightning/mint_lightning agent_message markers (three markers,
    unchanged). Honest note: the probe creates ONE real seed on prod per
    run (probe_seed_created=True).

Contract 6 — M6 share probe (server-side counter):
    Round 1 (Care tab, after a successful summon where has_summoned=True)
    clicks '📤 Share' exactly once. share_creature() records on the
    persisted share registry BEFORE the clipboard write, so the /health
    share_count delta is the authoritative M6 signal — clipboard
    exceptions are non-fatal. The KPI never pays and never clicks
    '✅ I've paid — verify'.
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

# Any '.click(' line sharing text with one of these labels is a forbidden
# action: a mint-button click ('Mint (1 Star)' = buy_stars since ae3a162 —
# fabricates mint_count; '⚡ MINT ·' = the optimistic Stars mint area),
# payment verification ('I've paid'), or the dead F3 payment-gate click
# ('Pay with Lightning' — the gate never renders, see Contract 2).
_FORBIDDEN_CLICK_LABELS = ("⚡ MINT ·", "Mint (1 Star)", "I've paid", "Pay with Lightning")


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


# ── Contract 2: M7 mint-loop probe (the REAL loop, not the dead F3 gate) ─


def test_m7_mint_loop_probe(source):
    """The M7 probe must target the REAL mint loop, not the dead F3 gate.

    Structural finding: hydrate_from_memory() derives has_summoned from ALL
    seeds globally (15 already on prod) and load_terra sets unlocked=True
    for any returning player, so payment_gate() (renders only when
    summon_count > 0 AND ~unlocked) NEVER renders — the old 'Pay with
    Lightning' gate probe could never succeed and just created junk seeds.
    The real loop is the creature-card MINT area + the '⚡ Mint via
    Lightning' invoice button. Locks: the m7_probe record key exists, the
    mint-lightning selector exists exactly once, and it lives inside the
    pre-loop probe block, which clicks it exactly once (probe only —
    invoice creation, no payment, no mint record).
    """
    assert "m7_probe" in source, (
        "m7_probe record key missing — mint-loop probe reverted?"
    )
    assert "button:has-text('⚡ Mint via Lightning')" in source, (
        "mint-lightning selector button:has-text('⚡ Mint via Lightning') missing"
    )
    assert source.count("button:has-text('⚡ Mint via Lightning')") == 1, (
        "the '⚡ Mint via Lightning' locator must appear exactly once (in the probe block)"
    )
    block_start = source.index("m7_probe = {")
    block_end = source.index("M6 share probe", block_start)
    probe_block = source[block_start:block_end]
    assert "button:has-text('⚡ Mint via Lightning')" in probe_block, (
        "mint-lightning selector not inside the pre-loop probe block"
    )
    # After the selector, the probe block must click exactly once (the
    # invoice-creation click) — locks 'clicked at most/exactly once'.
    tail = probe_block[probe_block.index("button:has-text('⚡ Mint via Lightning')"):]
    assert tail.count(".click(") == 1, (
        f"the mint-loop probe must click '⚡ Mint via Lightning' exactly once, got {tail.count('.click(')}"
    )


# ── Contract 3: presence-only mint policy ──────────────────────────────


def test_never_clicks_mint_button(source):
    """The KPI must NEVER click any mint button (presence-only logging).

    Since ae3a162 the 'Mint (1 Star)' button is buy_stars with an
    optimistic _record_mint — a click on production would FABRICATE
    mint_count and poison the North Star metric. Also forbidden on a
    '.click(' line: the '⚡ MINT ·' mint-area label, "I've paid"
    ('✅ I've paid — verify'), and the dead F3 gate 'Pay with Lightning'.
    Counting them ('.count()') is allowed and required.
    """
    for lineno, line in enumerate(source.splitlines(), start=1):
        if ".click(" not in line:
            continue
        for label in _FORBIDDEN_CLICK_LABELS:
            assert label not in line, (
                f"line {lineno}: forbidden click detected — '.click(' on the same "
                f"line as {label!r}: {line.strip()!r}"
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


# ── Contract 5: run-unique probe thought (M7 pre-loop mint-loop probe) ─


def test_probe_thought_is_run_unique_timestamped(source):
    """The pre-loop mint-loop probe thought must be run-unique + plausible.

    The 12 THOUGHTS are already seeded on prod, so a summon of any of them
    hits the dedup guard (find_seed -> _present_existing_creature) and
    never reaches the fresh-summon path where can_mint is computed — the
    creature-card MINT area never renders on a dedup round. The probe
    thought must be run-unique — a millisecond time.time() stamp with a
    'мысль странника' prefix (a plausible Russian player thought, so the
    creature born is a real, presentable creature, not a junk label) — so
    dedup cannot match it and a REAL new summon happens.
    """
    assert "мысль странника" in source, (
        "probe thought prefix 'мысль странника' missing — run-unique thought reverted?"
    )
    assert "time.time()" in source, (
        "no time.time() timestamp in the probe thought generator — "
        "run-uniqueness broken, dedup would swallow the probe on prod"
    )
    assert "probe_seed_created" in source, (
        "probe_seed_created flag missing — honest note that the probe "
        "creates ONE real seed on prod per run was dropped?"
    )


def test_probe_parses_invoice_status_markers(source):
    """The probe must parse the three invoice agent_message markers.

    mint_lightning()/pay_lightning() set exactly these agent_message
    markers in terramon_tma.py: Alby Hub configured -> '⚡ Invoice ready',
    not configured -> '⚡ Lightning not configured yet', exception ->
    '⚡ Invoice failed'. The probe records which one appeared (invoice_ok /
    invoice_msg) — that is the M7 answer to "is Alby Hub configured on
    prod?".
    """
    for marker in (
        "⚡ Invoice ready",
        "⚡ Lightning not configured yet",
        "⚡ Invoice failed",
    ):
        assert marker in source, (
            f"invoice status marker {marker!r} missing from the probe parser"
        )
    assert "invoice_ok" in source and "invoice_msg" in source, (
        "probe evidence fields invoice_ok/invoice_msg missing"
    )


def test_mint_lightning_probe_clicks_exactly_once(source):
    """The pre-loop mint-loop probe must click '⚡ Mint via Lightning' once.

    The probe clicks the mint-lightning button at most once and only when
    the '⚡ MINT ·' mint area is present — invoice creation only: no
    payment, no mint record (minting happens only on settle via
    verify_lightning). No '.click(' line may share text with a mint-area
    label, 'Mint (1 Star)', "I've paid", or the dead F3 gate 'Pay with
    Lightning' (see Contract 2).
    """
    for lineno, line in enumerate(source.splitlines(), start=1):
        if ".click(" not in line:
            continue
        for label in _FORBIDDEN_CLICK_LABELS:
            assert label not in line, (
                f"line {lineno}: forbidden click detected — '.click(' on the same "
                f"line as {label!r}: {line.strip()!r}"
            )


def test_mint_loop_probe_fields(source):
    """The M7 probe must record the mint-area evidence fields.

    mint_button_presence (bool: '⚡ MINT ·' in the body text), mint_ui_state
    (which of 'free summon' / 'locked · train more' / 'mint visible' the
    creature card shows — the dedup path never sets can_mint, so the mint
    button is hidden by design there), and alby_configured (the /health
    json field cross-checking the invoice-creation outcome).
    """
    for field in ("mint_button_presence", "mint_ui_state", "alby_configured"):
        assert field in source, (
            f"{field} missing from the M7 probe — mint-loop evidence field reverted?"
        )


# ── Contract 6: M6 share probe (server-side counter) ──────────────────


def test_share_probe_reads_health_share_count(source):
    """The M6 share probe must read share_count from the /health JSON.

    share_creature() records EVERY share attempt on the persisted share
    registry BEFORE the clipboard write, so the server-side /health
    share_count delta is the authoritative M6 signal. Locks: the helper
    exists, /health is hit, and the delta is computed and logged.
    """
    assert "fetch_share_count" in source, (
        "fetch_share_count helper missing — share probe reverted?"
    )
    assert "share_count" in source, (
        "share_count missing — /health share counter not read by the probe"
    )
    assert "/health" in source, (
        "/health endpoint reference missing — probe cannot read the counter"
    )
    assert "share_delta" in source, (
        "share_delta missing — the probe must log the before/after delta"
    )


def test_share_probe_round1_after_summon(source):
    """The share probe runs in round 1 on the Care tab, only when has_summoned.

    share_creature() itself returns early when has_summoned is False, so
    clicking '📤 Share' before a successful summon would be a no-op — the
    probe guards on the same flag and only clicks the button on the Care
    tab in round 1 (server-side counter is what matters; clipboard errors
    are caught and non-fatal).
    """
    assert "has_summoned" in source, (
        "has_summoned flag missing — share probe must only run after a real summon"
    )
    assert "round_no == 1 and has_summoned" in source, (
        "share probe gate 'round_no == 1 and has_summoned' missing"
    )
    assert "button:has-text('📤 Share')" in source, (
        "'📤 Share' button selector missing from the probe"
    )
    assert "clipboard_error" in source, (
        "clipboard exceptions must be caught and logged (non-fatal) — "
        "the server-side counter is what matters"
    )
