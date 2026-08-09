"""Win-path contract guards for scripts/kpi/play_to_win.py (offline, source-level).

The KPI Playwright player's *win path* is: for each of the 12 THOUGHTS,
summon a creature, and the 12 summons must yield 12 DISTINCT archetypes —
that is the whole point of the run (``distinct_archetypes: 12``). These
guards lock that contract so a future edit cannot silently break it:

  1. Thought/archetype 1:1 mapping — the 12 THOUGHTS texts must classify
     (via terramon.adapters.embedding_classifier.EmbeddingClassifier, the
     same pure-stdlib model the game uses) to exactly the 12 distinct
     archetypes, i.e. the full archetype universe. Duplicate thoughts or
     ambiguous thought texts would stall collection below 12 and must fail.
  2. No mint-button click — the script must never click the 'Mint (1 Star)'
     gate inside wait_result() (the old ``gate_clicked`` flow). Minting a
     duplicate of an already-collected archetype wastes a round and breaks
     the 1:1 mapping; the win path is presence-only for minting.
  3. Care re-check block — the Care-tab re-read that collects
     ``map_imgs_after_care`` / ``m2_after_care`` (M1/M2 evidence path,
     independent of the summon view state) must stay in the script.

Like test_iter6_regression.py, the KPI module is NEVER imported — it has a
module-level Playwright block (``with sync_playwright()``) that would launch
a browser. Everything here is pure offline: pathlib text reading plus the
EmbeddingClassifier (pure stdlib: hashed TF-IDF + centroids, deterministic).
"""

import re
from pathlib import Path

import pytest

from terramon.adapters.embedding_classifier import EmbeddingClassifier

KPI_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "kpi" / "play_to_win.py"

EXPECTED_THOUGHT_COUNT = 12


@pytest.fixture(scope="module")
def kpi_source() -> str:
    """The real KPI script, read fresh from disk as TEXT on every run (read-only)."""
    if not KPI_SCRIPT.is_file():
        pytest.fail(f"KPI script not found: {KPI_SCRIPT}")
    return KPI_SCRIPT.read_text(encoding="utf-8")


def _extract_thoughts(source: str) -> list[tuple[str, str]]:
    """Extract the (archetype, thought) tuples from the THOUGHTS = [...] block.

    Anchored to the 'THOUGHTS = [' literal so the regex never matches the
    other string lists in the file (ARCHETYPES, DISMISS). The thought texts
    contain no double quotes, so ``"([^"]+)"`` is safe.
    """
    marker = "THOUGHTS = ["
    start = source.index(marker) + len(marker)
    end = source.index("]", start)  # closing bracket of the THOUGHTS list
    block = source[start:end]
    return re.findall(r'\(\s*"([A-Za-z]+)",\s*"([^"]+)"\s*\)', block)


def _mint_click_proximity_hits(source: str, window: int = 200) -> list[int]:
    """Start indexes of every 'Mint (1 Star)' that has a '.click(' within *window* chars.

    The button label legitimately appears in the script (the app renders it);
    what the win path forbids is CLICKING it. An empty list = no mint click.
    """
    hits = []
    for m in re.finditer(r"Mint \(1 Star\)", source):
        if ".click(" in source[m.end(): m.end() + window]:
            hits.append(m.start())
    return hits


# ── Test 1 (core): the 12 THOUGHTS map 1:1 to the 12 archetypes ─────────


def test_thoughts_classify_to_12_distinct_archetypes(kpi_source):
    """Win-path core: 12 thoughts -> 12 distinct archetypes == the full universe.

    If the classifier maps two thoughts onto the same archetype (duplicate
    thought texts, or texts too ambiguous to separate), the run can never
    collect all 12 and the KPI stalls — that is the regression this guards.
    """
    thoughts = _extract_thoughts(kpi_source)
    assert len(thoughts) == EXPECTED_THOUGHT_COUNT, (
        f"expected {EXPECTED_THOUGHT_COUNT} THOUGHTS tuples, got {len(thoughts)}"
    )

    clf = EmbeddingClassifier()
    # ARCHETYPES is a dict[str, list[str]] (archetype -> training phrases);
    # its keys are the archetype universe — the source of truth, not a
    # hardcoded list, so the test tracks the model's real vocabulary.
    universe = set(clf.ARCHETYPES)
    assert len(universe) == EXPECTED_THOUGHT_COUNT, (
        f"classifier universe must have {EXPECTED_THOUGHT_COUNT} archetypes, got {len(universe)}"
    )

    results = [clf.classify(text) for _, text in thoughts]
    assert len(set(results)) == EXPECTED_THOUGHT_COUNT, (
        "THOUGHTS do not classify to 12 DISTINCT archetypes — duplicate/ambiguous "
        f"thought texts stall the win path. Got: {results}"
    )
    assert set(results) == universe, (
        "THOUGHTS do not cover the full archetype universe — missing: "
        f"{sorted(universe - set(results))}"
    )


# ── Test 2: the script never clicks a mint button ───────────────────────


def test_no_mint_button_click(kpi_source):
    """Win-path guard: 'Mint (1 Star)' must never be clicked.

    The old wait_result() flow clicked the mint gate once (``gate_clicked``)
    to force a duplicate summon of an already-collected archetype — which
    breaks the 1:1 mapping and wastes rounds. The agreed contract: presence
    only, never click. Two independent checks:

      * the ``gate_clicked`` variable is gone entirely;
      * no 'Mint (1 Star)' occurrence is followed within 200 chars by '.click('.
    """
    assert "gate_clicked" not in kpi_source, (
        "gate_clicked still present — wait_result() can still click the mint gate"
    )
    hits = _mint_click_proximity_hits(kpi_source)
    assert not hits, (
        "'Mint (1 Star)' followed by '.click(' at char offset(s) "
        f"{hits} — the win path must never click the mint button"
    )


def test_wait_result_has_no_mint_click(kpi_source):
    """Targeted check on the wait_result() function body itself.

    Even if the proximity window above is ever relaxed, wait_result() must
    not contain the mint label next to a click call at all.
    """
    m = re.search(r"def wait_result\(page\):(.*?)(?=\ndef |\Z)", kpi_source, re.DOTALL)
    assert m, "wait_result() function not found in the KPI script"
    body = m.group(1)
    assert "gate_clicked" not in body, "wait_result() still contains the gate_clicked mint-click flow"
    # The label may legitimately appear in a policy COMMENT inside the
    # function; what the contract forbids is a CLICK on it. Reuse the
    # proximity check on the function body: no '.click(' within 200 chars
    # after any 'Mint (1 Star)' occurrence.
    hits = _mint_click_proximity_hits(body)
    assert not hits, (
        "wait_result() clicks the mint button — 'Mint (1 Star)' followed by "
        f"'.click(' at char offset(s) {hits} (relative to function body)"
    )


# ── Test 3: the Care re-check block (M1/M2 evidence path) stays ─────────


def test_care_recheck_evidence_block_present(kpi_source):
    """The Care-tab re-check that collects main-card M2 evidence must stay.

    After a successful summon the script re-reads the Care tab to gather
    ``map_imgs_after_care`` (static-map / yandex imgs) into
    ``rlog['m2_after_care']`` — M2 evidence independent of the summon view
    state (works even when the celebration overlay is up).
    """
    assert "m2_after_care" in kpi_source, (
        "rlog['m2_after_care'] assignment missing — Care re-check block was removed"
    )
    assert "map_imgs_after_care" in kpi_source, (
        "map_imgs_after_care collection missing — Care re-check block was removed"
    )
