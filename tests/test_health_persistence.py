"""Data-persistence self-check regression guards (offline, source-level).

A parallel change adds a boot-epoch persistence marker to the TMA app so
the KPI monitor can SEE when the Railway volume (terramon-data @
/app/data) is NOT attached. Evidence: an iter-13 KPI run showed prod
seed_count going 2 → 0 across a redeploy even though railway.json declares
deploy.volumes — the volume is evidently not attached, so the whole data/
dir (tma_memory.jsonl, beliefs.jsonl, players.jsonl, shares.jsonl) resets
on every deploy and silently zeroes mint_count / share_count /
player_count (M6/M7/M8 + the kill-condition monitor).

The fix: at module level, next to ``_MEMORY_PATH``, the app checks whether
``data/boot_epoch.json`` survived the previous boot (DATA_PERSISTED) and
atomically rewrites it with a fresh boot id. /health reports
``data_persisted`` so the monitor can tell 'no players' apart from
'data wiped on redeploy'.

Like test_mint_funnel_home.py / test_gate_regression.py, the app module
is NEVER imported: importing terramon_tma executes Reflex app
construction at module level (app assembly / page registration with
browser-side effects). Everything here is pure offline: pathlib text
reading of the source, located by NAME markers — never by line number,
because the file is edited in parallel and offsets shift.
"""

import re
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "terramon_tma" / "terramon_tma.py"

MEMORY_PATH_MARKER = '_MEMORY_PATH = Path("data/tma_memory.jsonl")'
MEMORY_BLOCK_END_MARKER = "# ── Player identity (D7 retention cohorts)"
BOOT_MARKER_FILENAME = "boot_epoch.json"
PROXIMITY = 3000  # chars after _MEMORY_PATH line the boot marker must live in


@pytest.fixture(scope="module")
def source() -> str:
    """The real TMA source, read fresh from disk as TEXT on every run (read-only)."""
    if not SOURCE.is_file():
        pytest.fail(f"app source not found: {SOURCE}")
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


def _boot_marker_region(source: str) -> str:
    """The module-level boot-marker block: text strictly BETWEEN the
    ``_MEMORY_PATH = ...`` line and the '# ── Player identity' comment
    (both boundary lines excluded)."""
    lines = source.splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if MEMORY_PATH_MARKER in ln),
        None,
    )
    end = next(
        (i for i, ln in enumerate(lines) if MEMORY_BLOCK_END_MARKER in ln),
        None,
    )
    if start is None:
        pytest.fail(f"'{MEMORY_PATH_MARKER}' not found in source")
    if end is None:
        pytest.fail(f"'{MEMORY_BLOCK_END_MARKER}' not found in source")
    if not start < end:
        pytest.fail("'Player identity' marker appears before '_MEMORY_PATH' in source")
    return "\n".join(lines[start + 1 : end])


# ── 1: boot-epoch marker lives right next to _MEMORY_PATH ─────────────


def test_boot_epoch_marker_near_memory_path(source):
    """The 'boot_epoch.json' marker filename must appear in the module-level
    block immediately after _MEMORY_PATH — i.e. in the persistent-memory
    section, not anywhere else in the file."""
    region = _boot_marker_region(source)
    assert BOOT_MARKER_FILENAME in region, (
        f"'{BOOT_MARKER_FILENAME}' not found in the module-level block "
        f"right after {MEMORY_PATH_MARKER}"
    )
    # belt-and-braces: it must be within PROXIMITY chars of _MEMORY_PATH
    mem_idx = source.find(MEMORY_PATH_MARKER)
    marker_idx = source.find(BOOT_MARKER_FILENAME)
    assert 0 <= marker_idx - mem_idx <= PROXIMITY, (
        f"'{BOOT_MARKER_FILENAME}' too far from '{MEMORY_PATH_MARKER}' "
        f"({marker_idx - mem_idx} chars away)"
    )


# ── 2: marker write is atomic (tmp file + os.replace) ─────────────────


def test_boot_epoch_marker_atomic_write(source):
    """The marker must be written atomically: a tmp path + os.replace, so a
    crash mid-write can never leave a half-written boot_epoch.json."""
    region = _boot_marker_region(source)
    assert "os.replace(" in region, (
        "atomic rename via 'os.replace(' not found in boot-marker block"
    )
    assert ".tmp" in region, (
        "no tmp-file path ('*.tmp') found in boot-marker block — marker "
        "write is not atomic"
    )


# ── 3: marker I/O is guarded (try/except, DATA_PERSISTED=False on fail) ─


def test_boot_epoch_marker_io_guarded(source):
    """Marker I/O must be wrapped in try/except so a read-only or missing
    data dir can never crash the app at import time; on failure
    DATA_PERSISTED must be False."""
    region = _boot_marker_region(source)
    assert "try:" in region, "no 'try:' guard around boot-marker I/O"
    assert "except" in region, "no 'except' guard around boot-marker I/O"
    assert "DATA_PERSISTED = False" in region, (
        "no 'DATA_PERSISTED = False' fallback in boot-marker block"
    )


# ── 4: marker records a boot id (uuid / time-based) + timestamp ────────


def test_boot_epoch_marker_records_boot_id(source):
    """Each boot must stamp a fresh identity (uuid4 hex here) plus an ISO
    boot_time and the 'survived' flag, so the monitor can correlate a
    boot_id with the reported data_persisted value."""
    region = _boot_marker_region(source)
    assert "boot_id" in region, "no 'boot_id' key in boot-marker block"
    assert "uuid" in region, (
        "no uuid-based boot id in boot-marker block (uuid4.hex expected)"
    )
    assert "boot_time" in region, "no 'boot_time' key in boot-marker block"
    assert "survived" in region, "no 'survived' key in boot-marker block"


# ── 5: /health reports data_persisted ─────────────────────────────────


def test_health_reports_data_persisted(source):
    """The health() endpoint must surface 'data_persisted' (module-level
    DATA_PERSISTED in the happy path, False in the except branch) so the
    KPI monitor can SEE a wiped data dir instead of reading it as
    'no players'."""
    health = "\n".join(_top_level_func_lines(source, "health"))
    assert "data_persisted" in health, (
        "'data_persisted' not found in health() body"
    )
    assert '"data_persisted": data_persisted' in health, (
        "health() JSON response missing '\"data_persisted\": data_persisted'"
    )
    assert "data_persisted = DATA_PERSISTED" in health, (
        "health() happy path does not read module-level DATA_PERSISTED"
    )
    assert "data_persisted = False" in health, (
        "health() except branch does not fall back to data_persisted = False"
    )
