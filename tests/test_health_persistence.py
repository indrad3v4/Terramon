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

import json
import re
import sys
import types
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


# ── 6: DATA_PERSISTED is age-based (memory older than the boot marker) ──


def test_data_persisted_age_based(source):
    """iter-15: DATA_PERSISTED must be TRUE only when the memory file is
    OLDER than the current boot marker (st_mtime comparison) — the marker's
    mere existence is not enough, because every boot rewrites it."""
    region = _boot_marker_region(source)
    assert "_MEMORY_PATH.stat().st_mtime" in region, (
        "boot-marker block does not stat _MEMORY_PATH via st_mtime — "
        "возраст файла памяти не проверяется"
    )
    assert "_BOOT_MARKER.stat().st_mtime" in region, (
        "boot-marker block does not stat _BOOT_MARKER via st_mtime — "
        "возраст boot-маркера не сравнивается"
    )
    assert "DATA_PERSISTED = _data_older" in region, (
        "DATA_PERSISTED must be assigned from the age comparison "
        "(_data_older) — одного существования маркера недостаточно"
    )


# ── 7: previous-boot marker mtime is captured BEFORE overwrite (iter-16) ─


def test_prev_marker_mtime_captured_before_overwrite(source):
    """iter-16: the age check must compare the memory file against the
    PREVIOUS boot's marker mtime, captured BEFORE os.replace overwrites it.
    Rationale: data/boot_epoch.json used to be baked into the Docker image
    (build context), so on a wiped volume the marker still exists and
    JsonMemory.__init__ recreates an EMPTY memory file — the old 'memory
    older than the freshly written marker' check then reported
    DATA_PERSISTED=True with 0 seeds (prod 2026-08-10: seed_count 19→0 with
    data_persisted=true). 'Memory older than the PREVIOUS marker' cannot be
    true for a file recreated at this boot."""
    region = _boot_marker_region(source)
    assert "_prev_marker_mtime" in region, (
        "no previous-marker mtime capture ('_prev_marker_mtime') in "
        "boot-marker block"
    )
    # the capture must stat the PREVIOUS marker, before os.replace rewrites it
    assert "_BOOT_MARKER.stat().st_mtime" in region, (
        "previous-marker capture must stat _BOOT_MARKER (st_mtime)"
    )
    assert "os.replace(" in region, "no 'os.replace(' in boot-marker block"
    assert region.find("_prev_marker_mtime") < region.find("os.replace("), (
        "previous-marker mtime must be read BEFORE os.replace overwrites "
        "the marker"
    )
    # the age check must compare memory mtime against the PREVIOUS marker,
    # never against a freshly (re)written marker
    assert "_MEMORY_PATH.stat().st_mtime < _prev_marker_mtime" in region, (
        "age check must compare memory mtime against _prev_marker_mtime "
        "(previous boot's marker), not a fresh marker stat"
    )
    # NAME-marker proximity convention, same as guard 1
    mem_idx = source.find(MEMORY_PATH_MARKER)
    prev_idx = source.find("_prev_marker_mtime")
    assert 0 <= prev_idx - mem_idx <= PROXIMITY, (
        f"previous-marker capture too far from '{MEMORY_PATH_MARKER}' "
        f"({prev_idx - mem_idx} chars away)"
    )


# ── 8: marker is excluded from the Docker build context (iter-16) ───────


def test_dockerignore_excludes_boot_epoch_marker():
    """iter-16: data/boot_epoch.json must be excluded from the Docker build
    context (.dockerignore). While only data/*.jsonl was ignored, the local
    marker file got baked into the image at /app/data/boot_epoch.json and a
    wiped volume still 'saw' it — the root cause of the prod false positive
    (seed_count 19→0 with data_persisted=true, 2026-08-10)."""
    dockerignore = Path(__file__).resolve().parents[1] / ".dockerignore"
    assert dockerignore.is_file(), f"repo .dockerignore not found: {dockerignore}"
    text = dockerignore.read_text(encoding="utf-8")
    assert "boot_epoch.json" in text, (
        ".dockerignore must exclude data/boot_epoch.json (image-baked marker "
        "false positive)"
    )
    # the pre-existing exclusions must stay intact (negation survives)
    assert "data/*.jsonl" in text, ".dockerignore lost the 'data/*.jsonl' line"
    assert "!data/.gitkeep" in text, (
        ".dockerignore lost the '!data/.gitkeep' negation"
    )


# ── 9: /health D7 cohort + kill-condition (getattr-degradable) ─────────


class _FakeMemory:
    """Stub JsonMemory for RUNTIME /health tests (no data dir, no I/O).

    ``d7_cohort_stats`` / ``days_since_last_mint`` / ``days_since_first_seed``
    model the parallel-task methods that may not exist on the real
    JsonMemory yet — the missing-method test deletes them via monkeypatch
    to lock the graceful-degradation contract (keys None,
    kill_condition.triggered False, never a 500). ``share_count`` /
    ``seed_count`` let tests exercise the share-per-summon funnel.
    """

    def __init__(
        self,
        d7_stats=None,
        days_since_last_mint=None,
        days_since_first_seed=None,
        share_count=0,
        seed_count=0,
    ):
        self._d7_stats = d7_stats
        self._days_since_last_mint = days_since_last_mint
        self._days_since_first_seed = days_since_first_seed
        self._share_count = share_count
        self._seed_count = seed_count

    def load_all_seeds(self):
        return [object() for _ in range(self._seed_count)]

    def count_unique_players(self):
        return 0

    def count_returning_players(self, days=7):
        return 0

    def count_shares(self):
        return self._share_count

    def count_shares_since(self, days=7):
        return 0

    def d7_cohort_stats(self, days=7):
        return self._d7_stats

    def days_since_last_mint(self):
        return self._days_since_last_mint

    def days_since_first_seed(self):
        return self._days_since_first_seed


def _exec_health(memory) -> dict:
    """Run the REAL health() source against a stub module namespace.

    The app module is never imported (module-level Reflex app
    construction); instead the function source is exec'd with a fake
    module registered in sys.modules so the ``sys.modules.get(__name__)``
    snapshot-restore lookups resolve. Returns the parsed JSON body.
    """
    func_src = "\n".join(
        _top_level_func_lines(SOURCE.read_text(encoding="utf-8"), "health")
    )
    mod_name = "terramon_tma_health_under_test"
    fake_mod = types.ModuleType(mod_name)
    fake_mod.DATA_PERSISTED = True
    fake_mod._SNAPSHOT_RESTORED = False
    fake_mod._RESTORED_COUNTS = {}
    fake_mod._SNAPSHOT_TS = ""
    sys.modules[mod_name] = fake_mod
    try:
        namespace = {
            "__name__": mod_name,
            "DATA_PERSISTED": True,
            "_MEMORY": memory,
            "_ALBY": types.SimpleNamespace(url=None, api_key=None),
            "sys": sys,
        }
        exec(compile(func_src, "<health>", "exec"), namespace)
        return json.loads(namespace["health"](None).body)
    finally:
        sys.modules.pop(mod_name, None)


def test_health_reports_d7_kill_condition_keys(source):
    """health() must surface the D7 cohort fields + kill-condition block
    with EXACT key names, read via getattr + callable fallback so a
    JsonMemory without the parallel-task methods degrades to None/False
    instead of crashing /health."""
    health = "\n".join(_top_level_func_lines(source, "health"))
    for key in (
        '"d7_eligible": (d7_stats or {}).get("eligible")',
        '"d7_retained": (d7_stats or {}).get("retained")',
        '"d7_retention": (d7_stats or {}).get("retention_rate")',
        '"days_since_last_mint": days_since_last_mint',
        '"kill_condition": {',
        '"days_mint_zero": days_mint_zero',
        '"share_rate": share_rate',
        '"triggered": bool(',
    ):
        assert key in health, f"health() JSON missing {key!r}"
    # getattr fallback wiring for the parallel-task methods, plus the
    # degraded defaults (inner try/except AND the outer except branch).
    assert 'getattr(_MEMORY, "d7_cohort_stats", None)' in health
    assert 'getattr(_MEMORY, "days_since_last_mint", None)' in health
    assert 'getattr(_MEMORY, "days_since_first_seed", None)' in health
    assert health.count("d7_stats = None") >= 2
    assert "days_since_last_mint = None" in health
    assert "days_since_first_seed = None" in health
    # Kill-clock fallback: with no mint ever, days_mint_zero anchors to
    # days_since_first_seed; share_rate is the lifetime share-per-summon
    # funnel and None only when there are no summoners.
    assert (
        "days_since_last_mint if days_since_last_mint is not None else days_since_first_seed"
        in health
    )
    assert "(share_count / seed_count) if seed_count > 0 else None" in health


def test_health_d7_stats_flow():
    """/health happy path: d7_eligible/retained/retention come from
    _MEMORY.d7_cohort_stats(days=7); days_since_last_mint from
    _MEMORY.days_since_last_mint(); kill_condition NOT triggered < 30."""
    mem = _FakeMemory(
        d7_stats={"eligible": 12, "retained": 5, "retention_rate": 0.4167},
        days_since_last_mint=4,
    )
    data = _exec_health(mem)
    assert data["status"] == "ok"
    assert data["d7_eligible"] == 12
    assert data["d7_retained"] == 5
    assert data["d7_retention"] == 0.4167
    assert data["days_since_last_mint"] == 4
    assert data["kill_condition"] == {
        "days_mint_zero": 4,
        "share_rate": None,
        "triggered": False,
    }


def test_health_d7_missing_methods_degrade(monkeypatch):
    """JsonMemory WITHOUT d7_cohort_stats/days_since_last_mint (parallel
    task not landed yet): /health must still return ok — D7 keys read None
    and kill_condition.triggered is False, never a 500."""
    mem = _FakeMemory()
    monkeypatch.delattr(_FakeMemory, "d7_cohort_stats")
    monkeypatch.delattr(_FakeMemory, "days_since_last_mint")
    data = _exec_health(mem)
    assert data["status"] == "ok"
    assert data["d7_eligible"] is None
    assert data["d7_retained"] is None
    assert data["d7_retention"] is None
    assert data["days_since_last_mint"] is None
    assert data["kill_condition"] == {
        "days_mint_zero": None,
        "share_rate": None,
        "triggered": False,
    }


def test_health_kill_condition_triggered_at_30_days():
    """The kill-condition fires exactly when days_since_last_mint >= 30."""
    assert (
        _exec_health(_FakeMemory(days_since_last_mint=30))["kill_condition"]["triggered"]
        is True
    )
    assert (
        _exec_health(_FakeMemory(days_since_last_mint=31))["kill_condition"]["triggered"]
        is True
    )
    assert (
        _exec_health(_FakeMemory(days_since_last_mint=29))["kill_condition"]["triggered"]
        is False
    )
    assert (
        _exec_health(_FakeMemory(days_since_last_mint=0))["kill_condition"]["triggered"]
        is False
    )


def test_health_kill_clock_anchors_to_first_seed_when_no_mint():
    """No mint has EVER happened (days_since_last_mint None): the 30-day
    kill clock anchors to days_since_first_seed (first summon / game
    launch) so it can still fire; stays None only with no mint AND no
    seed at all."""
    data = _exec_health(
        _FakeMemory(days_since_last_mint=None, days_since_first_seed=12)
    )
    assert data["kill_condition"] == {
        "days_mint_zero": 12,
        "share_rate": None,
        "triggered": False,
    }
    data = _exec_health(
        _FakeMemory(days_since_last_mint=None, days_since_first_seed=31)
    )
    assert data["kill_condition"] == {
        "days_mint_zero": 31,
        "share_rate": None,
        "triggered": True,
    }


def test_health_share_rate_computed():
    """share_rate = lifetime share-per-summon funnel (share_count /
    seed_count); None when there are no summoners (seed_count == 0)."""
    data = _exec_health(
        _FakeMemory(days_since_last_mint=None, share_count=3, seed_count=21)
    )
    assert data["share_count"] == 3
    assert data["seed_count"] == 21
    assert data["kill_condition"]["share_rate"] == 3 / 21
    assert data["kill_condition"]["days_mint_zero"] is None
    assert data["kill_condition"]["triggered"] is False
    # No summoners at all -> no funnel rate (and no kill clock).
    data = _exec_health(_FakeMemory())
    assert data["kill_condition"]["share_rate"] is None
