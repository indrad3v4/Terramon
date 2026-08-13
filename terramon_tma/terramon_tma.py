"""Terramon TMA — Reflex app with AGENTIC loop + polished UI.

UI/UX SINS FIXED (July 2026, after ccgs-p + prism audit):
  SIN 1 — SUMMON has no "juice" (no loading, no glow, no feedback)
    FIX: amber-branded button, scale-on-hover via style, loading state text
  SIN 2 — Flat black background feels dead
    FIX: subtle gradient background + ambient aura glow on card
  SIN 3 — Empty state hook too dim (#d8b4fe on #0b0b0f)
    FIX: brighter text (#c4b5fd) + subtle box-shadow aura behind hook
  SIN 4 — No creature image shown on card
    FIX: FAL portrait rendered on the main card + terra grid (Lesson 13:
    the portrait is the thought vector made visible). /creature-art route
    serves data/creatures/*.png; the sigil stays as fallback while art is
    still generating (bounded rx.moment poller, mirrors the lightning one).
  SIN 5 — CAPTURE and SUMMON same visual weight
    FIX: CAPTURE = outline variant, SUMMON = solid amber primary
  SIN 6 — XP bar is flat (no transition/animation)
    FIX: inline style width-transition via style prop
  SIN 7 — Terra grid cards have no hover state
    FIX: CSS "transform: scale(1.02)" transition on hover
  SIN 8 — MINT button has no explanation
    FIX: tooltip on hover explaining Stars ⚡ minting
  SIN 9 — Creature card appears instantly (no animation)
    FIX: animated fade-in via style opacity
  SIN 10 — Flat typography hierarchy
    FIX: clear size hierarchy (heading > progress > insight > stats)
  SIN 11 — Goal-reached celebration too subtle
    FIX: gold border glow + emoji sparkle
  SIN 12 — First-time user guidance missing
    FIX: guided tip below SUMMON: "Write how you feel. The creature becomes."
"""

from __future__ import annotations

import json, logging, os, sys, traceback, uuid

# Logging setup — writes to stderr (visible in Railway logs)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
    force=True,
)
log = logging.getLogger("terramon")

import reflex as rx
from pathlib import Path

import segno

from terramon.adapters.portrait_serve import creature_art_url, portrait_file_path
from terramon.adapters.embedding_classifier import EmbeddingClassifier
from terramon.adapters.alby_hub_adapter import AlbyHubAdapter
from terramon.adapters.json_memory import JsonMemory
from terramon.adapters.durability import restore_counters_if_wiped
from terramon.adapters.static_map import (
    render_static_map,
    static_map_endpoint_path,
)
from terramon.application.game_loop import GameLoop, TurnResult
from terramon.application.geo_tournament import GeoTournamentService
from terramon.application.summon_service import SummonService
from terramon.domain.progress import PlayerProgress, XP_BY_RARITY
from terramon.domain.rarity import (
    Rarity,
    RITUAL_RELEASE_SATS,
    RITUAL_RELEASE_STARS,
    lightning_mint_price,
)
from terramon.domain.thought_seed import ThoughtSeed
from terramon.events.bus import EventBus
from terramon.application.insight_engine import _scores, _THEMES
from terramon.application.agent_service import AgentService
from terramon.application.llm_behavior import set_api_key as _init_llm
from terramon.domain.creature_agent import CreatureAgent
from terramon.domain.candle import (
    CANDLE_PRICE_SATS,
    candle_js,
    candle_lore_for,
    candle_outcome,
    persist_candle_lore,
    seed_is_released,
)
from terramon.domain.insight import GeoContext, Insight
from terramon.domain.player import PlayerIdentity
from tools.time_tool import get_current_time

# ── G05: Geo-capture support (Telegram LocationButton → geolocation API) ──
# Returns {lat, lon} from the Telegram native location picker when inside a
# Mini App, else falls back to the browser geolocation API. Wrapped in a
# Promise with a 60 s timeout; resolves null on denial/timeout (degraded
# path: the creature is born "в неизвестном месте").
_LOCATION_JS = '''(async () => {
  const tg = window.Telegram?.WebApp;
  if (tg && tg.LocationButton) {
    tg.LocationButton.show();
    return await new Promise((resolve) => {
      const t = setTimeout(() => { tg.LocationButton.hide(); resolve(null); }, 60000);
      tg.onEvent('location_accessed', (loc) => {
        clearTimeout(t); tg.LocationButton.hide();
        resolve({ lat: loc.latitude, lon: loc.longitude });
      });
    });
  }
  return await new Promise((resolve) => {
    if (!navigator.geolocation) return resolve(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
      () => resolve(null),
      { timeout: 10000, maximumAge: 300000 });
  });
})()'''


# ── Stars ritual rail (payment-gated, cf. nikandr-surkov/telegram-mini-app-
# stars-payments OSS reference): openInvoice callback → 'paid' | 'cancelled'
# | 'failed' | 'unavailable'. The reward (complete_releases) is granted
# ONLY in the 'paid' branch — never optimistically on button click. The
# invoice URL is injected at call time (token __INVOICE_URL__) so
# TERRAMON_STARS_INVOICE_URL is honoured.
_RITUAL_STARS_JS = '''(async () => {
  const tg = window.Telegram?.WebApp;
  if (!tg || !tg.openInvoice) return 'unavailable';
  return await new Promise((resolve) => {
    try {
      tg.openInvoice('__INVOICE_URL__', (status) => resolve(
        status === 'paid' ? 'paid' :
        (status === 'cancelled' ? 'cancelled' : 'failed')
      ));
    } catch (e) {
      resolve('unavailable');
    }
  });
})()'''


# ── Player identity capture: read Telegram.WebApp.initData (raw, signed) ──
# Runs on every app open (load_terra). Empty string when not inside a TMA —
# the anon fallback path, never a crash. The raw string is verified server-side
# (HMAC-SHA256 vs the bot token) before any identity is trusted.
_INITDATA_JS = (
    "(() => {"
    "try { return (window.Telegram && window.Telegram.WebApp && "
    "window.Telegram.WebApp.initData) ? String(window.Telegram.WebApp.initData) : ''; }"
    "catch (e) { return ''; }"
    "})()"
)


def _validate_coords(coords) -> tuple[float | None, float | None]:
    """None-safe lat/lon validation (-90..90 / -180..180). Garbage → (None, None)."""
    try:
        lat = float(coords["lat"])
        lon = float(coords["lon"])
    except (TypeError, ValueError, KeyError):
        return None, None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None, None
    return lat, lon


# Initialize LLM-powered creature behavior from env
import os
_llm_key = os.environ.get("OPENROUTER_API_KEY", "")
if not _llm_key:
    log.warning(
        "OPENROUTER_API_KEY not set — creature LLM responses will be disabled. "
        "Set it in .env or Railway environment variables."
    )
_init_llm(_llm_key)


# One classifier instance (prototypes precomputed once).
_CLASSIFIER = EmbeddingClassifier()

# Persistent memory — survives sessions (Railway volume mount at data/).
_MEMORY_PATH = Path("data/tma_memory.jsonl")
_MEMORY = JsonMemory(_MEMORY_PATH)

# ── Data-persistence self-check (Railway volume attach honesty) ──────
# railway.json declares deploy.volumes (terramon-data @ /app/data), but
# Railway only attaches volumes created in the project dashboard. When the
# volume is missing, the data/ dir is wiped on EVERY redeploy and
# seed_count/player_count/share_count silently reset to 0 (M6/M7/M8 + the
# kill-condition monitor). This boot-epoch marker survives only if the
# data dir actually persists between boots, so /health can report
# DATA_PERSISTED and the KPI monitor stops reading a wiped data dir as
# 'no players'.
_BOOT_MARKER = Path("data/boot_epoch.json")
DATA_PERSISTED = False
try:
    _boot_survived = _BOOT_MARKER.exists()  # True ⇒ data dir survived last boot
    # iter-16: capture the PREVIOUS boot's marker mtime BEFORE os.replace
    # below overwrites it. Root cause of the prod 2026-08-10 false positive
    # (seed_count 19→0 with data_persisted=true): .dockerignore only excluded
    # data/*.jsonl, so data/boot_epoch.json in the local build context got
    # BAKED INTO the image at /app/data/boot_epoch.json. On a wiped/missing
    # volume the marker still "exists" (image file) and JsonMemory.__init__
    # above already recreated an EMPTY tma_memory.jsonl — comparing that
    # fresh file against the freshly written marker's mtime reported
    # DATA_PERSISTED=True with 0 seeds. Comparing against the PREVIOUS
    # marker's mtime kills the false positive: a memory file recreated THIS
    # boot (or written during the previous session) is never older than the
    # previous boot's marker, so DATA_PERSISTED stays False for a wiped dir.
    _prev_marker_mtime = _BOOT_MARKER.stat().st_mtime if _boot_survived else None
    _BOOT_MARKER.parent.mkdir(parents=True, exist_ok=True)
    _boot_tmp = _BOOT_MARKER.with_name(_BOOT_MARKER.name + ".tmp")
    _boot_tmp.write_text(
        json.dumps(
            {
                "boot_id": uuid.uuid4().hex,
                "boot_time": get_current_time(),
                "survived": _boot_survived,
            },
            indent=2,
        )
    )
    os.replace(_boot_tmp, _BOOT_MARKER)
    # Age-based honesty (iter-15/16): the marker alone is a false positive
    # when the data dir is wiped between boots (marker survives, memory gone).
    # DATA_PERSISTED only when a REAL data file from a previous boot exists —
    # i.e. its mtime is strictly OLDER than the PREVIOUS boot's marker mtime
    # (captured above, before os.replace) — never compared against the new
    # marker, whose fresh mtime would bless a just-recreated empty memory.
    if _boot_survived and _prev_marker_mtime is not None:
        try:
            _data_older = (
                _MEMORY_PATH.exists()
                and _MEMORY_PATH.stat().st_mtime < _prev_marker_mtime
            )
            DATA_PERSISTED = _data_older
        except Exception:
            DATA_PERSISTED = False
    else:
        DATA_PERSISTED = False
except Exception as _boot_err:  # best-effort: never crash the app on marker I/O
    DATA_PERSISTED = False
    log.warning(
        "boot-epoch marker I/O failed (data dir not writable?): %s", _boot_err
    )

# ── Snapshot restore (durability across Railway volume wipes) ──────
# The LOOP snapshots the /health COUNTERS to data/snapshots/latest/
# health.json at ship time (scripts/kpi/snapshot_data.py) and commits it
# to git (.gitignore negations keep data/snapshots/ trackable; the
# .dockerignore only excludes data/*.jsonl, so the snapshot also survives
# into the Docker image). On boot, when data/tma_memory.jsonl is MISSING
# or EMPTY (volume not attached -> wiped on redeploy), restore the real
# counters from that snapshot so the KPI evidence
# (mint_count/share_count/seed_count) survives infra wipes. No fabricated
# data: only the app's own previously-observed counters, clearly labeled
# via data_restored_from_snapshot + restored_* fields in /health.
_SNAPSHOT_RESTORED = False
_RESTORED_COUNTS = {}
_SNAPSHOT_TS = None
try:
    _snap_restore = restore_counters_if_wiped(_MEMORY_PATH)
    _SNAPSHOT_RESTORED = bool(_snap_restore.get("restored"))
    _RESTORED_COUNTS = _snap_restore.get("counts") or {}
    _SNAPSHOT_TS = _snap_restore.get("snapshot_ts")
except Exception as _snap_err:  # best-effort: never crash the app on restore I/O
    _SNAPSHOT_RESTORED = False
    _RESTORED_COUNTS = {}
    _SNAPSHOT_TS = None
    log.warning(
        "snapshot restore check failed (continuing without restore): %s", _snap_err
    )

# ── Player identity (D7 retention cohorts) ──────────────────────────
# The TMA ships initData signed with the BOT token. Verification is pure
# HMAC-SHA256 (terramon.domain.player); with no token configured the app
# keeps working — every session is simply anonymous (auth is additive).
_BOT_TOKEN = os.environ.get("TERRAMON_BOT_TOKEN") or os.environ.get("BOT_TOKEN") or ""
if not _BOT_TOKEN:
    log.warning(
        "TERRAMON_BOT_TOKEN/BOT_TOKEN not set — initData verification disabled, "
        "all sessions will be anonymous (player_count/returning_players_7d stay 0)."
    )

# Telegram Stars invoice for creature minting (Stars rail). openInvoice has
# NO server callback in this MVP — the mint record for this rail is recorded
# OPTIMISTICALLY on click (see mint_creature / buy_stars); Lightning mints
# on settle (verify_lightning).
# TODO(MVP→v1): replace this PLACEHOLDER with the REAL Stars invoice link
# from @BotFather (BotFather → Settings → Payments → Stars). Do NOT invent
# a URL: until then buy_stars/mint_creature keep minting optimistically and
# the guarded openInvoice simply no-ops when Telegram.WebApp is absent.
# Env-overridable (TERRAMON_STARS_INVOICE_URL) — the release ritual's
# payment-gated Stars rail reads the same constant.
_STARS_INVOICE_URL = os.environ.get(
    "TERRAMON_STARS_INVOICE_URL",
    "https://t.me/terramon_bot/TERRAMON_STAR_INVOICE",
)

# F3 gate: price to summon AGAIN after the free first summon. This is a
# FIXED gate price (independent of the current creature's rarity tier) —
# previously the gate showed price_sats of the LAST summoned creature, which
# was 0 for free tiers, so 'Pay with Lightning' clicked and did nothing.
GATE_SUMMON_PRICE_SATS = 3000  # Lightning rail (>= Alby JIT floor 2501)
GATE_SUMMON_STARS = 1          # Telegram Stars rail

# Lightning auto-verify: after an invoice is created the panel polls the
# Alby Hub for settlement every LIGHTNING_VERIFY_INTERVAL_MS via a hidden
# rx.moment periodic callback (the only sane periodic pattern in Reflex
# 0.9.x — no rx.timer). Bounded: after LIGHTNING_VERIFY_MAX_ATTEMPTS
# (~3 min) polling stops and the manual «✅ I've paid — verify» button
# remains as the fallback. A paid mint is never lost: the handler keeps
# polling until settle or gives up with a clear manual-fallback marker.
LIGHTNING_VERIFY_INTERVAL_MS = 6000   # rx.moment tick interval for auto-verify
LIGHTNING_VERIFY_MAX_ATTEMPTS = 30    # ~3 min of auto-polling, then manual fallback
# Release-ritual auto-verify: same bounded poller as the mint gate, but the
# ritual BOLT11 also EXPIRES (~1h Alby Hub default) with no in-app way to
# re-issue it — a dead-end. So the bound hands off to BOTH manual fallbacks:
# «✅ I've paid — verify» and «🔄 Новый инвойс» (refresh_ritual_invoice).
RITUAL_RELEASE_VERIFY_MAX_ATTEMPTS = 30    # ~3 min of ritual auto-polling, then manual verify + invoice refresh fallback

# GameLoop owns progression + reflection; SummonService persists each turn.
_SERVICE = SummonService(
    classifier=_CLASSIFIER,
    memory=_MEMORY,
    bus=EventBus(),  # fire-and-forget; no subscriber needed in TMA
    clock=get_current_time,
)
_TOURNAMENT_SVC = GeoTournamentService()
_LOOP = GameLoop(_SERVICE, PlayerProgress(goal_distinct=5),
                 tournament_service=_TOURNAMENT_SVC)

# Lightning payments — self-custodial Alby Hub node (Railway).
# Reads ALBY_HUB_URL / ALBY_HUB_API_KEY from env; if unset, adapter stays
# unconfigured and the Stars fallback gate is shown instead (BTC-first UI).
_ALBY = AlbyHubAdapter()

# Agent service for creature interaction (Tamagotchi×Pokemon)
_AGENT_SVC = AgentService(_MEMORY)

_RARITY_COLOR = {
    "common": "#9ca3af",
    "uncommon": "#22c55e",
    "rare": "#3b82f6",
    "legendary": "#f59e0b",
}
_RARITY_SIGIL = {
    "common": "·",
    "uncommon": "✦",
    "rare": "✧",
    "legendary": "★",
}
_RARITY_GLOW = {
    "common": "0 0 12px rgba(156,163,175,0.25)",
    "uncommon": "0 0 20px rgba(34,197,94,0.35)",
    "rare": "0 0 28px rgba(59,130,246,0.45)",
    "legendary": "0 0 36px rgba(245,158,11,0.55)",
}
_ARCHETYPE_LORE = {
    "Innocent": "Sees the good. Trusts the world.",
    "Orphan": "Knows what it means to be left out.",
    "Hero": "Rises to meet every challenge.",
    "Caregiver": "Gives without counting the cost.",
    "Explorer": "The horizon is never far enough.",
    "Rebel": "Questions every answer.",
    "Lover": "Connection is the only truth.",
    "Creator": "Builds worlds from nothing.",
    "Jester": "Laughs in the face of the void.",
    "Sage": "Seeks the truth beneath the surface.",
    "Magician": "Transforms the ordinary into the extraordinary.",
    "Ruler": "Brings order to chaos.",
}

# Summon anti-stall (KPI: server-side stall of the LLM path at 01:27 — the
# summon event hung on the LLM call, the state-update never arrived and the
# UI froze on summoning=True forever). These graceful fallbacks guarantee the
# event ALWAYS clears summoning and returns a result, even when the LLM path
# fails or times out: worst case the creature is born with a template greeting.
_SUMMON_GREETING_FALLBACK = "Существо родилось, но молчит."
_SUMMON_FAILURE_MESSAGE = "Что-то пошло не так — существо не родилось. Попробуй ещё раз."


def _reflect_on_memory(seeds: list[ThoughtSeed], new_agent: str) -> str:
    """Agent reflects on the player from memory (schema-driven, no LLM)."""
    if not seeds:
        return "A new presence stirs. The terra is empty; you are its first visitor."
    total = len(seeds)
    agents = [s.summoned_agent for s in seeds]
    from collections import Counter
    common = Counter(agents).most_common(1)[0]
    text = " ".join(s.raw_input.lower() for s in seeds)
    themes = []
    if any(k in text for k in ("rent", "money", "pay", "broke", "work", "job")):
        themes.append("survival & money")
    if any(k in text for k in ("afraid", "fear", "anxious", "scared", "interview")):
        themes.append("fear & the unknown")
    if any(k in text for k in ("love", "friend", "family", "alone", "miss")):
        themes.append("connection")
    theme_txt = ", ".join(themes) if themes else "the quiet ordinary"
    return (
        f"{new_agent} remembers {total} thought(s). "
        f"You summon {common[0]} most often ({common[1]}×). "
        f"Your terra echoes: {theme_txt}."
    )


def _share_code_from_seed(seed) -> str:
    """M6: 8-char share code for the Telegram deep link on the share card.

    Prefers a stored ``share_code`` attribute on the seed; falls back to the
    timestamp-derived code (identical derivation to summon_service's
    AgentSummoned event) so a real creature always gets a deep link. Never
    raises — a missing attribute yields an empty string.
    """
    if seed is None:
        return ""
    code = getattr(seed, "share_code", "") or ""
    if code:
        return code
    ts = getattr(seed, "timestamp", "") or ""
    if ts:
        return ts.replace(":", "").replace("-", "").replace(".", "")[-8:]
    return ""


class TerramonState(rx.State):
    """Backend state — runs in Python, drives the agentic summon loop."""

    thought: str = ""
    agent: str = ""
    rarity: str = ""
    sigil: str = ""
    color: str = "#9ca3af"
    lore: str = ""
    xp: int = 0
    level: int = 1
    distinct: int = 0
    goal: int = 5
    price_sats: int = 0
    has_summoned: bool = False
    goal_reached: bool = False
    reflection: str = ""
    insight: str = ""
    place: str = ""  # v2: geographic anchor — "Kraków, Poland" or "50.06, 19.94"
    share_code: str = ""  # M6: 8-char code for the Telegram deep link on the share card
    intelligence: int = 0
    photo_mode: bool = False
    summoning: bool = False  # animation flag (SIN 1 fix: loading state)
    evolve_animating: bool = False  # evolution animation flag (set by evolve_agent)
    celebration_dismissed: bool = False  # F2: Tamer Unlock celebration dismissed
    celebration_pending: bool = False  # F2: session-only — goal JUST reached in THIS session (never hydrated)

    # B1: LLM-generated creature greeting on summon
    creature_greeting: str = ""
    # B3: last-seen tracking for memory greetings
    last_seen: str = ""
    memory_greeting: str = ""

    # F3 — Monetization Gate: first summon free, then payment required
    summon_count: int = 0
    unlocked: bool = False  # becomes True after payment/unlock
    # Lightning (BTC-first): current BOLT11 invoice + its hub id
    lightning_invoice: str = ""      # BOLT11 string shown to player
    lightning_qr: str = ""           # local data-URI QR for the current BOLT11 invoice
    lightning_price: int = 0         # actual sats price (>= LIGHTNING_MIN_MINT_SATS)
    lightning_ref: str = ""          # hub invoice id for verification
    lightning_checking: bool = False  # in-flight verify flag
    lightning_auto_verify: bool = False  # auto-poll Alby settle after invoice creation
    lightning_verify_attempts: int = 0   # bounded auto-poll tick counter
    invoice_copied: bool = False  # BOLT11 copy feedback flag (reset on every new invoice)

    # M7 — Mint loop (closed): a real mint record on the seed + a counter
    # for analytics. Stars = optimistic mint on click (openInvoice has no
    # server callback); Lightning = mint only when the invoice SETTLES.
    minted: bool = False       # current creature has a real mint record
    minted_at: str = ""        # ISO timestamp of the mint ('' = not minted)
    mint_count: int = 0        # total minted collectibles (synced from seeds)

    # Tamagotchi×Pokemon: creature agent interaction
    selected_agent_id: str = ""
    agent_hunger: int = 0
    agent_energy: int = 0
    agent_happiness: int = 0
    agent_message: str = ""
    agent_name: str = ""
    agent_evolution: int = 0
    agent_last_message: str = ""
    agent_evolution_prob: float = 0.0  # Lesson 06: logistic P(evolve)

    # Lesson 06 probability displays
    archetype_probs: list[dict] = []  # [{"name": "Hero", "prob": 0.87}, ...]
    rarity_odds: list[float] = []  # [P(common), P(uncommon), P(rare), P(legendary)]

    # Phase 4 — economy & retention
    last_tick: str = ""  # ISO timestamp of last decay tick
    agent_portrait: str = ""  # FAL.ai generated portrait path → /creature-art URL
    portrait_pending: bool = False  # Lesson 13: bounded poller armed while FAL draws
    can_mint: bool = False  # Bayesian confidence gate for MINT

    # Phase 19 — Creature state machine display
    creature_state: str = "happy"
    creature_mood: str = "content"
    day_phase: str = "day"

    # Phase 19 — BPE tokenizer / classifier info
    token_count: int = 0
    token_archetype: str = ""
    token_confidence: float = 0.0

    # Phase 19 — Safety flag
    safety_flagged: bool = False
    safety_reason: str = ""

    # I03 — Embedding drift (how much creature evolved since birth)
    embedding_drift: float = 0.0

    # Domain — bond level from creature_agent.py
    bond_level: int = 0

    # I05 — Progression tier display
    tier_name: str = "Tamer"
    tier_badge: str = "★"
    next_tier_name: str = "Master"
    next_tier_distinct: int = 5

    # Phase 19 — Scout integration
    scout_result: str = ""
    scout_running: bool = False

    # G04: Birthplace lat/lon for static map
    agent_lat: float = 0.0
    agent_lon: float = 0.0

    # G05: Geo-capture state — '' | 'granted' | 'denied'
    geo_status: str = ""
    pending_thought: str = ""  # first-summon geo gate: text held while awaiting coords
    geo_lat: float = 0.0
    geo_lon: float = 0.0
    geo_place: str = ""

    # ── Player identity (D7 retention) ──
    # Verified Telegram identity from initData; None while unverified/anonymous.
    # '' = not yet captured, 'anon' = initData absent/invalid (game keeps
    # working — auth is additive), otherwise a JSON object {user_id, ...}.
    player_identity: str = ""

    # TERRA vision: the creature's own words about its birthplace
    # (generated lazily via see_birthplace, cached in this field)
    home_lore: str = ""
    home_lore_loading: bool = False

    # The player's terra: every creature that ever lived (persisted).
    terra: list[dict] = []

    # Bottom navigation tab: "" = none, "terra", "care", "map"
    active_tab: str = ""

    # Onboarding tutorial (shown once per first visit)
    show_tutorial: bool = True

    # I09: Summon streak counter
    summon_streak: int = 0

    # I11 — Global creature map
    global_creatures: list[dict] = []
    selected_region: str = ""
    region_creatures: list[dict] = []
    map_loading: bool = False

    # I10: Auto-care while away — terra caretaker
    stasis_active: bool = False
    stasis_cooldown_until: float = 0.0  # epoch; 0 = available
    grazed_away_message: str = ""  # shown on return after auto-graze

    # M02: Geo-tournament state
    tournament_id: str = ""  # battle_id of the latest tournament offer
    tournament_archetype: str = ""  # archetype that triggered the offer
    tournament_status: str = ""  # pending | accepted | declined | completed | expired
    tournament_offer_text: str = ""  # human-readable offer description
    tournament_score_a: float = 0.0
    tournament_score_b: float = 0.0
    tournament_winner_id: str = ""
    tournament_xp_gained: int = 0
    tournament_count: int = 0  # total battles participated in

    # I12: Release mechanic — creature goes into the wild
    show_release_dialog: bool = False
    wild_tamer_badge: bool = False

    # I12 v2: Release with final words + receipt ("Встреча, а не коллекция")
    final_words: str = ""
    released_place: str = ""
    released_words: str = ""
    released_just_now: bool = False
    released_count: int = 0  # reframed win counter — released-based ("Встречено X из 5")
    complete_releases: int = 0  # depth win (Lens #97): releases WITH final words + real geo
    # Ritual monetisation (owner directive 2026-08-13): the ACTUAL WIN —
    # a complete release (final words + real geo) — is the paid sacred
    # moment. Words reach the world only when the ritual settles
    # (Lightning sacred rail / Stars), so complete_releases counts PAID
    # wins by construction. The free path releases the creature but
    # never persists words → never counts toward the depth win.
    show_ritual_payment: bool = False
    release_ritual_paid: bool = False
    release_ritual_invoice: str = ""
    release_ritual_ref: str = ""
    release_ritual_qr: str = ""
    release_ritual_lightning_uri: str = ""  # lightning: deep link (1-tap wallet open)
    release_ritual_auto_verify: bool = False
    release_ritual_verify_attempts: int = 0
    pending_words: str = ""
    ritual_stars_pending: bool = False  # Stars invoice open — gate the button, never complete on click

    # «Зажечь свечу» — WebLN candle ritual on a released creature's birthplace.
    # 500-sat keysend zap from the player's browser wallet (Alby extension);
    # the reward is a NEW creature line (candle_lore), not cosmetics.
    candle_price: int = CANDLE_PRICE_SATS
    candle_state: str = ""        # '' | 'paying' | 'lit' | 'failed' | 'nowebln'
    candle_lore: str = ""         # the creature's new line after lighting
    candle_lit: bool = False      # session flag — shows the flame + words
    candle_reason: str = ""       # last failure reason ('nowebln', 'rejected', ...)

    # P3 M04: Creature trading
    show_trade_dialog: bool = False
    trade_target_id: int = 0
    trade_target_name: str = ""
    trade_target_rarity: str = ""
    trade_price_input: str = ""
    trade_min_price: int = 0
    trade_message: str = ""
    trade_listings: list[dict] = []

    @rx.var
    def xp_into_level(self) -> int:
        """XP progress within the current level (0-100) for the XP bar."""
        return self.xp % 100

    @rx.var
    def static_map_url(self) -> str:
        """G04: birthplace thumbnail via self-hosted OSM static map renderer.

        staticmap.openstreetmap.de was shut down by OSM (DNS dead since 2024)
        and the Yandex Static Maps hotfix is removed (RU service + external API).
        We now stitch OSM tiles server-side (terramon/adapters/static_map.py)
        and serve them from /static-map — one OSM source for the whole game.
        """
        if self.agent_lat != 0.0 or self.agent_lon != 0.0:
            return static_map_endpoint_path(
                self.agent_lat, self.agent_lon, zoom=14, width=300, height=200
            )
        return ""

    @rx.var
    def rarity_glow_style(self) -> str:
        """CSS box-shadow glow matching current creature rarity."""
        return _RARITY_GLOW.get(self.rarity, _RARITY_GLOW["common"])

    @rx.var
    def candle_visible(self) -> bool:
        """«Зажечь свечу» block renders only for a released creature.

        Session truth: released_just_now (set right after the release
        receipt). The seed-status fallback covers the reload case where
        load_terra() re-syncs the flag from the persisted seed record.
        """
        return bool(self.released_just_now)

    @rx.var
    def evolution_hint(self) -> str:
        """Actionable evolution progress text (Phase 2)."""
        pct = self.agent_evolution_prob
        if pct >= 50:
            return "✦ Ready to evolve! Click EVOLVE."
        if self.agent_happiness < 70:
            return f"Need {70 - self.agent_happiness} more ❤️ Happiness"
        if self.level < 10:
            return f"{10 - self.level} more levels to evolve"
        return "Keep interacting to grow"

    @rx.var
    def lightning_button_label(self) -> str:
        """Honest Lightning mint price on the '⚡ Mint via Lightning' button.

        lightning_mint_price lifts the Stars-typed price_sats to at least
        LIGHTNING_MIN_MINT_SATS (the Alby Hub JIT floor) — the button shows
        the REAL invoiced sats, not the Stars price. The '⚡ Mint via
        Lightning' prefix is load-bearing: the KPI probe's has-text selector
        keys on it, so it must stay at the START of the label.
        """
        return f"⚡ Mint via Lightning · {lightning_mint_price(self.price_sats)} sats"

    @rx.event
    def set_thought(self, value: str):
        self.thought = value

    # ── G05: Geo capture ─────────────────────────────────────────────

    def _apply_coords(self, coords) -> None:
        """Validate + store captured coordinates (shared by capture paths)."""
        lat, lon = _validate_coords(coords)
        if lat is None or lon is None:
            self.geo_status = "denied"
        else:
            self.geo_status = "granted"
            self.geo_lat, self.geo_lon = lat, lon
        # iter-29 re-anchor: a creature born unanchored (geo denied at
        # first summon) must still be able to reach the paid ritual — ⟳
        # now updates the CURRENT creature's anchor and persists it to
        # the seed, so release_creature's has_anchor gate passes. The
        # first-summon deferral is skipped (pending_thought set, agent
        # empty).
        if self.agent and not self.pending_thought:
            self.agent_lat, self.agent_lon = lat, lon
            self.place = self.geo_place or f"{lat:.2f}, {lon:.2f}"
            try:
                _MEMORY.update_seed(
                    self.agent, self.thought,
                    lat=lat, lon=lon, place_name=self.geo_place or "",
                )
            except Exception as e:
                log.warning(f"Re-anchor persist failed: {e}")

    @rx.event
    def capture_location(self):
        """G05: request device coordinates — Telegram LocationButton (native
        picker) with navigator.geolocation fallback. Result lands in
        geo_status / geo_lat / geo_lon.

        NOTE: in Reflex 0.9.x a plain (non-async) event cannot capture the
        result of rx.call_script via `yield` — the value is delivered to the
        `callback=` handler instead (reflex_base/event/__init__.py:1739).
        """
        yield rx.call_script(_LOCATION_JS, callback=TerramonState.on_coords)

    @rx.event
    def on_coords(self, result):
        """Receive the geolocation result from the call_script callback.

        Applies coords, then re-runs summon() to finish the deferred
        first-summon (the thought was held in pending_thought).
        """
        self._apply_coords(result)
        if self.pending_thought:
            text = self.pending_thought
            self.pending_thought = ""
            self.thought = text
            yield TerramonState.summon

    def _refresh_released_count(self) -> None:
        """Reframe: released-based win counter + the depth counter
        (complete releases WITH final words + real geo, Lens #97)."""
        try:
            self.released_count = int(_LOOP.progress.released_count())
            self.complete_releases = int(_LOOP.progress.complete_releases)
        except Exception:
            try:
                seeds = _MEMORY.load_all_seeds()
                self.released_count = sum(
                    1 for s in seeds if getattr(s, "status", "") == "released"
                )
            except Exception:
                pass

    @rx.event
    def summon(self):
        """Summon a creature from thought."""
        text = self.thought.strip()
        if not text:
            return
        if self.summon_count > 0 and not self.unlocked:
            self.summoning = False
            return
        self.summoning = True
        # M4: Dedup guard — the exact same thought already birthed a
        # creature. The router is deterministic (same thought => same
        # agent), so an existing seed with this raw_input IS the same
        # creature. Load it instead of summoning a duplicate: this kills
        # the redeploy pattern where the in-memory collection resets, the
        # gate reopens, and the next summon of the same thought appends a
        # duplicate Hero to the persisted seeds.
        existing = _MEMORY.find_seed(text)
        if existing is not None:
            self._present_existing_creature(existing)
            self.summoning = False
            return
        # G05: FIRST summon — capture location so the creature is born
        # anchored to a real place. Reflex 0.9.x: the call_script result is
        # delivered to callback= (not via yield), so we defer the summon:
        # store the thought, request coords, _on_coords re-runs summon().
        if self.geo_status == "":
            self.pending_thought = text
            self.summoning = False
            self.agent_message = "📍 Закрепи свою мысль на планете — разреши геолокацию"
            yield rx.call_script(_LOCATION_JS, callback=TerramonState.on_coords)
            return
        try:
            _geo = (
                GeoContext(self.geo_lat, self.geo_lon, self.geo_place)
                if self.geo_status == "granted"
                else None
            )
            result = _LOOP.take_turn(text, color=False, geo=_geo)
            rarity = result.rarity
            self.agent = result.agent
            self.rarity = rarity
            self.sigil = _RARITY_SIGIL[rarity]
            self.color = _RARITY_COLOR[rarity]
            self.lore = _ARCHETYPE_LORE.get(result.agent, "A thought made flesh.")
            self.price_sats = result.price_sats
            # M02: Geo-tournament offer state
            self.tournament_id = result.tournament_id
            self.tournament_archetype = result.tournament_archetype
            if result.tournament_id:
                battle = _TOURNAMENT_SVC.get_battle(result.tournament_id)
                if battle:
                    self.tournament_status = battle.status.value
                    self.tournament_offer_text = (
                        f"⚔️ Geo-tournament: Your {result.tournament_archetype} "
                        f"faces another {result.tournament_archetype} nearby! "
                        f"Accept to battle for XP!"
                    )
                else:
                    self.tournament_status = ""
                    self.tournament_offer_text = ""
            else:
                self.tournament_status = ""
                self.tournament_offer_text = ""
            self.tournament_score_a = 0.0
            self.tournament_score_b = 0.0
            self.tournament_winner_id = ""
            self.tournament_xp_gained = 0
            self.xp = _LOOP.progress.xp
            self.level = _LOOP.progress.level
            self.distinct = _LOOP.progress.distinct_count
            self.goal = _LOOP.progress.goal_distinct
            self.summon_streak = _LOOP.progress.summon_streak
            prev_goal = self.goal_reached
            self.goal_reached = result.goal_reached
            if result.goal_reached and not prev_goal:
                self.celebration_pending = True
            self.has_summoned = True
            self.summon_count += 1
            # Candle ritual: a new creature starts unlit — clear the previous
            # release/candle session state so the block re-gates correctly.
            self.released_just_now = False
            self.candle_state = ""
            self.candle_lore = ""
            self.candle_lit = False
            self.candle_reason = ""
            # M7: a new creature starts unminted (mint is per-creature).
            self.minted = False
            self.minted_at = ""
            seeds = _MEMORY.load_all_seeds()
            self.share_code = _share_code_from_seed(seeds[-1] if seeds else None)
            self.reflection = _reflect_on_memory(seeds, result.agent)
            if seeds:
                last_insight = seeds[-1].insight
                self.insight = f"INSIGHT: {last_insight.therefore}" if last_insight else ""
            else:
                self.insight = ""
            self.place = ""
            self.agent_lat = 0.0
            self.agent_lon = 0.0
            self.home_lore = ""
            self.home_lore_loading = False
            if seeds and seeds[-1].insight and seeds[-1].insight.geo:
                g = seeds[-1].insight.geo
                self.agent_lat = g.lat
                self.agent_lon = g.lon
                self.place = g.place_name or f"{g.lat:.2f}, {g.lon:.2f}"
                # G05: backfill geo-capture state from the seed (the backend
                # reverse-geocodes and fills place_name).
                self.geo_place = g.place_name or ""
                self.geo_lat, self.geo_lon = g.lat, g.lon
                if g.place_name or (g.lat != 0.0 or g.lon != 0.0):
                    self.geo_status = "granted"
            elif seeds and (seeds[-1].lat or seeds[-1].lon):
                self.agent_lat, self.agent_lon = seeds[-1].lat, seeds[-1].lon
                self.place = seeds[-1].place_name or f"{seeds[-1].lat:.2f}, {seeds[-1].lon:.2f}"
                self.geo_status = "granted"
        except Exception as e:
            log.error(f"take_turn failed: {e}", exc_info=True)
            # Anti-stall guard: ALWAYS clear the flag and return a graceful
            # result — never leave summoning=True with a frozen UI.
            self.summoning = False
            self.agent_message = _SUMMON_FAILURE_MESSAGE
            return

        # B1: Creature greeting via LLM (silent fail)
        try:
            from terramon.application.llm_behavior import generate_response
            from terramon.domain.insight import Insight
            _greeting_agent = CreatureAgent(
                agent_id="summon-greet",
                archetype=self.agent, place_name=self.place,
                level=self.level, xp=self.xp,
                insight=Insight(driver="", barrier="", therefore="", archetype=self.agent),
                total_xp_earned=self.xp + (self.level - 1) * 100,
            )
            _greeting_msg = generate_response(_greeting_agent, "summon", text)
            if _greeting_msg and hasattr(_greeting_msg, 'text'):
                self.creature_greeting = _greeting_msg.text
            else:
                # LLM silent (timeout/fallback chain exhausted) — the creature
                # is still born, with a graceful template greeting.
                self.creature_greeting = _SUMMON_GREETING_FALLBACK
        except Exception as e:
            log.warning(f"LLM greeting failed: {e}")
            self.creature_greeting = _SUMMON_GREETING_FALLBACK

        # B3: Memory greeting
        try:
            import datetime
            now_iso = datetime.datetime.now().isoformat()
            if self.last_seen:
                from datetime import datetime as _dt
                _hours = (_dt.fromisoformat(now_iso) - _dt.fromisoformat(self.last_seen)).total_seconds() / 3600
                if _hours < 1:       self.memory_greeting = "You were just here..."
                elif _hours < 6:     self.memory_greeting = f"{int(_hours)}h since you last visited."
                elif _hours < 24:    self.memory_greeting = "Almost a day..."
                else:               self.memory_greeting = f"{int(_hours)}h — the terra grew quiet."
            else:
                self.memory_greeting = "A new presence stirs."
            self.last_seen = now_iso
        except Exception as e:
            log.warning(f"Memory greeting failed: {e}")
            self.memory_greeting = "Welcome back."

        # Init agent stats
        self.agent_name = self.agent
        self.agent_hunger = 80
        self.agent_energy = 80
        self.agent_happiness = 60

        # Confidence + archetype probabilities (Bayesian — Lesson 07)
        try:
            from terramon.application.bayes_router import (
                load_belief, save_belief, bayes_forward, update_belief,
                _ARCHETYPE_NAMES,
            )
            prior = load_belief()
            bayes_winner, bayes_posterior, bayes_likelihood = bayes_forward(text, prior)
            new_counts = update_belief(prior, bayes_winner)
            save_belief(new_counts)
            self.intelligence = round(bayes_posterior[bayes_winner] * 100)
            probs = bayes_posterior
            top3 = sorted(range(12), key=lambda i: probs[i], reverse=True)[:3]
            self.archetype_probs = [
                {"name": _ARCHETYPE_NAMES[i], "prob": round(probs[i], 3)}
                for i in top3
            ]
            # Revenue gate: only show MINT when Bayesian confidence > 50%
            from terramon.application.bayes_router import should_gate_payment
            self.can_mint = should_gate_payment(bayes_posterior, threshold=0.5)
        except Exception as e:
            log.warning(f"Bayesian confidence failed: {e}")

        # Rarity odds + evolution
        try:
            from terramon.domain.rarity import classify_rarity
            self.rarity_odds = classify_rarity(text).probabilities
            from terramon.domain.creature_agent import CreatureAgent
            from terramon.domain.insight import Insight
            _tmp = CreatureAgent(
                agent_id="tmp", archetype=self.agent,
                insight=Insight(driver="", barrier="", therefore="", archetype=self.agent),
                level=self.level, xp=self.xp,
                total_xp_earned=self.xp + (self.level - 1) * 100,
            )
            _tmp.can_evolve
            self.agent_evolution_prob = _tmp.evolution_probability
        except Exception as e:
            log.warning(f"Rarity/evolve failed: {e}")

        # I03: Embedding drift — how much this creature evolved since birth
        try:
            self.embedding_drift = _MEMORY.compute_embedding_drift(self.agent)
        except Exception as e:
            log.warning(f"Embedding drift failed: {e}")

        # I05: Progression tier vars from PlayerProgress
        try:
            _p = _LOOP.progress
            self.tier_name = _p.current_tier_name
            self.tier_badge = _p.current_tier_badge
            self.next_tier_name = _p.next_tier_name
            self.next_tier_distinct = _p.next_tier_requirement
        except Exception as e:
            log.warning(f"Tier vars failed: {e}")

        # Phase 19: Creature state + mood computation
        try:
            from tools.time_tool import get_day_phase
            _phase = get_day_phase()
            self.day_phase = "night" if _phase == "night" else "day"
            _tmp_agent = CreatureAgent(
                agent_id="_state", archetype=self.agent,
                hunger=self.agent_hunger, energy=self.agent_energy,
                happiness=self.agent_happiness,
            )
            self.creature_state = _tmp_agent.state.value
            self.creature_mood = _tmp_agent.mood
        except Exception as e:
            log.warning(f"Creature state/mood failed: {e}")
            self.day_phase = "day"
            self.creature_state = "happy"
            self.creature_mood = "content"

        # Phase 19: BPE tokenizer status (token count + archetype confidence)
        try:
            _classifier_scores = _CLASSIFIER.scores(text)
            self.token_archetype = self.agent
            self.token_confidence = _classifier_scores.get(self.agent, 0.0)
            # Token count from text preprocessing
            from terramon.adapters.text_preprocessing import preprocess_for_classifier
            _clean = preprocess_for_classifier(text)
            import re
            self.token_count = len(re.findall(r"[a-z']+", _clean))
        except Exception as e:
            log.warning(f"Token stats failed: {e}")
            self.token_count = 0
            self.token_archetype = self.agent
            self.token_confidence = 0.0

        # Phase 19: Safety flag from content safety middleware
        try:
            from terramon.events.bus import content_safety_middleware
            from terramon.events.agent_summoned import AgentSummoned
            import datetime as _dt
            _evt = AgentSummoned(text, self.agent, _dt.datetime.now().isoformat())
            _flagged_evt, _ = content_safety_middleware(_evt)
            self.safety_flagged = _flagged_evt.safety_flagged
            self.safety_reason = _flagged_evt.safety_reason
        except Exception as e:
            log.warning(f"Safety check failed: {e}")
            self.safety_flagged = False
            self.safety_reason = ""

        # Reload terra
        try:
            seeds = _MEMORY.load_all_seeds()
            self.terra = [_seed_to_card(s) for s in seeds]
        except Exception as e:
            log.warning(f"Terra reload failed: {e}")

        # I07: Haptic feedback — SUMMON → medium
        try:
            yield rx.call_script(
                'Telegram.WebApp.HapticFeedback.impactOccurred("medium")'
            )
        except Exception:
            pass

        self.summoning = False

        # Phase 2: FAL.ai creature portrait (background, silent fail)
        import threading
        _thought = text
        _agent = self.agent
        _rarity = self.rarity
        def _gen_portrait():
            try:
                from terramon.application.portrait_gen import generate_portrait as _gen
                _gen(_thought, _agent, _rarity)
            except Exception as _e:
                log.debug("Portrait generation skipped: %s", _e)
        threading.Thread(target=_gen_portrait, daemon=True).start()
        # Lesson 13: arm the bounded portrait poller so the art pops in
        # while the player watches (the thread cannot touch Reflex state).
        self.portrait_pending = True

    @rx.event
    def see_birthplace(self):
        """TERRA vision: the creature opens its eyes on its birthplace.

        Renders the OSM static map of the birth coordinates, sends it as a
        vision image to GPT-4o (same OpenRouter key, no new env var) with
        the creature's archetype voice + insight lens, and stores the
        1-3 sentence lore in home_lore. Silent fail: any error leaves
        home_lore empty and the UI keeps the plain map + place name.
        """
        if not self.agent_lat and not self.agent_lon:
            return
        if self.home_lore or self.home_lore_loading:
            return
        self.home_lore_loading = True
        try:
            from terramon.adapters.static_map import render_static_map
            from terramon.application.llm_behavior import describe_birthplace
            from terramon.domain.creature_agent import CreatureAgent
            from terramon.domain.insight import Insight

            png = render_static_map(
                self.agent_lat, self.agent_lon, zoom=14, width=300, height=200
            )
            # Last insight for this creature (DRIVER/BARRIER/THEREFORE lens)
            insight = None
            try:
                seeds = _MEMORY.load_all_seeds()
                if seeds and seeds[-1].insight:
                    insight = seeds[-1].insight
            except Exception:
                pass
            agent = CreatureAgent(
                agent_id="birthplace",
                archetype=self.agent,
                place_name=self.place,
                insight=insight or Insight(
                    driver="", barrier="", therefore="", archetype=self.agent
                ),
            )
            lore = describe_birthplace(png, agent)
            if lore:
                self.home_lore = lore
        except Exception as e:
            log.warning("see_birthplace failed (silent): %s", e)
        finally:
            self.home_lore_loading = False

    @rx.event
    def load_terra(self):
        """Load the player's persisted terra on app open (survives redeploys)."""
        # Player identity: read the raw initData from the TMA bridge FIRST.
        # The verified result lands in on_init_data (callback pattern, same as
        # G05 geolocation) — the game never blocks on it: absent/invalid
        # initData simply leaves the session anonymous.
        yield rx.call_script(_INITDATA_JS, callback=TerramonState.on_init_data)
        # F2: restore celebration-dismissed from localStorage (browser-storage
        # pattern) so returning players who already celebrated never see the
        # full-screen overlay again. celebration_pending stays False here.
        yield rx.call_script(
            "localStorage.getItem('terramon_celebration_dismissed')",
            callback=TerramonState.on_celebration_restore,
        )
        # Candle ritual: start unlit; the seed sync below restores the lit
        # state for an already-released creature with a persisted candle.
        self.released_just_now = False
        self.candle_state = ""
        self.candle_lore = ""
        self.candle_lit = False
        self.candle_reason = ""
        seeds = _MEMORY.load_all_seeds()
        # M4: rebuild the WHOLE collection state from the persisted seeds.
        # Previously only terra/xp/level/distinct were restored, while
        # summon_count/has_summoned/goal_reached reset to 0 — after a
        # redeploy the monetization gate opened again and the next summon
        # of the same thought created a duplicate creature. Now every
        # counter is seed-derived (see hydrate_from_memory).
        _LOOP.progress = PlayerProgress.from_seeds(seeds)
        _LOOP.progress.recalculate_tier()
        hydrated = hydrate_from_memory(_MEMORY, seeds=seeds)
        self.terra = hydrated["terra"]
        if hydrated["has_summoned"]:
            self.summon_count = hydrated["summon_count"]
            self.has_summoned = True
            self.xp = hydrated["xp"]
            self.level = hydrated["level"]
            self.distinct = hydrated["distinct"]
            self.goal = hydrated["goal"]
            self.goal_reached = hydrated["goal_reached"]
            self.summon_streak = hydrated["summon_streak"]
            # I05: progression tier vars
            self.tier_name = hydrated["tier_name"]
            self.tier_badge = hydrated["tier_badge"]
            self.next_tier_name = hydrated["next_tier_name"]
            self.next_tier_distinct = hydrated["next_tier_distinct"]
            # G05: released-based win counter for the "Встречено X из 5" display
            self.released_count = hydrated["released_count"]
            # Depth win (Lens #97): complete releases (final words + real geo)
            self.complete_releases = hydrated.get("complete_releases", 0)
            # F3 gate: a returning player has already been through the
            # summon flow — keep them unblocked across redeploys. The MVP
            # unlock is free anyway (Stars fallback sets unlocked=True),
            # and real monetization is MINT, not the summon gate.
            self.unlocked = True

        # M7: re-sync the session mint counter from the PERSISTED seed
        # records (survives reloads — /health reads the same source).
        self.mint_count = sum(1 for s in seeds if getattr(s, "minted", False))
        try:
            _LOOP.progress.mint_count = self.mint_count
        except Exception:
            pass

        # Phase 4: tick decay on app open (retention)
        if seeds:
            self._apply_tick_decay()

        # Candle ritual: restore the released flag + candle lore from the
        # persisted seed record (survives reloads) so the memorial card and
        # the «Зажечь свечу» block render correctly.
        try:
            for s in reversed(seeds):
                if s.summoned_agent == self.agent and s.raw_input == self.thought:
                    self.released_just_now = s.status == "released"
                    self.candle_lore = getattr(s, "candle_lore", "")
                    self.candle_lit = bool(self.candle_lore)
                    self.released_words = self.released_words or self.final_words
                    # M7: restore the mint record so the 💠 MINTED badge
                    # survives reloads.
                    self.minted = bool(getattr(s, "minted", False))
                    self.minted_at = str(getattr(s, "minted_at", "") or "")
                    break
        except Exception as e:
            log.warning(f"Candle state sync failed: {e}")

        # Lesson 13: refresh the current creature's portrait from the
        # registry (survives redeploys — the art lives on the volume).
        self.portrait_pending = False
        self.refresh_portrait()

    @rx.event
    def on_init_data(self, result):
        """Verify + persist the Telegram identity from initData (additive auth).

        Callback of the load_terra call_script. ``result`` is the raw initData
        string ('' outside a TMA). Invalid/missing initData → anonymous player,
        the game continues exactly as before — identity never gates gameplay.
        """
        raw = result or ""
        try:
            identity = PlayerIdentity.from_init_data(raw, _BOT_TOKEN)
        except Exception as e:
            log.warning("initData verification failed (anon fallback): %s", e)
            identity = None
        if identity is None:
            self.player_identity = "anon"
            return
        try:
            _MEMORY.record_player(identity)
        except Exception as e:
            log.warning("record_player failed (identity not persisted): %s", e)
        self.player_identity = json.dumps(
            {
                "user_id": identity.user_id,
                "first_name": identity.first_name,
                "username": identity.username,
                "platform": identity.platform,
            },
            ensure_ascii=False,
        )

    def _present_existing_creature(self, seed: ThoughtSeed) -> None:
        """M4: show the already-persisted creature for a repeated thought.

        Dedup guard path: NO new seed is saved, NO counters advance
        (summon_count, xp, distinct stay as persisted) — the collection
        cannot gain a duplicate creature from a re-summoned thought.
        """
        rarity = seed.rarity if isinstance(seed.rarity, str) else seed.rarity.value
        self.agent = seed.summoned_agent
        self.rarity = rarity
        self.sigil = _RARITY_SIGIL.get(rarity, "·")
        self.color = _RARITY_COLOR.get(rarity, "#9ca3af")
        self.lore = _ARCHETYPE_LORE.get(seed.summoned_agent, "A thought made flesh.")
        self.price_sats = seed.price_sats
        self.has_summoned = True
        self.insight = f"INSIGHT: {seed.insight.therefore}" if seed.insight else ""
        self.reflection = (
            f"Ты уже встречал эту мысль — {seed.summoned_agent} живёт в твоей терре."
        )
        self.place = seed.place_name or (
            f"{seed.lat:.2f}, {seed.lon:.2f}" if (seed.lat or seed.lon) else ""
        )
        self.agent_lat = seed.lat or 0.0
        self.agent_lon = seed.lon or 0.0
        self.share_code = _share_code_from_seed(seed)
        self.released_just_now = seed.status == "released"
        self.agent_name = seed.summoned_agent
        self.agent_message = (
            f"🔁 Ты уже встречал эту мысль — {seed.summoned_agent} не рождается дважды."
        )

    @rx.event
    def capture(self):
        """Open the photo-entry path (simulated in this MVP)."""
        self.photo_mode = True

    @rx.event
    def set_tab(self, tab: str):
        """Toggle bottom nav tab: clicking active tab closes it.
        Auto-loads global map data when the map tab is selected."""
        self.active_tab = tab if self.active_tab != tab else ""
        # I11: auto-fetch global map data when map tab opens
        if self.active_tab == "map" and not self.global_creatures:
            # Defer so the UI updates first, then fetch starts
            yield
            yield TerramonState.load_global_map

    @rx.event
    def dismiss_tutorial(self):
        """Close the first-time onboarding overlay."""
        self.show_tutorial = False

    # ── I11: Global creature map ────────────────────────────────────

    @rx.event
    def load_global_map(self):
        """Fetch creature locations from Nostr relays for the global map.

        Runs in a background thread; updates global_creatures when done.
        Falls back gracefully to local-only markers when relays are unreachable.
        """
        if self.map_loading:
            return
        self.map_loading = True
        import threading

        def _fetch():
            try:
                from terramon.adapters.nostr_reader import NostrRelayReader
                reader = NostrRelayReader(timeout=3)
                creatures = reader.fetch_global_creatures(max_events=200)
                self.global_creatures = [
                    {
                        "event_id": c.event_id,
                        "lat": c.lat,
                        "lon": c.lon,
                        "agent": c.agent,
                        "thought": c.thought,
                        "rarity": c.rarity,
                        "timestamp": c.timestamp,
                        "region_key": c.region_key,
                    }
                    for c in creatures
                ]
            except Exception as e:
                log.warning("Global map fetch failed: %s", e)
            finally:
                self.map_loading = False

        threading.Thread(target=_fetch, daemon=True).start()

    @rx.event
    def select_region(self, region_key: str):
        """Select a region on the global map and show its creatures."""
        self.selected_region = region_key
        if not region_key:
            self.region_creatures = []
            return
        # Filter global creatures by this 5-degree grid cell
        self.region_creatures = [
            c for c in self.global_creatures
            if c.get("region_key") == region_key
        ]

    @rx.var
    def map_heatmap_data(self) -> str:
        """Build a density heatmap JSON for Leaflet's heatmap layer.

        Returns a JSON string of [lat, lon, intensity] tuples grouped
        by 5-degree grid cells. Used by the Leaflet heatmap overlay.
        """
        if not self.global_creatures:
            return "[]"
        from collections import Counter
        # Count creatures per region_key
        regions: Counter = Counter()
        cell_centers: dict[str, tuple[float, float]] = {}
        for c in self.global_creatures:
            rk = c.get("region_key", "")
            if not rk:
                continue
            regions[rk] += 1
            if rk not in cell_centers:
                parts = rk.split("_")
                try:
                    center_lat = int(parts[0]) + 2.5
                    center_lon = int(parts[1]) + 2.5
                    cell_centers[rk] = (center_lat, center_lon)
                except (ValueError, IndexError):
                    continue
        import json as _json
        heatmap = [
            [lat, lon, min(count / max(regions.values()), 1.0)]
            for rk, count in regions.most_common(50)
            for (lat, lon) in [cell_centers.get(rk, (0, 0))]
        ]
        return _json.dumps(heatmap)

    @rx.var
    def map_marker_json(self) -> str:
        """Build JSON array of creature markers for Leaflet.

        Returns a JSON string of [lat, lon, agent, thought] tuples
        for creatures with valid geo data. Limited to first 100 to
        keep the marker layer performant.
        """
        import json as _json
        markers = [
            [c["lat"], c["lon"], c.get("agent", ""), c["thought"]]
            for c in self.global_creatures[:100]
            if c.get("lat") and c.get("lon")
        ]
        return _json.dumps(markers)

    @rx.event
    def dismiss_celebration(self):
        """Dismiss the TERRA AWAKENED celebration overlay (F2)."""
        self.celebration_pending = False
        self.celebration_dismissed = True
        yield rx.call_script("localStorage.setItem('terramon_celebration_dismissed','1')")

    @rx.event
    def on_celebration_restore(self, result):
        """F2: callback of the load_terra localStorage.getItem restore."""
        try:
            self.celebration_dismissed = result == "1"
        except Exception as e:
            log.warning(f"celebration restore failed: {e}")

    # ── Tamagotchi×Pokemon interaction handlers ───────────

    def _init_agent_stats(self):
        """Initialize creature stats from current summon state."""
        if not self.agent_name:
            self.agent_name = self.agent
        # Set initial stats if they're at defaults (meaning no agent was initialized)
        if self.agent_hunger == 0 and self.agent_energy == 0 and self.agent_happiness == 0:
            self.agent_hunger = 80
            self.agent_energy = 80
            self.agent_happiness = 60

    @rx.event
    def feed_agent(self):
        self._init_agent_stats()
        msg = _AGENT_SVC.feed(CreatureAgent("_tmp", hunger=self.agent_hunger,
                              energy=self.agent_energy, happiness=self.agent_happiness))
        self.agent_hunger = min(100, self.agent_hunger + 25)
        self.agent_energy = min(100, self.agent_energy + 5)
        self.agent_message = msg.text
        self._recompute_creature_state()
        # I07: Haptic feedback — FEED → light
        try:
            yield rx.call_script(
                'Telegram.WebApp.HapticFeedback.impactOccurred("light")'
            )
        except Exception:
            pass

    @rx.event
    def play_with_agent(self):
        self._init_agent_stats()
        self.agent_happiness = min(100, self.agent_happiness + 20)
        self.agent_energy = max(0, self.agent_energy - 15)
        msg = _AGENT_SVC.play(CreatureAgent("_tmp", hunger=self.agent_hunger,
                              energy=self.agent_energy, happiness=self.agent_happiness))
        self.agent_message = msg.text
        self._recompute_creature_state()
        # I07: Haptic feedback — PLAY → light
        try:
            yield rx.call_script(
                'Telegram.WebApp.HapticFeedback.impactOccurred("light")'
            )
        except Exception:
            pass

    @rx.event
    def rest_agent(self):
        self._init_agent_stats()
        self.agent_energy = min(100, self.agent_energy + 40)
        msg = _AGENT_SVC.rest(CreatureAgent("_tmp", hunger=self.agent_hunger,
                              energy=self.agent_energy, happiness=self.agent_happiness))
        self.agent_message = msg.text
        self._recompute_creature_state()

    @rx.event
    def talk_to_agent(self):
        self._init_agent_stats()
        self.agent_happiness = min(100, self.agent_happiness + 5)
        msg = _AGENT_SVC.talk(CreatureAgent("_tmp", hunger=self.agent_hunger,
                              energy=self.agent_energy, happiness=self.agent_happiness,
                              archetype=self.agent,
                              insight=Insight(driver="", barrier="",
                                              therefore=self.insight.replace("INSIGHT: ", ""),
                                              archetype=self.agent)))
        self.agent_message = msg.text
        self._recompute_creature_state()

    @rx.event
    def evolve_agent(self):
        self._init_agent_stats()
        self.agent_evolution += 1
        if self.agent_evolution >= 2:
            self.agent_evolution = 2
        msg = _AGENT_SVC.evolve(CreatureAgent("_tmp", hunger=self.agent_hunger,
                                energy=self.agent_energy, happiness=self.agent_happiness,
                                level=self.level, total_xp_earned=self.xp + (self.level-1)*100))
        self.agent_message = msg.text
        self.agent_last_message = msg.text
        # I08 v2 (iter-26): evolution shimmer — PLAIN (non-generator) handler.
        # The old generator yielded rx.call_script(setTimeout→sendEvent), which
        # suspended the handler and delayed the state delta; under load the
        # second EVOLVE click then read a stale state and its increment was
        # LOST (agent_evolution stuck at 1 → '💨 Отпустить' never rendered →
        # the win-path release ritual was unreachable on prod). A plain handler
        # delivers the full delta on return: every click increments exactly
        # once, immediately. The animation flag is auto-cleared by the gated
        # rx.moment in creature_care_panel (mirrors poll_portrait) — no JS
        # setTimeout/sendEvent round-trip needed.
        self.evolve_animating = True

    @rx.event
    def clear_evolution_animation(self):
        """Reset the evolution shimmer animation flag."""
        self.evolve_animating = False

    # ── I12: Release mechanic ───────────────────────────────────────

    @rx.event
    def show_release(self):
        """Show the release confirmation dialog."""
        if self.agent_evolution < 2:
            self.agent_message = (
                "This creature has not matured enough. "
                "Evolve it to stage 2 first."
            )
            return
        self.show_release_dialog = True

    @rx.event
    def hide_release(self):
        """Hide the release confirmation dialog."""
        self.show_release_dialog = False

    @rx.event
    def confirm_release(self):
        """Release the creature into the wild.

        Requirements:
        - evolution_stage >= 2
        - Creature not already released

        On release:
        1. Creature is removed from active care (reset stats)
        2. It stays in terra as a memorial (read-only)
        3. CreatureReleased event published to Nostr
        4. ★ Wild Tamer badge awarded
        """
        self.show_release_dialog = False
        if self.agent_evolution < 2:
            self.agent_message = "Not ready. Evolve to stage 2 first."
            return

        # Perform the release via AgentService
        try:
            _agent = CreatureAgent(
                agent_id=self.agent,
                archetype=self.agent,
                level=self.level,
                evolution_stage=self.agent_evolution,
                lat=self.agent_lat,
                lon=self.agent_lon,
                place_name=self.place,
            )
            msg = _AGENT_SVC.release(_agent)
            self.agent_message = msg.text
        except Exception as e:
            log.warning(f"Release failed: {e}")
            self.agent_message = "Something went wrong releasing this creature."

        # Publish CreatureReleased event
        try:
            from terramon.events.creature_released import CreatureReleased
            import datetime
            _evt = CreatureReleased(
                agent_id=self.agent,
                agent_name=self.agent_name or self.agent,
                archetype=self.agent,
                thought_seed=self.thought,
                lat=self.agent_lat,
                lon=self.agent_lon,
                place_name=self.place,
                evolution_stage=self.agent_evolution,
                level=self.level,
                rarity=self.rarity,
                release_timestamp=datetime.datetime.now().isoformat(),
                previous_owner="player",
            )
            # Publish via Nostr publisher if configured
            from terramon.adapters.nostr_publisher import NostrPublisher
            _pub = NostrPublisher()
            if _pub.seckey_hex:
                _pub.on_creature_released(_evt)
        except Exception as e:
            log.warning(f"Nostr publish for release failed: {e}")

        # Award ★ Wild Tamer badge
        self.wild_tamer_badge = True

        # Reset creature stats (removed from active care)
        self.agent_hunger = 0
        self.agent_energy = 0
        self.agent_happiness = 0
        self.agent_evolution = 0
        self.agent_name = ""
        self.agent_last_message = ""

        # Mark seed as released in memory
        try:
            seeds = _MEMORY.load_all_seeds()
            if seeds:
                # Update the last matching seed's status to "released"
                for s in reversed(seeds):
                    if s.summoned_agent == self.agent and s.raw_input == self.thought:
                        s.status = "released"
                        break
        except Exception as e:
            log.warning(f"Failed to update seed status: {e}")

        # Persist the release so it survives a restart (depth win, Lens #97):
        # without this /health complete_releases stays 0 forever.
        try:
            _MEMORY.update_seed(self.agent, self.thought, status="released")
        except Exception as e:
            log.warning(f"Release persistence failed: {e}")

        # Reload terra
        try:
            seeds = _MEMORY.load_all_seeds()
            self.terra = [_seed_to_card(s) for s in seeds]
        except Exception as e:
            log.warning(f"Terra reload after release failed: {e}")

        # G05 reframe: released-based win counter (idempotent set add)
        try:
            _LOOP.progress.record_release(self.agent)
        except Exception as e:
            log.warning(f"record_release failed: {e}")
        self._refresh_released_count()

    # ── I12 v2: Release with final words ─────────────────────────────

    @rx.event
    def set_final_words(self, value: str):
        """I12 v2: bind the dialog textarea to state."""
        self.final_words = value

    @rx.event
    def release_creature(self):
        """I12 v2 + ritual monetisation (owner directive 2026-08-13).

        The ACTUAL WIN — a complete release (final words + real geo) —
        is the PAID sacred moment («монета в фонтан»). Words reach the
        world only when the ritual settles (Lightning sacred rail via
        Alby BOLT11, or Stars). The free path (no words / no real geo)
        still releases the creature as a legacy release, but it never
        persists words → never counts toward complete_releases, so the
        depth win is monetised BY CONSTRUCTION.
        """
        self.show_release_dialog = False
        if self.agent_evolution < 2:
            self.agent_message = "Not ready. Evolve to stage 2 first."
            return
        words = self.final_words.strip()
        self.final_words = ""
        has_anchor = (
            self.agent_lat not in (None, 0) and self.agent_lon not in (None, 0)
        )
        if not words or not has_anchor:
            # Free legacy path — no ritual, no depth win.
            self._do_release("", complete=False)
            return
        if not self.release_ritual_paid:
            # Sacred rail: hold the words, open the ritual payment panel.
            self.pending_words = words
            self.show_ritual_payment = True
            self.create_ritual_invoice()
            return
        self._complete_ritual_release(words)

    @rx.event
    def create_ritual_invoice(self):
        """BOLT11 invoice for the release ritual (Alby Hub, sacred rail)."""
        try:
            if not _ALBY.url or not _ALBY.api_key:
                self.release_ritual_invoice = ""
                self.release_ritual_lightning_uri = ""
                self.agent_message = (
                    "🪙 Ритуал: Lightning не настроен — используй Stars "
                    f"({RITUAL_RELEASE_STARS} ⭐)."
                )
                return
            price = RITUAL_RELEASE_SATS
            req = _ALBY.create_payment(
                price, f"Terramon release ritual · {self.pending_words[:40]}"
            )
            self.release_ritual_invoice = req.destination
            self.release_ritual_lightning_uri = "lightning:" + req.destination
            self.release_ritual_ref = req.verification_ref
            try:
                self.release_ritual_qr = _qr_data_uri(req.destination)
            except Exception:
                self.release_ritual_qr = ""
            self.release_ritual_auto_verify = True
            self.release_ritual_verify_attempts = 0
            self.agent_message = (
                f"⚡ Ритуал отпускания: {price} sats. Оплати — и слова уйдут в мир."
            )
        except Exception as e:
            log.error(f"ritual invoice failed: {e}", exc_info=True)
            self.agent_message = f"⚡ Инвойс не создан: {getattr(e, 'message', e)}"

    @rx.event
    def verify_release_ritual(self, _tick=None):
        """Auto-verify poller + manual button: on settle the ritual fires.

        Mirrors the lightning gate poller (rx.moment passes datetime,
        swallowed by _tick). While polling, agent_message is never
        touched — the KPI probe parses the «⚡ Ритуал отпускания:»
        marker within seconds of the release click.
        """
        if not self.release_ritual_ref or not _ALBY.url:
            if self.release_ritual_auto_verify:
                self.release_ritual_auto_verify = False
                self.release_ritual_verify_attempts = 0
            return
        try:
            from terramon.ports.payment_port import PaymentRequest, PaymentMethod
            req = PaymentRequest(
                id=self.release_ritual_ref,
                method=PaymentMethod.LIGHTNING,
                amount_sats=RITUAL_RELEASE_SATS,
                destination=self.release_ritual_invoice,
                memo="terramon",
                verification_ref=self.release_ritual_ref,
            )
            if _ALBY.verify_payment(req):
                self.release_ritual_paid = True
                self.ritual_stars_pending = False  # defensive: both rails raced
                self.release_ritual_auto_verify = False
                self.release_ritual_verify_attempts = 0
                words = self.pending_words
                self.show_ritual_payment = False
                self._complete_ritual_release(words)
            else:
                if self.release_ritual_auto_verify:
                    # Auto poll tick (rx.moment passes a datetime): count it
                    # and keep polling WITHOUT touching agent_message — the
                    # KPI probe parses the «⚡ Ритуал отпускания:» marker.
                    # Give up gracefully at the bound: the manual button and
                    # «🔄 Новый инвойс» remain as the expiry escape hatch.
                    self.release_ritual_verify_attempts += 1
                    if self.release_ritual_verify_attempts >= RITUAL_RELEASE_VERIFY_MAX_ATTEMPTS:
                        self.release_ritual_auto_verify = False
                        self.release_ritual_verify_attempts = RITUAL_RELEASE_VERIFY_MAX_ATTEMPTS
                        self.agent_message = (
                            "⏳ Платёж не обнаружен — если ты оплатил, нажми "
                            "«✅ I've paid — verify», либо создай новый инвойс."
                        )
                else:
                    self.agent_message = "⏳ Ритуал не подтверждён — проверь, что инвойс оплачен."
        except Exception as e:
            log.warning(f"ritual verify failed: {e}")
            if self.release_ritual_auto_verify:
                # Same bounded poll path as not-settled: never clobber the
                # invoice marker while polling; give up gracefully at the bound.
                self.release_ritual_verify_attempts += 1
                if self.release_ritual_verify_attempts >= RITUAL_RELEASE_VERIFY_MAX_ATTEMPTS:
                    self.release_ritual_auto_verify = False
                    self.release_ritual_verify_attempts = RITUAL_RELEASE_VERIFY_MAX_ATTEMPTS
                    self.agent_message = (
                        "⏳ Платёж не обнаружен — если ты оплатил, нажми "
                        "«✅ I've paid — verify», либо создай новый инвойс."
                    )
            else:
                self.agent_message = f"⚡ Проверка не удалась: {getattr(e, 'message', e)}"

    @rx.event
    def refresh_ritual_invoice(self):
        """Escape hatch: re-issue the ritual BOLT11 when it expired (~1h Alby
        Hub default) or the bounded poller gave up. If the OLD invoice
        actually settled after the poller stopped, complete the ritual
        instead of regenerating over a paid payment — a paid win is never
        lost (mirrors the mint path's settle-on-verify)."""
        if self.release_ritual_ref and _ALBY.url:
            try:
                from terramon.ports.payment_port import PaymentRequest, PaymentMethod
                req = PaymentRequest(
                    id=self.release_ritual_ref,
                    method=PaymentMethod.LIGHTNING,
                    amount_sats=RITUAL_RELEASE_SATS,
                    destination=self.release_ritual_invoice,
                    memo="terramon",
                    verification_ref=self.release_ritual_ref,
                )
                if _ALBY.verify_payment(req):
                    self.release_ritual_paid = True
                    self.ritual_stars_pending = False
                    self.release_ritual_auto_verify = False
                    self.release_ritual_verify_attempts = 0
                    self.show_ritual_payment = False
                    self._complete_ritual_release(self.pending_words)
                    return
            except Exception as e:
                log.warning("ritual refresh pre-verify failed: %s", e)
        # No ref, Alby unconfigured, old invoice unpaid, or pre-verify
        # errored: regenerate BOLT11 + QR + ref. create_ritual_invoice
        # already resets attempts to 0 and re-arms release_ritual_auto_verify.
        self.create_ritual_invoice()

    @rx.event
    def pay_ritual_stars(self):
        """Stars rail for the ritual — payment-GATED (openInvoice callback).

        Opens the Telegram Stars invoice and waits for the REAL 'paid'
        status: complete_releases is only ever incremented in
        on_ritual_stars_status, never optimistically on click. While the
        invoice is open, ritual_stars_pending replaces the button with a
        waiting hint. Plain (non-generator) event: the pending delta must
        apply immediately while openInvoice is open, and the resolved
        callback value lands in on_ritual_stars_status (Reflex 0.9.x
        call_script callback= delivery).
        """
        if self.ritual_stars_pending:
            return
        self.ritual_stars_pending = True
        self.release_ritual_auto_verify = False  # one rail at a time — stops the Lightning poller's rx.moment
        self.agent_message = (
            "⭐ Stars-ритуал: оплати в Telegram — слова уйдут в мир после оплаты."
        )
        return rx.call_script(
            _RITUAL_STARS_JS.replace("__INVOICE_URL__", _STARS_INVOICE_URL),
            callback=TerramonState.on_ritual_stars_status,
        )

    @rx.event
    def on_ritual_stars_status(self, status: str):
        """openInvoice callback — the ONLY path that completes the Stars ritual.

        'paid' → words reach the world, complete_releases counts (the
        depth win is PAID by construction). 'cancelled' → the panel stays
        open, words stay with the player. 'failed'/'unavailable' (incl.
        None/empty) → panel stays open, Lightning or the free path remain.
        """
        self.ritual_stars_pending = False
        if status == "paid":
            self.release_ritual_paid = True
            self.show_ritual_payment = False
            self._complete_ritual_release(self.pending_words)
            self.agent_message = (
                "⭐ Ритуал оплачен — слова ушли в мир. Отпущено в мир: +1"
            )
        elif status == "cancelled":
            self.agent_message = (
                "⭐ Ритуал не оплачен (отменено) — слова остались с тобой. "
                "Можно повторить или отпустить без ритуала."
            )
        else:
            # 'failed' / 'unavailable' / None / '' — keep the panel open.
            self.agent_message = (
                "⭐ Stars-ритуал не прошёл — используй ⚡ Lightning (3000 sats) "
                "или отпусти без ритуала."
            )

    @rx.event
    def release_without_ritual(self):
        """Free legacy path — the creature goes free; words stay with the player."""
        self.show_ritual_payment = False
        self.release_ritual_auto_verify = False
        self.release_ritual_verify_attempts = 0
        self.ritual_stars_pending = False
        self.pending_words = ""
        self._do_release("", complete=False)

    def _complete_ritual_release(self, words: str) -> None:
        """The paid ritual fires: words reach the world, the depth win counts."""
        self._do_release(words, complete=True)

    def _do_release(self, words: str, complete: bool) -> None:
        """Shared release core.

        complete=True — the ritual was paid: final words are persisted,
        so the release counts toward complete_releases (the monetised
        depth win). complete=False — a free legacy release that never
        counts toward the depth win.
        """
        # Domain release — liberation, not death (needs frozen, words kept)
        try:
            _agent = CreatureAgent(
                agent_id=self.agent,
                archetype=self.agent,
                level=self.level,
                evolution_stage=self.agent_evolution,
                lat=self.agent_lat,
                lon=self.agent_lon,
                place_name=self.place,
            )
            _msg = _agent.release(words)
            self.agent_message = _msg.text
        except Exception as e:
            log.warning(f"Release failed: {e}")
            self.agent_message = "Something went wrong releasing this creature."

        # Reframe: record the release in the win counter
        try:
            _LOOP.progress.record_release(self.agent)
        except Exception as e:
            log.warning(f"record_release failed: {e}")

        # Depth win (prism roast, Lens #97): counts ONLY releases WITH
        # final words AND a real geo anchor — one thought lived all the
        # way through beats five archetype checkmarks. Only reachable
        # via the PAID ritual (complete=True).
        if complete:
            try:
                _complete = _LOOP.progress.record_complete_release(
                    words, self.agent_lat, self.agent_lon
                )
                if _complete:
                    self.complete_releases = int(_LOOP.progress.complete_releases)
            except Exception as e:
                log.warning(f"record_complete_release failed: {e}")

        # Publish CreatureReleased event (global map + Nostr, when configured)
        try:
            from terramon.events.creature_released import CreatureReleased
            import datetime
            _evt = CreatureReleased(
                agent_id=self.agent,
                agent_name=self.agent_name or self.agent,
                archetype=self.agent,
                thought_seed=self.thought,
                lat=self.agent_lat,
                lon=self.agent_lon,
                place_name=self.place,
                evolution_stage=self.agent_evolution,
                level=self.level,
                rarity=self.rarity,
                release_timestamp=datetime.datetime.now().isoformat(),
                previous_owner="player",
            )
            from terramon.adapters.nostr_publisher import NostrPublisher
            _pub = NostrPublisher()
            if _pub.seckey_hex:
                _pub.on_creature_released(_evt)
        except Exception as e:
            log.warning(f"Nostr publish for release failed: {e}")

        # Award ★ Wild Tamer badge (legacy badge kept)
        self.wild_tamer_badge = True

        # Receipt for the "Встреча, а не коллекция" moment
        self.released_place = self.place or self.geo_place or "неизвестное место"
        self.released_words = words
        self.released_just_now = True

        # Reset creature stats (removed from active care)
        self.agent_hunger = 0
        self.agent_energy = 0
        self.agent_happiness = 0
        self.agent_evolution = 0
        self.agent_name = ""
        self.agent_last_message = ""

        # Mark seed as released in memory
        try:
            seeds = _MEMORY.load_all_seeds()
            if seeds:
                for s in reversed(seeds):
                    if s.summoned_agent == self.agent and s.raw_input == self.thought:
                        s.status = "released"
                        break
        except Exception as e:
            log.warning(f"Failed to update seed status: {e}")

        # Persist the release: ritual persists final words (depth win,
        # Lens #97 — complete_releases survives a restart); the free
        # legacy path persists status only, so it never counts.
        try:
            if complete:
                _MEMORY.update_seed(
                    self.agent, self.thought, status="released", final_words=words
                )
            else:
                _MEMORY.update_seed(self.agent, self.thought, status="released")
        except Exception as e:
            log.warning(f"Release persistence failed: {e}")

        # Reload terra + refresh the released-based counter
        try:
            seeds = _MEMORY.load_all_seeds()
            self.terra = [_seed_to_card(s) for s in seeds]
        except Exception as e:
            log.warning(f"Terra reload after release failed: {e}")
        self._refresh_released_count()

    # ── P3 M04: Creature trading ──────────────────────────────────────

    @rx.event
    def set_trade_target(self, seed_id: int = 0, name: str = "", rarity: str = ""):
        """UI-facing setter: stores the tapped creature (Var-safe assignments only).
        The domain event show_trade_dialog() runs without Var args."""
        self.trade_target_id = seed_id
        self.trade_target_name = name
        self.trade_target_rarity = rarity

    @rx.event
    def open_trade_dialog(self):
        """Open the trade listing dialog for the creature selected via set_trade_target.

        Computes minimum price = embedding_uniqueness_score × base_price.
        """
        self.trade_price_input = ""
        self.trade_message = ""

        # Compute minimum price
        try:
            rarity = self.trade_target_rarity
            rarity_enum = Rarity(rarity) if rarity else Rarity.COMMON
            from terramon.domain.rarity import RARITY_PRICE
            base_price = RARITY_PRICE.get(rarity_enum, 0)
            if base_price > 0:
                # Try to get embedding uniqueness from the target seed
                seeds = _MEMORY.load_all_seeds()
                bonus = 1.0
                for s in seeds:
                    from terramon.adapters.json_memory import SqliteMemory
                    if isinstance(_MEMORY, SqliteMemory):
                        sid = getattr(s, 'id', None) or 0
                        if sid == self.trade_target_id and s.insight and s.insight.embedding:
                            bonus = _MEMORY.compute_uniqueness_bonus(s.insight.embedding)
                            break
                from terramon.application.payment_gate import PaymentGate
                self.trade_min_price = PaymentGate.compute_min_trade_price(bonus, base_price)
            else:
                self.trade_min_price = 1  # common/uncommon minimum
        except Exception:
            self.trade_min_price = 1

        self.show_trade_dialog = True

    @rx.event
    def hide_trade_dialog(self):
        """Close the trade listing dialog."""
        self.show_trade_dialog = False
        self.trade_target_id = 0
        self.trade_price_input = ""

    @rx.event
    def set_trade_price(self, value: str):
        """Update the price input for a trade listing."""
        self.trade_price_input = value

    @rx.event
    def confirm_list_for_trade(self):
        """List the creature for trade at the specified price."""
        price_str = self.trade_price_input.strip()
        if not price_str or not price_str.isdigit():
            self.trade_message = "⚠️ Enter a valid price."
            return

        price_sats = int(price_str)
        if price_sats < self.trade_min_price:
            self.trade_message = (
                f"⚠️ Minimum price is {self.trade_min_price} sats "
                f"(uniqueness bonus × base price)."
            )
            return

        try:
            import sqlite3
            conn = sqlite3.connect(str(_MEMORY.path))
            cursor = conn.execute(
                "UPDATE seeds SET for_trade = 1, trade_price_sats = ? WHERE id = ?",
                (price_sats, self.trade_target_id),
            )
            conn.commit()
            conn.close()
            if cursor.rowcount > 0:
                self.trade_message = (
                    f"✅ {self.trade_target_name} listed for {price_sats} sats!"
                )
                # Reload terra to reflect the updated status
                seeds = _MEMORY.load_all_seeds()
                self.terra = [_seed_to_card(s) for s in seeds]
            else:
                self.trade_message = "⚠️ Could not find creature to list."
        except Exception as e:
            log.warning(f"Trade listing failed: {e}")
            self.trade_message = "⚠️ Could not list for trade."

        self.show_trade_dialog = False

    @rx.event
    def load_trade_listings(self):
        """Load trade listings from the local database."""
        try:
            import sqlite3
            conn = sqlite3.connect(str(_MEMORY.path))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM seeds WHERE for_trade = 1 ORDER BY trade_price_sats ASC"
            ).fetchall()
            conn.close()
            self.trade_listings = [dict(r) for r in rows]
        except Exception as e:
            log.warning(f"Load trade listings failed: {e}")

    @rx.event
    def mint_creature(self):
        """Mint current creature — Stars rail (Telegram openInvoice).

        HONEST DESIGN DECISION (M7): Telegram Stars openInvoice has NO server
        callback in this MVP, so the mint record is OPTIMISTIC — recorded on
        click. Lightning (verify_lightning) mints only on invoice SETTLE.
        """
        if not self.has_summoned or self.price_sats <= 0:
            return
        if self._record_mint():
            self.agent_message = (
                f"💠 {self.agent} minted — a tradable collectible! "
                f"({self.mint_count} minted total)"
            )
        # Keep the Stars rail: open the Stars invoice in the TMA.
        return rx.call_script(
            f"if(window.Telegram?.WebApp?.openInvoice)Telegram.WebApp.openInvoice('{_STARS_INVOICE_URL}');"
        )

    @rx.event
    def mint_lightning(self):
        """Mint current creature via Lightning — BOLT11 invoice on the Alby Hub.

        M7 honest contract: Lightning mints ONLY on invoice SETTLE
        (verify_lightning → _record_mint), unlike Stars which is optimistic
        on click (openInvoice has no server callback). Same SILENT guards as
        mint_creature. The KPI probe parses the ⚡ agent_message markers —
        keep their wording byte-identical to pay_lightning.
        """
        if not self.has_summoned or self.price_sats <= 0:
            return
        if self.minted:
            self.agent_message = "💠 This creature is already minted."
            return
        if not _ALBY.url or not _ALBY.api_key:
            self.agent_message = "⚡ Lightning not configured yet — use Stars for now."
            return
        # Lightning rail invoices at the JIT-floor-clearing amount via
        # lightning_mint_price (>= LIGHTNING_MIN_MINT_SATS, above the Alby
        # Hub 2501-sat JIT floor) — NOT the raw Stars-typed price_sats.
        # (The mint area renders only when price_sats > 0, so free tiers
        # never reach this rail.)
        price = lightning_mint_price(self.price_sats)
        self.lightning_price = price
        try:
            req = _ALBY.create_payment(price, f"Terramon mint · {self.agent}")
            self.lightning_invoice = req.destination
            self.invoice_copied = False  # fresh invoice → clear copy feedback
            try:
                self.lightning_qr = _qr_data_uri(req.destination)
            except Exception:
                self.lightning_qr = ""
            self.lightning_ref = req.verification_ref
            self.lightning_checking = False
            # Auto-verify: arm the hidden rx.moment poller so the mint
            # records itself when the invoice settles — no click needed.
            self.lightning_auto_verify = True
            self.lightning_verify_attempts = 0
            self.agent_message = f"⚡ Invoice ready: {price} sats. Pay with any Lightning wallet."
        except Exception as e:
            log.error(f"mint_lightning failed: {e}", exc_info=True)
            self.agent_message = f"⚡ Invoice failed: {getattr(e, 'message', e)}"

    def _record_mint(self) -> bool:
        """The real mint record: persist minted/minted_at on the current seed
        and bump the counter. Idempotent — a creature is minted at most once
        (second mint = no-op, no double-count).

        Returns True when a NEW mint was recorded, False on no-op/failure.
        """
        if not self.agent or not self.thought:
            return False
        if self.minted:
            self.agent_message = "💠 This creature is already minted."
            return False
        import datetime as _dt
        now = _dt.datetime.now().isoformat(timespec="seconds")
        # Persisted guard: survive a session reload (self.minted may be stale).
        try:
            already, _ = _MEMORY.get_mint_state(self.agent, self.thought)
        except Exception:
            already = False
        if already:
            self.minted = True
            self.minted_at = now
            return False
        try:
            ok = bool(
                _MEMORY.update_seed(
                    self.agent, self.thought, minted=True, minted_at=now
                )
            )
        except Exception as e:
            log.warning(f"Mint persistence failed: {e}")
            ok = False
        if not ok:
            self.agent_message = "💠 Mint failed — creature record not found."
            return False
        self.minted = True
        self.minted_at = now
        self.mint_count += 1
        try:
            _LOOP.progress.mint_count += 1
        except Exception:
            pass
        return True

    # ── I10: Stasis caretaker ─────────────────────────────────────────

    @rx.event
    def activate_stasis(self):
        """Activate stasis — pause all decay for 24h (7-day cooldown)."""
        import time as _time
        if _time.time() < self.stasis_cooldown_until:
            self.agent_message = "⏳ Stasis is on cooldown. Wait 7 days."
            return
        self.stasis_active = True
        self.stasis_cooldown_until = _time.time() + 7 * 86400
        self.agent_message = "💤 Stasis activated. Your creature rests for 24h."

    @rx.event
    def deactivate_stasis(self):
        """Manually deactivate stasis early."""
        self.stasis_active = False
        self.agent_message = "✨ Stasis deactivated. Your creature stirs."

    @rx.event
    def buy_stars(self):
        """F3 — Telegram Stars rail: MINT the current creature for 1 Star.

        Same honest MVP contract as mint_creature: Telegram Stars
        openInvoice has NO server callback, so the mint record is written
        OPTIMISTICALLY on click (idempotent _record_mint, see above).
        The gate ALWAYS closes (unlocked=True) — the player keeps their
        creature even while _STARS_INVOICE_URL is a placeholder.
        Lightning stays the BTC-first primary (mints on settle, see
        verify_lightning). No price_sats guard here on purpose: the F3
        gate price is FIXED (GATE_SUMMON_STARS), independent of the last
        creature's tier, which is 0 for free tiers.
        """
        if not self.has_summoned:
            return
        # Stars mint: optimistic record — openInvoice has no callback.
        if self._record_mint():
            self.agent_message = (
                f"💠 {self.agent} minted — a tradable collectible! "
                f"({self.mint_count} minted total)"
            )
        self.unlocked = True  # gate closes on click — same UX as today
        return rx.call_script(
            f"if(window.Telegram?.WebApp?.openInvoice)Telegram.WebApp.openInvoice('{_STARS_INVOICE_URL}');"
        )

    @rx.event
    def pay_lightning(self):
        """BTC-first: create a BOLT11 invoice on the self-custodial Alby Hub node.
        Player pays with any Lightning wallet; sats settle straight to the node."""
        if not _ALBY.url or not _ALBY.api_key:
            self.agent_message = "⚡ Lightning not configured yet — use Stars for now."
            return
        # F3 gate price: fixed summon-again price, NOT the last creature's tier
        # (which is 0 for free tiers → the button previously did nothing).
        price = GATE_SUMMON_PRICE_SATS
        self.lightning_price = price
        try:
            req = _ALBY.create_payment(price, f"Terramon summon · {self.thought[:40]}")
            self.lightning_invoice = req.destination
            self.invoice_copied = False  # fresh invoice → clear copy feedback
            try:
                self.lightning_qr = _qr_data_uri(req.destination)
            except Exception:
                self.lightning_qr = ""
            self.lightning_ref = req.verification_ref
            self.lightning_checking = False
            # Auto-verify: arm the hidden rx.moment poller so the gate
            # unlocks itself when the invoice settles — no click needed.
            self.lightning_auto_verify = True
            self.lightning_verify_attempts = 0
            self.agent_message = f"⚡ Invoice ready: {price} sats. Pay with any Lightning wallet."
        except Exception as e:
            log.error(f"pay_lightning failed: {e}", exc_info=True)
            self.agent_message = f"⚡ Invoice failed: {getattr(e, 'message', e)}"

    @rx.event
    def mark_invoice_copied(self):
        """BOLT11 copy feedback flag — flips invoice_copied so the panel can
        show '✓ Инвойс скопирован'. Deliberately does NOT touch agent_message:
        the KPI probe parses the '⚡ Invoice ready' marker from it."""
        self.invoice_copied = True

    @rx.event
    def verify_lightning(self, _tick=None):
        """Check whether the BOLT11 invoice was settled on the hub; unlock on success.

        Auto-verify: called every LIGHTNING_VERIFY_INTERVAL_MS by the hidden
        rx.moment poller (rx.moment passes the current datetime — swallowed by
        _tick) AND by the manual «✅ I've paid — verify» button (no arg). On
        settle the mint records itself with no click; polling is bounded and
        falls back to the manual button with a clear marker. While polling,
        agent_message is never touched — the KPI probe parses the
        "⚡ Invoice ready: ..." marker within seconds of the mint click.
        """
        if not self.lightning_ref or not _ALBY.url:
            # Stale timer after a new invoice / panel teardown: stop the poll
            # silently — never clobber the invoice marker the KPI probe parses.
            if self.lightning_auto_verify:
                self.lightning_auto_verify = False
                self.lightning_verify_attempts = 0
                return
            self.agent_message = "⚡ Create an invoice first (Pay with Lightning)."
            return
        is_auto = self.lightning_auto_verify
        self.lightning_checking = True
        try:
            from terramon.ports.payment_port import PaymentRequest, PaymentMethod
            req = PaymentRequest(
                id=self.lightning_ref,
                method=PaymentMethod.LIGHTNING,
                # Verify the amount ACTUALLY invoiced (lightning_price): the
                # gate invoices at GATE_SUMMON_PRICE_SATS while a creature's
                # price_sats is 0 for free tiers — verifying the stale
                # creature price alone would mismatch every gate invoice.
                amount_sats=self.lightning_price or self.price_sats,
                destination=self.lightning_invoice,
                memo="terramon",
                verification_ref=self.lightning_ref,
            )
            if _ALBY.verify_payment(req):
                self.unlocked = True
                self.lightning_checking = False
                # Auto-verify done — the invoice settled, stop the poller.
                self.lightning_auto_verify = False
                self.lightning_verify_attempts = 0
                # M7: Lightning mints on SETTLE — the invoice really was paid.
                if self._record_mint():
                    self.agent_message = (
                        f"✅ Payment received! 💠 {self.agent} minted — "
                        f"a tradable collectible. ({self.mint_count} minted total)"
                    )
                else:
                    self.agent_message = "✅ Payment received! Your thought is free to summon."
            else:
                if is_auto:
                    # Poll tick: count it and keep polling WITHOUT touching
                    # agent_message (the KPI probe parses the invoice-ready
                    # marker). Give up gracefully at the bound — the manual
                    # button remains as the fallback.
                    self.lightning_verify_attempts += 1
                    self.lightning_checking = False
                    if self.lightning_verify_attempts >= LIGHTNING_VERIFY_MAX_ATTEMPTS:
                        self.lightning_auto_verify = False
                        self.agent_message = "⏳ Payment not detected yet — press «✅ I've paid — verify» once you've paid."
                else:
                    self.lightning_checking = False
                    self.agent_message = "⏳ Not settled yet — waiting for the payment to confirm."
        except Exception as e:
            log.error(f"verify_lightning failed: {e}", exc_info=True)
            self.lightning_checking = False
            if is_auto:
                # Same bounded poll path as not-settled: never clobber the
                # invoice marker while polling; give up gracefully at the bound.
                self.lightning_verify_attempts += 1
                if self.lightning_verify_attempts >= LIGHTNING_VERIFY_MAX_ATTEMPTS:
                    self.lightning_auto_verify = False
                    self.agent_message = "⏳ Payment not detected yet — press «✅ I've paid — verify» once you've paid."
            else:
                self.agent_message = f"⚡ Verify failed: {getattr(e, 'message', e)}"

    @rx.event
    def light_candle(self):
        """«Зажечь свечу» — the emotional monetization ritual.

        A 500-sat Lightning zap from the player's OWN browser wallet via
        WebLN (Alby extension). No invoice node needed: keysend is a push
        payment, so the Alby Hub's 2501-sat JIT floor never applies. The
        reward is a NEW creature line appended to its memory — words, not
        cosmetics. Deterministic template: ZERO LLM calls on this path.

        Flow: inline JS (same pattern as the HapticFeedback literal) checks
        window.webln → enable() → keysend (fallback: sendPayment) → the
        result dict comes back here via the rx.call_script yield.
        """
        if not self.released_just_now and not seed_is_released(
            _MEMORY, self.agent, self.thought
        ):
            self.agent_message = "🕯️ Свечу можно зажечь только у отпущенного существа."
            return
        if self.candle_lit:
            self.agent_message = "🕯️ Свеча уже горит. Огонь помнит тебя."
            return
        self.candle_state = "paying"
        self.candle_reason = ""
        try:
            payload = yield rx.call_script(candle_js())
        except Exception as e:
            log.warning(f"light_candle JS failed: {e}")
            payload = {"ok": False, "reason": "error"}
        outcome = candle_outcome(payload)
        if outcome["state"] == "lit":
            lore = candle_lore_for(self.released_words or self.final_words)
            self.candle_lore = lore
            self.candle_lit = True
            self.candle_state = "lit"
            self.agent_message = "🔥 Свеча зажжена. Существо ответило тебе."
            # Persist on the creature seed (survives reloads) — silent fail.
            if not persist_candle_lore(_MEMORY, self.agent, self.thought, lore):
                log.warning("candle_lore persistence failed for %s", self.agent)
            try:
                seeds = _MEMORY.load_all_seeds()
                self.terra = [_seed_to_card(s) for s in seeds]
            except Exception as e:
                log.warning(f"Terra reload after candle failed: {e}")
        elif outcome["state"] == "nowebln":
            self.candle_state = "nowebln"
            self.candle_reason = "nowebln"
            self.agent_message = "⚡ Установи Alby-кошелёк, чтобы зажечь свечу."
        else:
            self.candle_state = "failed"
            self.candle_reason = outcome["reason"]
            self.agent_message = (
                "⚡ Зажжение не удалось ("
                + (outcome["reason"] or "error")
                + "). Попробуй ещё раз."
            )

    @rx.event
    def share_creature(self):
        """Copy shareable creature card to clipboard (virality)."""
        if not self.has_summoned:
            return
        # M6 share counter: record EVERY share attempt on the persisted
        # share registry (JsonMemory.record_share) for the /health KPI.
        _MEMORY.record_share()
        _place = self.place or self.geo_place
        if not _place and self.agent_lat and self.agent_lon:
            _place = f"{self.agent_lat:.2f}, {self.agent_lon:.2f}"
        if _place == "0.00, 0.00":
            _place = ""
        _place_line = f"📍 {_place}\n" if _place else ""
        if self.share_code:
            _link = f"🔗 https://t.me/terrramonBot/terramon?startapp=share_{self.share_code}"
        else:
            _link = "🌍 https://t.me/terrramonBot/terramon"
        card = (
            f"🃏 Terramon — {self.agent}\n"
            f"✦ Rarity: {self.rarity} {self.sigil}\n"
            f"   \"{self.thought}\"\n"
            f"Lv.{self.level} · Отпущено в мир: {self.complete_releases}\n"
            f"{_place_line}"
            f"{_link}"
        )
        yield rx.set_clipboard(card)
        self.agent_message = "📤 Creature card copied! Share it anywhere."

    # ── M02: Geo-tournament interaction ────────────────────────────────

    @rx.event
    def accept_tournament(self):
        """Accept the pending tournament offer."""
        if not self.tournament_id:
            return
        battle = _TOURNAMENT_SVC.accept(self.tournament_id, "player_default")
        if battle:
            self.tournament_status = battle.status.value
            self.agent_message = "✅ Tournament accepted! Both sides ready."
            # Both accepted → resolve automatically
            if battle.both_accepted:
                resolved = _TOURNAMENT_SVC.resolve(self.tournament_id)
                if resolved:
                    self.tournament_status = resolved.status.value
                    self.tournament_score_a = resolved.score_a
                    self.tournament_score_b = resolved.score_b
                    self.tournament_winner_id = resolved.winner_id
                    self.tournament_xp_gained = resolved.xp_awarded_to_winner
                    self.tournament_count += 1
                    if resolved.winner_id == "player_default":
                        self.agent_message = (
                            f"🏆 Tournament VICTORY! "
                            f"+{resolved.xp_awarded_to_winner} XP!"
                        )
                        self.xp += resolved.xp_awarded_to_winner
                    else:
                        self.agent_message = (
                            f"💪 Tournament lost. "
                            f"+{resolved.xp_awarded_to_loser} consolation XP."
                        )
                        self.xp += resolved.xp_awarded_to_loser
        else:
            self.agent_message = "⚠️ Tournament not found or already resolved."

    @rx.event
    def decline_tournament(self):
        """Decline the pending tournament offer."""
        if not self.tournament_id:
            return
        _TOURNAMENT_SVC.decline(self.tournament_id, "player_default")
        self.tournament_status = "declined"
        self.tournament_id = ""
        self.tournament_offer_text = ""
        self.agent_message = "🚫 Tournament declined."

    @rx.event
    def dismiss_tournament(self):
        """Dismiss a completed/expired tournament notification."""
        self.tournament_id = ""
        self.tournament_status = ""
        self.tournament_offer_text = ""
        self.tournament_score_a = 0.0
        self.tournament_score_b = 0.0
        self.tournament_winner_id = ""
        self.tournament_xp_gained = 0

    def _apply_tick_decay(self):
        """Apply stat decay based on elapsed time (Phase 6: state machine + EMA).

        Uses the CreatureAgent's _apply_tick() core logic so the TMA's
        batch tick decay is consistent with the canonical implementation.
        Called from load_terra() on every app open.

        I10: Passes stasis state to the temp agent and checks for auto-graze
        to notify the player on return.
        """
        import datetime
        if not self.last_tick:
            self.last_tick = datetime.datetime.now().isoformat()
            return
        try:
            last_dt = datetime.datetime.fromisoformat(self.last_tick)
            hours = (datetime.datetime.now() - last_dt).total_seconds() / 3600
            ticks = min(int(hours), 48)

            # Use the canonical CreatureAgent tick logic
            from terramon.domain.creature_agent import CreatureAgent
            from tools.time_tool import get_day_phase

            day_phase = get_day_phase()
            temp = CreatureAgent(
                agent_id="_tick",
                hunger=self.agent_hunger or 80,
                energy=self.agent_energy or 80,
                happiness=self.agent_happiness or 60,
                # I10: Pass stasis state to survive across batch ticks
                stasis_active=self.stasis_active,
                stasis_activated_at=self.stasis_cooldown_until,  # not used on batch
                stasis_cooldown_until=self.stasis_cooldown_until,
            )
            graze_happened = False
            for _ in range(ticks):
                temp._apply_tick(day_phase)
                if temp.grazed_while_away:
                    graze_happened = True
                    temp.grazed_while_away = False  # reset for next tick

            self.agent_hunger = temp.hunger
            self.agent_energy = temp.energy
            self.agent_happiness = temp.happiness
            self.last_tick = datetime.datetime.now().isoformat()

            # I10: Sync stasis state back (auto-deactivation during tick loop)
            self.stasis_active = temp.stasis_active

            # I10: Notify player if auto-graze happened while away
            if graze_happened and hours > 1:
                self.grazed_away_message = (
                    "🌿 Your creature grazed while you were away. "
                    "Its happiness kept it nourished."
                )
            else:
                self.grazed_away_message = ""
        except (ValueError, TypeError):
            self.last_tick = datetime.datetime.now().isoformat()

    # ── Phase 19: Creature state recomputation ───────────────

    def _recompute_creature_state(self):
        """Recompute creature state + mood from current stats (after care actions)."""
        try:
            from terramon.domain.creature_agent import CreatureAgent
            from tools.time_tool import get_day_phase
            _phase = get_day_phase()
            self.day_phase = "night" if _phase == "night" else "day"
            _c = CreatureAgent(
                agent_id="_recompute",
                hunger=self.agent_hunger, energy=self.agent_energy,
                happiness=self.agent_happiness,
            )
            self.creature_state = _c.state.value
            self.creature_mood = _c.mood
        except Exception as e:
            log.warning(f"State recompute failed: {e}")

    @rx.event
    def run_scout(self):
        """Run the Scout agent on the current thought seed in a background thread."""
        if not self.thought.strip() or self.scout_running:
            return
        self.scout_running = True
        self.scout_result = ""
        import threading
        _text = self.thought
        def _scout_thread():
            try:
                from main import run_scout
                import io, contextlib
                _buf = io.StringIO()
                with contextlib.redirect_stdout(_buf):
                    run_scout(_text)
                self.scout_result = _buf.getvalue()
            except Exception as _e:
                log.warning(f"Scout failed: {_e}")
                self.scout_result = f"⚠️ Scout error: {_e}"
            finally:
                self.scout_running = False
        threading.Thread(target=_scout_thread, daemon=True).start()

    @rx.event
    def refresh_portrait(self):
        """Refresh the current creature's portrait from the registry.

        Lesson 13: the portrait is the thought vector made visible — look it
        up in the content-addressed registry (blake2b(thought, archetype,
        rarity)) and expose it as a local /creature-art URL. The current
        creature is the LAST seed, so this never depends on localStorage
        restore order. Silent fail: sigil fallback while art is drawing.
        """
        try:
            seeds = _MEMORY.load_all_seeds()
            if not seeds:
                return
            s = seeds[-1]
            from terramon.application.portrait_gen import get_portrait
            _rarity = s.rarity if isinstance(s.rarity, str) else s.rarity.value
            _p = get_portrait(s.raw_input, s.summoned_agent, _rarity)
            if _p:
                self.agent_portrait = creature_art_url(_p)
        except Exception as e:
            log.debug(f"Portrait refresh skipped: {e}")

    @rx.event
    def poll_portrait(self, _tick=None):
        """Bounded portrait poller (mirrors the lightning rx.moment pattern).

        The FAL generation thread cannot touch Reflex state, so while
        portrait_pending is armed this polls the registry every 4s; once the
        art lands it refreshes the main card AND the whole terra grid, then
        disarms. No-op when not pending — cheap forever-tick.
        """
        if not self.portrait_pending:
            return
        self.refresh_portrait()
        if self.agent_portrait != "":
            self.portrait_pending = False
            try:
                seeds = _MEMORY.load_all_seeds()
                self.terra = [_seed_to_card(s) for s in seeds]
            except Exception as _e:
                log.debug(f"Terra portrait refresh skipped: {_e}")


def _portrait_url_for(seed: ThoughtSeed) -> str:
    """Resolve a seed's cached portrait to a local /creature-art URL ('' if none)."""
    try:
        from terramon.application.portrait_gen import get_portrait
        _rarity = seed.rarity if isinstance(seed.rarity, str) else seed.rarity.value
        _p = get_portrait(seed.raw_input, seed.summoned_agent, _rarity)
        if _p:
            return creature_art_url(_p)
    except Exception:
        pass
    return ""


def _seed_to_card(seed: ThoughtSeed) -> dict:
    rarity = seed.rarity if isinstance(seed.rarity, str) else seed.rarity.value
    card = {
        "id": getattr(seed, "id", 0),  # stable contract: trade/select need the DB id
        "agent": seed.summoned_agent,
        "rarity": rarity,
        "sigil": _RARITY_SIGIL.get(rarity, "·"),
        "color": _RARITY_COLOR.get(rarity, "#9ca3af"),
        "thought": seed.raw_input,
        "lore": _ARCHETYPE_LORE.get(seed.summoned_agent, "A thought made flesh."),
        "timestamp": seed.timestamp,
        "insight": f"INSIGHT: {seed.insight.therefore}" if seed.insight else "",
        "released": seed.status == "released",
        # Candle ritual: the creature's new line ('' = candle never lit)
        "candle_lore": getattr(seed, "candle_lore", ""),
        # M7: the creature became a minted collectible
        "minted": bool(getattr(seed, "minted", False)),
        # P3 M04: Trade info
        "for_trade": getattr(seed, 'for_trade', False),
        "trade_price_sats": getattr(seed, 'trade_price_sats', 0),
        # G04: geographic anchor — lat/lon for static map, place name fallback.
        # Stable contract: keys ALWAYS present (None when no geo) so the UI layer
        # can index them directly without .get() (Var has no .get in Reflex 0.9.8).
        "lat": getattr(seed, "lat", None),
        "lon": getattr(seed, "lon", None),
        "place": getattr(seed, "place_name", "")
                 or (f"{getattr(seed, 'lat', 0):.2f}, {getattr(seed, 'lon', 0):.2f}" if getattr(seed, "lat", None) is not None else ""),
        # Lesson 13: cached FAL portrait → local URL ('' = art still drawing)
        "portrait": _portrait_url_for(seed),
    }
    return card


def hydrate_from_memory(
    memory: JsonMemory, seeds: list[ThoughtSeed] | None = None
) -> dict:
    """Seed-derived hydration of the TMA collection state (redeploy-safe).

    M4: the collection used to live in-memory (TerramonState fields +
    GameLoop._LOOP) and was wiped on every Railway redeploy, while the
    creature seeds survived on the volume (data/*.jsonl). This rebuilds
    the UI counters from the persisted seeds so a redeploy NEVER shows
    an empty collection and never re-opens the summon gate that caused
    4× duplicate Hero seeds.

    Returns a plain dict of the state fields load_terra mirrors.
    """
    if seeds is None:
        seeds = memory.load_all_seeds()
    progress = PlayerProgress.from_seeds(seeds)
    progress.recalculate_tier()
    return {
        "terra": [_seed_to_card(s) for s in seeds],
        "summon_count": len(seeds),
        "has_summoned": bool(seeds),
        "distinct": progress.distinct_count,
        "xp": progress.xp,
        "level": progress.level,
        "goal": progress.goal_distinct,
        "goal_reached": progress.distinct_count >= progress.goal_distinct,
        "released_count": progress.released_count(),
        "complete_releases": progress.complete_releases,
        "summon_streak": progress.summon_streak,
        "tier_name": progress.current_tier_name,
        "tier_badge": progress.current_tier_badge,
        "next_tier_name": progress.next_tier_name,
        "next_tier_distinct": progress.next_tier_requirement,
    }


def terra_card(item: dict) -> rx.Component:
    """One creature in the terra grid. SIN 7 FIX: hover scale-up.
    I12: Released creatures show with a memorial badge & muted styling.
    P3 M04: "List for Trade" button on non-released creatures.
    """
    return rx.box(
        rx.vstack(
            # I12: Released badge for wild creatures
            rx.cond(
                item["released"],
                rx.hstack(
                    rx.text("\U0001f54a\ufe0f", font_size="0.7em"),
                    rx.text("WILD", font_size="0.5em", color="#6b7280",
                            font_weight="bold", letter_spacing="0.1em"),
                    spacing="1",
                    align="center",
                    background="#1a1a24",
                    border="1px solid #27272a",
                    border_radius="999px",
                    padding="0.1em 0.5em",
                ),
                rx.fragment(),
            ),
            rx.cond(
                item["portrait"] != "",
                rx.image(
                    src=item["portrait"],
                    width="100%",
                    height="auto",
                    border_radius="8px",
                    border="1px solid #27272a",
                    opacity=rx.cond(item["released"], "0.6", "1.0"),
                ),
                rx.text(
                    item["sigil"],
                    font_size="1.8em",
                    letter_spacing="0.2em",
                    color=rx.cond(item["released"], "#6b7280", item["color"]),
                    text_shadow=f"0 0 16px {item['color']}66",
                ),
            ),
            rx.heading(item["agent"], size="5",
                       color=rx.cond(item["released"], "#6b7280", item["color"])),
            rx.text(item["thought"], font_style="italic",
                    color="#9ca3af", font_size="0.75em", max_width="200px"),
            # G04: birthplace (map image if BOTH real coords present, else place text)
            # Fix: lat/lon default to 0.0 when no geo — `!= None` passed for 0,
            # rendering an open-ocean map at (0,0). Require non-None AND non-zero.
            # NOTE: Reflex Vars do NOT support `in`/`not in` — bitwise ops only.
            rx.cond(
                (item["lat"] != None) & (item["lat"] != 0) & (item["lon"] != None) & (item["lon"] != 0),
                rx.image(
                    src=static_map_endpoint_path(item["lat"], item["lon"], zoom=14, width=280, height=160),
                    width="100%",
                    height="auto",
                    border_radius="6px",
                    border="1px solid #27272a",
                    opacity=rx.cond(item["released"], "0.6", "1.0"),
                ),
                rx.cond(
                    item["place"],
                    rx.hstack(
                        rx.text("\U0001f4cd", font_size="0.7em"),
                        rx.text(item["place"], font_size="0.65em", color="#6b7280"),
                        spacing="1",
                        align="center",
                    ),
                    rx.fragment(),
                ),
            ),
            # P3 M04: Trade button inside the vstack (positional args before keywords)
            rx.cond(
                ~item["released"],
                rx.cond(
                    item["for_trade"],
                    rx.box(
                        rx.text(
                            f"↔ Trading · {item['trade_price_sats']} sats",
                            font_size="0.55em", color="#f59e0b",
                            font_weight="bold",
                            background="rgba(245,158,11,0.1)",
                            border="1px solid #f59e0b44",
                            border_radius="999px",
                            padding="0.1em 0.5em",
                            margin_top="0.3em",
                        ),
                    ),
                    rx.button(
                        "↔ List for Trade",
                        on_click=[
                            TerramonState.set_trade_target(
                                item["id"], item["agent"], item["rarity"]
                            ),
                            TerramonState.open_trade_dialog,
                        ],
                        size="1",
                        variant="ghost",
                        color_scheme="amber",
                        font_size="0.55em",
                        width="100%",
                        margin_top="0.3em",
                        _hover={"opacity": "0.8"},
                    ),
                ),
                rx.fragment(),
            ),
            spacing="1",
            align="center",
        ),
        border="1px solid #27272a",
        border_left=f"3px solid {item['color']}",
        border_radius="12px",
        padding="0.8em",
        background=rx.cond(item["released"], "#111115", "#141418"),
        width="100%",
        opacity=rx.cond(item["released"], "0.7", "1.0"),
        _hover=rx.cond(
            item["released"],
            {},
            {"transform": "scale(1.02)", "border_color": item["color"]},
        ),
        style={"transition": "transform 0.15s ease, border-color 0.15s ease"},
    )


def progress_header() -> rx.Component:
    """FIX 3 + SIN 6: always-visible progression with animated XP bar."""
    return rx.box(
        rx.vstack(
            rx.text(
                "Отпущено в мир: " + TerramonState.complete_releases.to_string(),
                color="#e5e7eb",
                font_size="0.85em",
                font_weight="bold",
                letter_spacing="0.04em",
            ),
            # SIN 6: animated XP bar via inline style width
            rx.box(
                rx.box(
                    style={
                        "width": TerramonState.xp_into_level.to_string() + "%",
                        "height": "100%",
                        "background": "linear-gradient(90deg, #f59e0b, #d97706)",
                        "border_radius": "999px",
                        "transition": "width 0.4s ease",
                    },
                ),
                width="100%",
                height="10px",
                background="#27272a",
                border_radius="999px",
                overflow="hidden",
            ),
            rx.text(
                TerramonState.xp.to_string() + " XP",
                color="#6b7280",
                font_size="0.7em",
            ),
            # Depth win (Lens #97): badge earned by ONE complete release —
            # a thought let go with final words at a real place.
            rx.cond(
                TerramonState.complete_releases >= 1,
                rx.text("★ Встретивший", color="#f59e0b", font_size="0.75em",
                        font_weight="bold"),
                rx.fragment(),
            ),
            spacing="1",
            align="center",
            width="100%",
        ),
        width="100%",
        max_width="380px",
        padding="0 0.2em",
    )


def creature_care_panel() -> rx.Component:
    """Tamagotchi×Pokemon interaction panel — shows stats + interaction buttons."""
    return rx.cond(
        TerramonState.has_summoned,
        rx.box(
            rx.vstack(
                # Agent name + evolution stage
                rx.hstack(
                    rx.text(TerramonState.agent_name, font_size="0.85em",
                            color="#e5e7eb", font_weight="bold"),
                    rx.cond(
                        TerramonState.agent_evolution > 0,
                        rx.text("✦ Evolved", font_size="0.7em",
                                color=rx.cond(TerramonState.evolve_animating, "#ffd700", "#f59e0b"),
                                text_shadow=rx.cond(
                                    TerramonState.evolve_animating,
                                    "0 0 20px rgba(255,215,0,0.8)",
                                    "none",
                                ),
                                style=rx.cond(
                                    TerramonState.evolve_animating,
                                    {"animation": "celebrationSparkle 0.5s ease-in-out 3"},
                                    {},
                                ),
                        ),
                        rx.fragment(),
                    ),
                    # M7: minted collectible badge — GameBoy style, amber/gold
                    rx.cond(
                        TerramonState.minted,
                        rx.hstack(
                            rx.text("💠", font_size="0.8em"),
                            rx.text("MINTED", font_size="0.55em", color="#fbbf24",
                                    font_weight="bold", letter_spacing="0.12em"),
                            spacing="1",
                            align="center",
                            background="#1a1405",
                            border="1px solid #fbbf2444",
                            border_radius="999px",
                            padding="0.15em 0.6em",
                        ),
                        rx.fragment(),
                    ),
                    spacing="2",
                ),
                # G04: birthplace map + TERRA vision — the creature opens its eyes
                # on its birthplace. (Formerly stranded in the removed creature_card();
                # index() only renders this LIVE panel, so this map block, the MINT
                # button and the Share button all live here.)
                rx.cond(
                    TerramonState.static_map_url != "",
                    rx.box(
                        rx.image(
                            src=TerramonState.static_map_url,
                            width="100%",
                            height="auto",
                            border_radius="8px",
                            border="1px solid #27272a",
                        ),
                        rx.cond(
                            TerramonState.place != "",
                            rx.text(TerramonState.place, font_size="0.65em",
                                    color="#6b7280", text_align="center", margin_top="0.3em"),
                            rx.fragment(),
                        ),
                        # TERRA vision: creature opens its eyes on its birthplace
                        rx.cond(
                            TerramonState.home_lore != "",
                            rx.text(
                                TerramonState.home_lore,
                                font_size="0.7em",
                                color="#d4d4d8",
                                font_style="italic",
                                text_align="center",
                                margin_top="0.3em",
                                padding="0.4em 0.6em",
                                background="rgba(255,255,255,0.04)",
                                border_radius="6px",
                                border="1px solid #27272a",
                            ),
                            rx.cond(
                                TerramonState.home_lore_loading,
                                rx.text("👁 the creature opens its eyes...",
                                        font_size="0.7em", color="#f59e0b",
                                        font_style="italic", text_align="center",
                                        margin_top="0.3em"),
                                rx.button(
                                    "👁 Open your eyes",
                                    on_click=TerramonState.see_birthplace,
                                    size="1", variant="ghost", color_scheme="gray",
                                    font_size="0.65em", margin_top="0.3em",
                                ),
                            ),
                        ),
                        width="100%",
                    ),
                    rx.cond(
                        TerramonState.place != "",
                        rx.hstack(
                            rx.text("📍", font_size="0.8em"),
                            rx.text(TerramonState.place, font_size="0.75em",
                                    color="#6b7280", font_style="italic"),
                            spacing="1",
                            align="center",
                        ),
                        rx.fragment(),
                    ),
                ),
                # SIN 8: MINT with explanation tooltip (+ Lightning rail)
                rx.cond(
                    TerramonState.price_sats > 0,
                    rx.cond(
                        TerramonState.can_mint,
                        rx.vstack(
                            rx.tooltip(
                                rx.button(
                                    "⚡ MINT · " + TerramonState.price_sats.to_string() + " Stars",
                                    on_click=TerramonState.mint_creature,
                                    background=TerramonState.color,
                                    color="#0b0b0f",
                                    width="100%",
                                    _hover={"transform": "scale(1.02)", "opacity": "0.9"},
                                    style={"transition": "all 0.15s ease"},
                                ),
                                content="Mint this creature to Telegram Stars — tradable collectible on-chain",
                            ),
                            # '⚡ Mint via Lightning' — honest sats price via lightning_button_label
                            rx.button(
                                TerramonState.lightning_button_label,
                                on_click=TerramonState.mint_lightning,
                                variant="surface",
                                size="1",
                                color_scheme="yellow",
                                width="100%",
                            ),
                            spacing="1",
                            width="100%",
                        ),
                        rx.text("locked · train more", color="#6b7280", font_size="0.85em"),
                    ),
                    rx.text("free summon", color="#6b7280", font_size="0.85em"),
                ),
                # M7 Lightning mint: shared invoice panel (self-gates on
                # lightning_invoice != '' — appears after mint_lightning runs)
                _lightning_invoice_panel(),
                # Phase 4: Share button (virality)
                rx.button(
                    "📤 Share",
                    on_click=TerramonState.share_creature,
                    variant="surface", size="2", width="100%",
                    color_scheme="gray",
                    margin_top="0.25em",
                ),
                # Phase 19: Creature state + mood + day/night indicator
                rx.hstack(
                    rx.cond(
                        TerramonState.day_phase == "night",
                        rx.text("🌙 Night · ", font_size="0.65em", color="#6366f1"),
                        rx.text("☀️ Day · ", font_size="0.65em", color="#f59e0b"),
                    ),
                    rx.text(
                        rx.cond(
                            TerramonState.creature_mood == "cheerful",
                            "😊 ",
                            rx.cond(
                                TerramonState.creature_mood == "distressed",
                                "😰 ",
                                "😐 ",
                            ),
                        ),
                        font_size="0.7em", color="#9ca3af",
                    ),
                    rx.text(TerramonState.creature_state.upper(),
                            font_size="0.65em", color="#9ca3af"),
                    spacing="1",
                    align="center",
                ),
                # Stat bars — bound to state vars (WAS hardcoded 50% — Lens #55 roast)
                # I14: numeric overlays
                rx.hstack(
                    rx.text("🍽️ Hunger", font_size="0.7em", color="#9ca3af"),
                    rx.text(TerramonState.agent_hunger.to_string() + "/100",
                            font_size="0.7em", color="#f59e0b", font_weight="bold"),
                    justify="between",
                    width="100%",
                ),
                rx.box(
                    rx.box(
                        style={"width": TerramonState.agent_hunger.to_string() + "%",
                               "height": "100%",
                               "background": "linear-gradient(90deg, #f59e0b, #f59e0bdd)",
                               "border_radius": "999px",
                               "transition": "width 0.3s ease"},
                    ),
                    width="100%", height="8px",
                    background="#27272a", border_radius="999px", overflow="hidden",
                ),
                rx.hstack(
                    rx.text("⚡ Energy", font_size="0.7em", color="#9ca3af"),
                    rx.text(TerramonState.agent_energy.to_string() + "/100",
                            font_size="0.7em", color="#22c55e", font_weight="bold"),
                    justify="between",
                    width="100%",
                ),
                rx.box(
                    rx.box(
                        style={"width": TerramonState.agent_energy.to_string() + "%",
                               "height": "100%",
                               "background": "linear-gradient(90deg, #22c55e, #22c55edd)",
                               "border_radius": "999px",
                               "transition": "width 0.3s ease"},
                    ),
                    width="100%", height="8px",
                    background="#27272a", border_radius="999px", overflow="hidden",
                ),
                rx.hstack(
                    rx.text("❤️ Happiness", font_size="0.7em", color="#9ca3af"),
                    rx.text(TerramonState.agent_happiness.to_string() + "/100",
                            font_size="0.7em", color="#ef4444", font_weight="bold"),
                    justify="between",
                    width="100%",
                ),
                rx.box(
                    rx.box(
                        style={"width": TerramonState.agent_happiness.to_string() + "%",
                               "height": "100%",
                               "background": "linear-gradient(90deg, #ef4444, #ef4444dd)",
                               "border_radius": "999px",
                               "transition": "width 0.3s ease"},
                    ),
                    width="100%", height="8px",
                    background="#27272a", border_radius="999px", overflow="hidden",
                ),
                # Lesson 06: evolution probability (logistic)
                rx.hstack(
                    rx.text("✦ Evolution", font_size="0.7em", color="#f59e0b"),
                    rx.text(TerramonState.agent_evolution_prob.to_string() + "%",
                            font_size="0.7em", color="#f59e0b", font_weight="bold"),
                    justify="between",
                    width="100%",
                ),
                rx.box(
                    rx.box(
                        style={"width": TerramonState.agent_evolution_prob.to_string() + "%",
                               "height": "100%",
                               "background": "linear-gradient(90deg, #f59e0b, #d97706)",
                               "border_radius": "999px",
                               "transition": "width 0.3s ease"},
                    ),
                    width="100%", height="8px",
                    background="#27272a", border_radius="999px", overflow="hidden",
                ),
                # Phase 2: evolution hint (actionable progress text)
                rx.text(TerramonState.evolution_hint, font_size="0.65em",
                        color="#f59e0b", font_style="italic", text_align="center"),
                # Agent message (speech bubble)
                rx.cond(
                    TerramonState.agent_message != "",
                    rx.box(
                        rx.text(TerramonState.agent_message, font_size="0.8em",
                                color="#d8b4fe", font_style="italic",
                                text_align="center"),
                        padding="0.5em 1em",
                        background="#1e1e2a",
                        border_radius="12px",
                        border="1px solid #27272a",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                # I12 v2: Release receipt — shown right after release
                rx.cond(
                    TerramonState.released_just_now,
                    rx.box(
                        rx.vstack(
                            rx.text("✓ Отпущено: " + TerramonState.released_place,
                                    font_size="0.8em", color="#22c55e",
                                    font_weight="bold", text_align="center"),
                            rx.cond(
                                TerramonState.released_words != "",
                                rx.text('"' + TerramonState.released_words + '"',
                                        font_size="0.75em", color="#d8b4fe",
                                        font_style="italic", text_align="center"),
                                rx.fragment(),
                            ),
                            rx.text("Поделись: я отпустил свою мысль",
                                    font_size="0.65em", color="#6b7280",
                                    font_style="italic", text_align="center"),
                            spacing="1",
                            align="center",
                            width="100%",
                        ),
                        padding="0.6em 0.8em",
                        background="#1a2e1a",
                        border="1px solid #22c55e44",
                        border_radius="10px",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                # «Зажечь свечу» — the emotional monetization ritual.
                # Visible ONLY for a released creature. 500-sat WebLN zap from
                # the player's own wallet (keysend — no invoice node needed).
                # The reward is the creature's NEW WORDS, not cosmetics.
                rx.cond(
                    TerramonState.candle_visible,
                    rx.box(
                        rx.vstack(
                            rx.cond(
                                TerramonState.candle_lit,
                                rx.box(
                                    rx.vstack(
                                        rx.text("🔥", font_size="1.2em"),
                                        rx.text(
                                            TerramonState.candle_lore,
                                            font_size="0.75em",
                                            color="#fbbf24",
                                            font_style="italic",
                                            text_align="center",
                                        ),
                                        rx.text("Свеча горит у места рождения",
                                                font_size="0.6em",
                                                color="#6b7280",
                                                font_style="italic"),
                                        spacing="1",
                                        align="center",
                                        width="100%",
                                    ),
                                    padding="0.6em 0.8em",
                                    background="#1f1a10",
                                    border="1px solid #f59e0b44",
                                    border_radius="10px",
                                    width="100%",
                                ),
                                rx.vstack(
                                    rx.button(
                                        rx.hstack(
                                            rx.text("🕯️", font_size="0.9em"),
                                            rx.text(
                                                "Зажечь свечу · "
                                                + TerramonState.candle_price.to_string()
                                                + " sats",
                                                font_size="0.8em",
                                            ),
                                            spacing="1",
                                        ),
                                        on_click=TerramonState.light_candle,
                                        variant="ghost",
                                        size="2",
                                        color_scheme="amber",
                                        width="100%",
                                        is_disabled=(
                                            TerramonState.candle_state == "paying"
                                        ),
                                        _hover={"transform": "scale(1.02)"},
                                        style={"transition": "all 0.15s ease"},
                                    ),
                                    rx.cond(
                                        TerramonState.candle_state == "paying",
                                        rx.text("Свеча загорается…",
                                                font_size="0.65em",
                                                color="#f59e0b",
                                                font_style="italic"),
                                        rx.cond(
                                            TerramonState.candle_state == "nowebln",
                                            rx.text(
                                                "⚡ Установи Alby-кошелёк, "
                                                "чтобы зажечь свечу",
                                                font_size="0.65em",
                                                color="#9ca3af",
                                                font_style="italic",
                                            ),
                                            rx.cond(
                                                TerramonState.candle_state == "failed",
                                                rx.text(
                                                    "Зажжение не удалось — попробуй ещё раз",
                                                    font_size="0.65em",
                                                    color="#f87171",
                                                    font_style="italic",
                                                ),
                                                rx.text(
                                                    "500 сатоши из твоего кошелька — "
                                                    "и существо скажет новое слово",
                                                    font_size="0.6em",
                                                    color="#6b7280",
                                                    font_style="italic",
                                                ),
                                            ),
                                        ),
                                    ),
                                    spacing="1",
                                    align="center",
                                    width="100%",
                                ),
                            ),
                        ),
                        padding="0.4em 0.2em",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                # I10: Grazed while away notification
                rx.cond(
                    TerramonState.grazed_away_message != "",
                    rx.box(
                        rx.text(TerramonState.grazed_away_message, font_size="0.8em",
                                color="#22c55e", font_style="italic",
                                text_align="center"),
                        padding="0.5em 1em",
                        background="#1a2e1a",
                        border_radius="12px",
                        border="1px solid #22c55e44",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                # Interaction buttons grid (2x2)
                rx.grid(
                    rx.button("🍽️ Feed", on_click=TerramonState.feed_agent,
                              variant="soft", size="2", width="100%",
                              color_scheme="amber"),
                    rx.button("🎮 Play", on_click=TerramonState.play_with_agent,
                              variant="soft", size="2", width="100%",
                              color_scheme="green"),
                    rx.button("💤 Rest", on_click=TerramonState.rest_agent,
                              variant="soft", size="2", width="100%",
                              color_scheme="blue"),
                    rx.button("💬 Talk", on_click=TerramonState.talk_to_agent,
                              variant="soft", size="2", width="100%",
                              color_scheme="purple"),
                    columns="2",
                    spacing="2",
                    width="100%",
                ),
                # Evolve button
                rx.button("✦ EVOLVE", on_click=TerramonState.evolve_agent,
                          variant="outline", size="2", width="100%",
                          color_scheme="amber"),
                # I10: Stasis toggle button
                rx.cond(
                    TerramonState.stasis_active,
                    rx.button("✨ Deactivate Stasis",
                              on_click=TerramonState.deactivate_stasis,
                              variant="outline", size="2", width="100%",
                              color_scheme="blue"),
                    rx.button("💤 Stasis (24h pause)",
                              on_click=TerramonState.activate_stasis,
                              variant="outline", size="2", width="100%",
                              color_scheme="indigo"),
                ),
                # I12 v2: Release button — subtle ghost, visible at stage >= 2
                rx.cond(
                    TerramonState.agent_evolution >= 2,
                    rx.button(
                        "💨 Отпустить",
                        on_click=TerramonState.show_release,
                        variant="ghost", size="2", width="100%",
                        color_scheme="red", font_size="0.8em",
                        _hover={"opacity": "0.8"},
                    ),
                    rx.fragment(),
                ),
                # I08 v2: evolution shimmer auto-clear — gated rx.moment
                # (mirrors the lightning verify poller: cond gate mounts the
                # moment only while the flag is set; the on_change fires once
                # ~1.6s later, clears the flag and the cond unmounts it).
                rx.cond(
                    TerramonState.evolve_animating,
                    rx.moment(
                        interval=1600,
                        on_change=TerramonState.clear_evolution_animation,
                        display="none",
                    ),
                    rx.fragment(),
                ),
                spacing="3",
                align="center",
                width="100%",
            ),
            border="1px solid #27272a",
            border_radius="12px",
            padding="1em",
            background="#141418",
            width="100%",
            max_width="380px",
        ),
        rx.fragment(),
    )


def demo_creature() -> rx.Component:
    """Animated shadow-creature waiting for first input — breathing, floating, pulsing."""
    # CSS keyframes defined as animations via CSS style tag
    _DEMO_ANIM = """
@keyframes demoBreathe {
    0% { transform: scale(1) translateY(0); opacity: 0.55; }
    50% { transform: scale(1.04) translateY(-4px); opacity: 0.75; }
    100% { transform: scale(1) translateY(0); opacity: 0.55; }
}
@keyframes demoPulseGlow {
    0% { box-shadow: 0 0 20px rgba(212, 180, 254, 0.10); }
    50% { box-shadow: 0 0 40px rgba(212, 180, 254, 0.25); }
    100% { box-shadow: 0 0 20px rgba(212, 180, 254, 0.10); }
}
@keyframes demoBlink {
    0%, 45%, 55%, 100% { opacity: 1; }
    50% { opacity: 0.15; }
}
"""
    return rx.vstack(
        # The shadow creature — amorphous blob shape with breathing animation
        rx.box(
            rx.box(
                # Creature body: stacked circles forming an ethereal shadow shape
                rx.vstack(
                    # Glowing eyes
                    rx.hstack(
                        rx.box(
                            width="12px", height="14px",
                            border_radius="50%",
                            background="radial-gradient(circle, #d8b4fe 30%, #a78bfa88)",
                            box_shadow="0 0 12px #a78bfa",
                            style={"animation": "demoBlink 3.5s ease-in-out infinite"},
                        ),
                        rx.box(
                            width="6px", height="6px",
                        ),
                        rx.box(
                            width="12px", height="14px",
                            border_radius="50%",
                            background="radial-gradient(circle, #d8b4fe 30%, #a78bfa88)",
                            box_shadow="0 0 12px #a78bfa",
                            style={"animation": "demoBlink 3.5s ease-in-out infinite",
                                   "animation_delay": "0.15s"},
                        ),
                        spacing="3",
                        align="center",
                        justify="center",
                    ),
                    rx.text(
                        "✦",
                        font_size="1.6em",
                        color="#d8b4fe",
                        letter_spacing="0.3em",
                    ),
                    spacing="3",
                    align="center",
                ),
                # Shadow-body wrapper
                width="120px", height="110px",
                border_radius="50% 50% 45% 45%",
                background="radial-gradient(ellipse at 50% 40%, #2a2a3a 20%, #1a1a28 60%, transparent 80%)",
                style={"animation": "demoBreathe 3s ease-in-out infinite"},
                display="flex",
                align_items="center",
                justify_content="center",
            ),
            # Glow aura around creature
            style={"animation": "demoPulseGlow 3s ease-in-out infinite"},
            display="flex",
            align_items="center",
            justify_content="center",
            padding="0.5em",
        ),
        # Title
        rx.text(
            "Something stirs in the void...",
            color="#d8b4fe",
            font_size="0.95em",
            font_weight="bold",
            text_align="center",
            font_style="italic",
            max_width="320px",
        ),
        # Subtitle
        rx.text(
            "Type a thought. Meet what emerges.",
            color="#9ca3af",
            font_size="0.8em",
            text_align="center",
            max_width="320px",
        ),
        # Gentle tip
        rx.text(
            "Every thought becomes a creature. "
            "What's on your mind right now?",
            color="#6b7280",
            font_size="0.7em",
            text_align="center",
            font_style="italic",
            max_width="280px",
        ),
        spacing="2",
        align="center",
        padding="1.5em 0",
    )


def tutorial_overlay() -> rx.Component:
    """First-time onboarding overlay — explains how to play."""
    return rx.cond(
        TerramonState.show_tutorial,
        rx.box(
            rx.vstack(
                rx.text("🌍 Welcome to Terramon", font_size="1.2em",
                        color="#f5f5f5", font_weight="bold"),
                rx.text("Your thoughts become creatures on real planet Earth.",
                        font_size="0.8em", color="#9ca3af", text_align="center"),
                rx.hstack(
                    rx.box(rx.text("✍️", font_size="1.5em"), width="2em"),
                    rx.vstack(
                        rx.text("1. Type a thought", font_weight="bold",
                                font_size="0.8em", color="#e5e7eb"),
                        rx.text("Anything on your mind becomes a creature.",
                                font_size="0.7em", color="#6b7280"),
                        spacing="1",
                    ),
                    spacing="2",
                    width="100%",
                ),
                rx.hstack(
                    rx.box(rx.text("🃏", font_size="1.5em"), width="2em"),
                    rx.vstack(
                        rx.text("2. SUMMON it", font_weight="bold",
                                font_size="0.8em", color="#e5e7eb"),
                        rx.text("Your creature appears with personality + stats.",
                                font_size="0.7em", color="#6b7280"),
                        spacing="1",
                    ),
                    spacing="2",
                    width="100%",
                ),
                rx.hstack(
                    rx.box(rx.text("🍽️", font_size="1.5em"), width="2em"),
                    rx.vstack(
                        rx.text("3. Feed, Play, Talk, Rest", font_weight="bold",
                                font_size="0.8em", color="#e5e7eb"),
                        rx.text("Keep it alive. It remembers you.",
                                font_size="0.7em", color="#6b7280"),
                        spacing="1",
                    ),
                    spacing="2",
                    width="100%",
                ),
                rx.hstack(
                    rx.box(rx.text("✦", font_size="1.5em"), width="2em"),
                    rx.vstack(
                        rx.text("4. Evolve", font_weight="bold",
                                font_size="0.8em", color="#f59e0b"),
                        rx.text("Level up. Transform. Grow together.",
                                font_size="0.7em", color="#6b7280"),
                        spacing="1",
                    ),
                    spacing="2",
                    width="100%",
                ),
                rx.button("Got it!", on_click=TerramonState.dismiss_tutorial,
                          color_scheme="amber", variant="soft", size="2",
                          width="100%", margin_top="0.5em"),
                spacing="3",
                padding="2em",
                background="linear-gradient(145deg, #1a1a2e 0%, #141418 100%)",
                border="1px solid #27272a",
                border_radius="20px",
                max_width="340px",
                width="100%",
            ),
            position="fixed",
            top="0", left="0", right="0", bottom="0",
            background="rgba(0,0,0,0.75)",
            display="flex",
            align_items="center",
            justify_content="center",
            z_index="1000",
            padding="1em",
        ),
        rx.fragment(),
    )


def earth_map() -> rx.Component:
    """Global creature map with Leaflet heatmap overlay (I11).

    Shows creature density as a heatmap layer over a real-world map.
    Clicking a region loads recent creatures in that area.
    Falls back gracefully when no global data is available.
    """
    return rx.vstack(
        rx.hstack(
            rx.text("🗺️ Global Creature Map", font_size="0.85em",
                    color="#e5e7eb", font_weight="bold"),
            rx.cond(
                TerramonState.map_loading,
                rx.text("⟳ loading...", font_size="0.65em", color="#f59e0b"),
                rx.button("↻ refresh", on_click=TerramonState.load_global_map,
                          size="1", variant="ghost", color_scheme="gray",
                          font_size="0.65em"),
            ),
            justify="between",
            width="100%",
        ),
        # Leaflet map with heatmap + markers
        rx.html(
            f"""<div id="terramon-global-map" style="width:100%;height:320px;border-radius:12px;border:1px solid #27272a;background:#141418;"></div>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
<script>
(function() {{
    var container = document.getElementById('terramon-global-map');
    if (!container || container._terramonInitialized) return;
    container._terramonInitialized = true;

    var map = L.map(container, {{
        center: [20, 0],
        zoom: 2,
        zoomControl: true,
        attributionControl: false,
    }});

    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        maxZoom: 18,
    }}).addTo(map);

    // Heatmap data from state
    var heatData = {TerramonState.map_heatmap_data};
    if (heatData.length > 0) {{
        L.heatLayer(heatData, {{
            radius: 25,
            blur: 15,
            maxZoom: 10,
            max: 1.0,
            gradient: {{0.0: '#9ca3af', 0.3: '#22c55e', 0.6: '#f59e0b', 0.8: '#ef4444'}},
        }}).addTo(map);
    }}

    // Creature markers
    var markers = {TerramonState.map_marker_json};
    markers.forEach(function(m) {{
        var lat = m[0], lon = m[1], agent = m[2] || 'unknown', thought = m[3] || '';
        L.circleMarker([lat, lon], {{
            radius: 4,
            fillColor: '#f59e0b',
            color: '#f59e0b',
            weight: 1,
            opacity: 0.7,
            fillOpacity: 0.6,
        }}).addTo(map)
          .bindPopup('<b>' + agent + '</b><br><i>' + thought.substring(0, 40) + '</i>');
    }});

    // Tap region -> show creatures in 5-degree grid cell
    map.on('click', function(e) {{
        var gridLat = Math.floor(e.latlng.lat / 5) * 5;
        var gridLon = Math.floor(e.latlng.lng / 5) * 5;
        var regionKey = gridLat + '_' + gridLon;
        // Call back to Reflex state
        try {{
            reflex.sendEvent('select_region', {{region_key: regionKey}});
        }} catch(ex) {{
            console.warn('select_region failed', ex);
        }}
    }});

    // Fix size after mount
    setTimeout(function() {{ map.invalidateSize(); }}, 200);
}})();
</script>"""
        ),
        # Region creatures panel
        rx.cond(
            TerramonState.selected_region != "",
            rx.box(
                rx.vstack(
                    rx.hstack(
                        rx.text("📍 Region " + TerramonState.selected_region,
                                font_size="0.75em", color="#f59e0b", font_weight="bold"),
                        rx.button("✕", on_click=TerramonState.select_region(""),
                                  size="1", variant="ghost", color_scheme="gray"),
                        justify="between",
                        width="100%",
                    ),
                    rx.cond(
                        TerramonState.region_creatures.length() > 0,
                        rx.foreach(
                            TerramonState.region_creatures,
                            lambda c: rx.hstack(
                                rx.text("🃏", font_size="0.8em"),
                                rx.vstack(
                                    rx.text(c["agent"],
                                            font_size="0.7em", color="#e5e7eb",
                                            font_weight="bold"),
                                    rx.text(c["thought"],
                                            font_size="0.6em", color="#9ca3af",
                                            max_width="200px"),
                                    spacing="0",
                                ),
                                spacing="2",
                                align="center",
                                width="100%",
                                border_bottom="1px solid #27272a",
                                padding="0.3em 0",
                            ),
                        ),
                        rx.text("No creatures in this region yet.",
                                font_size="0.65em", color="#6b7280",
                                font_style="italic"),
                    ),
                    spacing="2",
                    width="100%",
                ),
                padding="0.5em",
                background="#141418",
                border="1px solid #27272a",
                border_radius="12px",
                width="100%",
                max_height="200px",
                style={"overflow_y": "auto"},
            ),
            rx.fragment(),
        ),
        # Local creatures count
        rx.hstack(
            rx.text("🌍 " + TerramonState.global_creatures.length().to_string()
                    + " creatures worldwide",
                    font_size="0.65em", color="#9ca3af"),
            rx.text("· tap map to see region",
                    font_size="0.6em", color="#6b7280", font_style="italic"),
            spacing="1",
            width="100%",
            justify="center",
        ),
        spacing="2",
        align="center",
        width="100%",
        padding="0.5em",
    )


def _qr_data_uri(invoice: str) -> str:
    """BOLT11 QR as a local data URI (lightning: URI scheme). No third-party QR API."""
    return segno.make_qr("lightning:" + invoice).png_data_uri(scale=4)


def _lightning_invoice_panel() -> rx.Component:
    """F3/M7 — shared Lightning invoice flow panel (BOLT11 QR + verify).

    Used by payment_gate() (summon gate) and creature_care_panel()'s
    Lightning mint path (mint_lightning). Self-gates on
    TerramonState.lightning_invoice != '' so it renders nothing until an
    invoice exists. The gate's no-invoice fallback button stays inline in
    payment_gate() (gate-specific fixed GATE_SUMMON_PRICE_SATS).
    """
    return rx.cond(
        TerramonState.lightning_invoice != "",
        rx.vstack(
            rx.cond(
                TerramonState.lightning_qr != "",
                rx.image(
                    src=TerramonState.lightning_qr,
                    width="180px", height="180px",
                    border_radius="8px", background="#fff", padding="4px",
                ),
                rx.text(
                    "QR unavailable — pay via BOLT11 below",
                    font_size="0.6em", color="#6b7280",
                ),
            ),
            rx.text(
                "Pay ⚡ " + TerramonState.lightning_price.to_string() + " sats with any Lightning wallet",
                font_size="0.75em", color="#fbbf24", text_align="center",
            ),
            rx.text(
                TerramonState.lightning_invoice,
                font_size="0.55em", color="#6b7280", text_align="center",
                max_width="280px", word_break="break-all",
            ),
            # BOLT11 copy affordance — same rx.set_clipboard pattern as
            # share_creature; mark_invoice_copied only flips the feedback
            # flag (never touches agent_message — KPI parses it).
            rx.button(
                "📋 Copy BOLT11",
                on_click=[rx.set_clipboard(TerramonState.lightning_invoice), TerramonState.mark_invoice_copied],
                variant="surface", size="1", color_scheme="gray",
                width="100%",
            ),
            rx.cond(
                TerramonState.invoice_copied,
                rx.text("✓ Инвойс скопирован", font_size="0.6em", color="#4ade80"),
                rx.fragment(),
            ),
            rx.cond(
                TerramonState.lightning_auto_verify,
                rx.text("⏳ Auto-checking payment… " + TerramonState.lightning_verify_attempts.to_string() + "/30", font_size="0.7em", color="#9ca3af"),
                rx.cond(
                    TerramonState.lightning_checking,
                    rx.text("⏳ Checking payment…", font_size="0.7em", color="#9ca3af"),
                    rx.button(
                        "✅ I've paid — verify",
                        on_click=TerramonState.verify_lightning,
                        variant="solid", size="2", color_scheme="yellow",
                        width="100%", _hover={"transform": "scale(1.02)"},
                    ),
                ),
            ),
            # Hidden periodic poller: while auto-verify is armed, rx.moment
            # re-renders every 6s and fires verify_lightning(datetime) —
            # the only sane periodic callback pattern in Reflex 0.9.x.
            # The cond gate unmounts it the moment auto-verify stops
            # (settled or gave up), so no stray timers keep firing.
            rx.cond(
                TerramonState.lightning_auto_verify,
                rx.moment(interval=6000, on_change=TerramonState.verify_lightning, display="none"),
                rx.fragment(),
            ),
            # Lesson 13: portrait poller — always mounted, cheap no-op when
            # portrait_pending is False (sigil → art swap appears in-session).
            rx.moment(interval=4000, on_change=TerramonState.poll_portrait, display="none"),
            rx.button(
                "🔄 New invoice",
                on_click=TerramonState.pay_lightning,
                variant="surface", size="1", color_scheme="gray",
                width="100%",
            ),
            spacing="2",
            align="center",
            width="100%",
        ),
        rx.fragment(),
    )


def payment_gate() -> rx.Component:
    """F3 — Monetization Gate: first summon free, then payment required.
    BTC-first: Lightning (BOLT11 on self-custodial Alby Hub) is primary;
    Telegram Stars is the fallback. In-flight disable via lightning_checking."""
    return rx.vstack(
        rx.box(
            rx.vstack(
                rx.text("⚡", font_size="1.5em"),
                rx.text("Free summon used!",
                        font_weight="bold", font_size="0.9em", color="#e5e7eb"),
                rx.text("Pay in bitcoin (Lightning) to summon again.",
                        font_size="0.75em", color="#9ca3af", text_align="center"),
                spacing="1",
                align="center",
            ),
            padding="1em",
            background="#141418",
            border="1px solid #27272a",
            border_radius="12px",
            width="100%",
        ),
        # BTC-first: Lightning invoice flow — the shared panel renders the
        # BOLT11 QR + verify flow (on_click=TerramonState.verify_lightning,
        # "🔄 New invoice" via on_click=TerramonState.pay_lightning) whenever
        # an invoice exists; the fallback below is the gate's no-invoice
        # state (fixed GATE_SUMMON_PRICE_SATS — the gate price is NOT the
        # last creature's tier, which is 0 for free tiers).
        _lightning_invoice_panel(),
        rx.cond(
            TerramonState.lightning_invoice == "",
            rx.button(
                rx.hstack(
                    rx.text("⚡", font_size="1em"),
                    rx.text("Pay with Lightning · " + str(GATE_SUMMON_PRICE_SATS) + " sats",
                            font_size="0.8em"),
                    spacing="1",
                ),
                on_click=TerramonState.pay_lightning,
                variant="solid",
                size="2",
                color_scheme="yellow",
                width="100%",
                _hover={"transform": "scale(1.02)"},
                style={"transition": "all 0.15s ease"},
            ),
            rx.fragment(),
        ),
        rx.text("— or —", font_size="0.65em", color="#52525b"),
        rx.button(
            rx.hstack(
                rx.text("⭐", font_size="1em"),
                rx.text("Mint (1 Star)", font_size="0.8em"),
                spacing="1",
            ),
            on_click=TerramonState.buy_stars,
            variant="solid",
            size="2",
            color_scheme="amber",
            width="100%",
            _hover={"transform": "scale(1.02)"},
            style={"transition": "all 0.15s ease"},
        ),
        rx.text(
            "⚡ Bitcoin-first · sats go straight to the Terramon node. "
            "Stars via @BotFather as fallback.",
            font_size="0.6em",
            color="#6b7280",
            text_align="center",
            font_style="italic",
        ),
        spacing="2",
        align="center",
        width="100%",
        max_width="360px",
    )


# ── F2: Tamer Unlock celebration (5/5 distinct → "Terra Awakened") ──
# CSS keyframes defined as a style string (Reflex 0.9.x compat)
_CELEBRATION_STYLE = """
@keyframes celebrationSparkle {
    0% { opacity: 0.3; transform: scale(1); }
    50% { opacity: 1; transform: scale(1.05); }
    100% { opacity: 0.3; transform: scale(1); }
}
"""

# ── Evolution animation keyframes (used by evolve_agent / evolve_animating) ──
# Shimmer sweep, burst stars, card scale + tutorial fade. All four were
# referenced in UI but the constant was lost — restoring here.
_EVOLVE_STYLE = """
@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}
@keyframes evolutionShimmer {
    0% { background-position: 0% 0; }
    100% { background-position: 100% 0; }
}
@keyframes evolutionBurst {
    0% { transform: scale(0) rotate(-45deg); opacity: 0; }
    60% { transform: scale(1.5) rotate(10deg); opacity: 1; }
    100% { transform: scale(1) rotate(0deg); opacity: 0.9; }
}
@keyframes evolutionScale {
    0% { transform: scale(0.85); filter: brightness(1.6); }
    60% { transform: scale(1.06); }
    100% { transform: scale(1); filter: brightness(1); }
}
"""


def celebration_component() -> rx.Component:
    """Full-screen celebration overlay when player reaches 5/5 distinct creatures.
    Shows 'TERRA AWAKENED' with golden border + sparkle animation.
    Dismissable — after dismiss, permanent visual upgrades appear (F2)."""
    return rx.box(
        rx.vstack(
            rx.box(height="12vh"),
            rx.text("✦", color="#f59e0b", font_size="4em",
                    style={"animation": "celebrationSparkle 1.5s ease-in-out infinite"}),
            rx.heading("TERRA AWAKENED", size="7", color="#f59e0b",
                       font_weight="bold", letter_spacing="0.08em",
                       text_shadow="0 0 30px rgba(245,158,11,0.6)"),
            rx.text("You have collected 5 distinct creatures.",
                    color="#d8b4fe", font_size="0.85em", text_align="center"),
            rx.text("Your terra is awake. All creatures now bear",
                    color="#d8b4fe", font_size="0.85em", text_align="center"),
            rx.text("the legendary ★ mark.",
                    color="#d8b4fe", font_size="0.85em", text_align="center"),
            rx.spacer(),
            rx.button(
                "✦ Continue",
                on_click=TerramonState.dismiss_celebration,
                color_scheme="amber", variant="solid", size="3",
                width="200px",
                _hover={"transform": "scale(1.05)"},
                style={"transition": "all 0.2s ease"},
            ),
            spacing="4",
            align="center",
            padding="2em",
            width="100%",
            max_width="360px",
        ),
        position="fixed",
        top="0", left="0", right="0", bottom="0",
        background="rgba(11,11,15,0.92)",
        display="flex",
        align_items="center",
        justify_content="center",
        z_index="900",
        border="2px solid #f59e0b66",
        style={"animation": "fadeIn 0.5s ease"},
    )


def release_dialog() -> rx.Component:
    """I12 v2: Release confirmation dialog — '💨 Отпустить' + final words.

    Confirms the release action before the creature goes into the wild.
    The creature is removed from active care but stays in terra as a memorial.
    """
    return rx.cond(
        TerramonState.show_release_dialog,
        rx.box(
            rx.vstack(
                rx.text("💨", font_size="2.5em"),
                rx.heading("Отпустить?", size="5", color="#e5e7eb",
                           font_weight="bold"),
                rx.text(
                    "Существо останется жить на месте рождения. Это нельзя отменить.",
                    font_size="0.75em", color="#9ca3af",
                    text_align="center", max_width="300px",
                ),
                rx.text_area(
                    placeholder="Последние слова (необязательно)...",
                    value=TerramonState.final_words,
                    on_change=TerramonState.set_final_words,
                    size="1",
                    variant="soft",
                    color_scheme="gray",
                    width="100%",
                    min_height="3em",
                ),
                rx.text(
                    "Оно уйдёт в дикий мир, но останется в терре как память.",
                    font_size="0.7em", color="#6b7280",
                    text_align="center", max_width="300px",
                    font_style="italic",
                ),
                rx.cond(
                    (TerramonState.agent_lat == 0.0) | (TerramonState.agent_lon == 0.0),
                    rx.hstack(
                        rx.text("📍 Нужна геолокация для ритуала",
                                font_size="0.7em", color="#fbbf24"),
                        rx.button("⟳", on_click=TerramonState.capture_location,
                                  size="1", variant="ghost", color_scheme="amber",
                                  font_size="0.9em"),
                        spacing="2", align="center", width="100%",
                        justify="center",
                    ),
                    rx.fragment(),
                ),
                rx.hstack(
                    rx.button(
                        "Отмена",
                        on_click=TerramonState.hide_release,
                        variant="soft", size="2",
                        color_scheme="gray", width="50%",
                    ),
                    rx.button(
                        "💨 Отпустить",
                        on_click=TerramonState.release_creature,
                        variant="solid", size="2",
                        color_scheme="red", width="50%",
                    ),
                    spacing="2",
                    width="100%",
                ),
                spacing="3",
                align="center",
                padding="2em",
                background="linear-gradient(145deg, #1a1a2e 0%, #141418 100%)",
                border="1px solid #ef444444",
                border_radius="20px",
                max_width="340px",
                width="100%",
            ),
            position="fixed",
            top="0", left="0", right="0", bottom="0",
            background="rgba(0,0,0,0.75)",
            display="flex",
            align_items="center",
            justify_content="center",
            z_index="950",
            padding="1em",
        ),
        rx.fragment(),
    )


def ritual_payment_panel() -> rx.Component:
    """🪙 Ритуал Отпускания — the ACTUAL WIN is the paid sacred moment.

    Shown when a release carries final words + a real geo anchor: the
    words reach the world only when the coin falls in the fountain.
    Lightning is the sacred rail (BOLT11 via Alby, RITUAL_RELEASE_SATS);
    Stars is the fallback rail. «Отпустить без ритуала» frees the
    creature as a legacy release that never counts toward the depth win.
    """
    return rx.cond(
        TerramonState.show_ritual_payment,
        rx.box(
            rx.vstack(
                rx.text("🪙", font_size="2.5em"),
                rx.heading("Ритуал Отпускания", size="5", color="#e5e7eb",
                           font_weight="bold"),
                rx.text(
                    "Твои слова дойдут до мира, когда монета упадёт в фонтан.",
                    font_size="0.75em", color="#9ca3af",
                    text_align="center", max_width="300px",
                ),
                rx.cond(
                    TerramonState.release_ritual_invoice != "",
                    rx.vstack(
                        rx.cond(
                            TerramonState.release_ritual_qr != "",
                            rx.image(
                                src=TerramonState.release_ritual_qr,
                                width="160px", height="160px",
                                border_radius="8px", background="#fff",
                                padding="4px",
                            ),
                            rx.fragment(),
                        ),
                        rx.text(
                            "Pay ⚡ " + str(RITUAL_RELEASE_SATS) + " sats with any Lightning wallet",
                            font_size="0.75em", color="#fbbf24", text_align="center",
                        ),
                        rx.text(
                            TerramonState.release_ritual_invoice,
                            font_size="0.55em", color="#6b7280", text_align="center",
                            max_width="280px", word_break="break-all",
                        ),
                        rx.button(
                            "📋 Copy BOLT11",
                            on_click=rx.set_clipboard(TerramonState.release_ritual_invoice),
                            variant="surface", size="1", color_scheme="gray",
                            width="100%",
                        ),
                        rx.link(
                            "⚡ Открыть кошелёк",
                            href=TerramonState.release_ritual_lightning_uri,
                            display="block",
                            text_align="center",
                            width="100%",
                            padding="0.5rem 1rem",
                            border_radius="8px",
                            background="#fbbf24",
                            color="#1c1917",
                            font_size="0.8em",
                            font_weight="bold",
                            text_decoration="none",
                            _hover={"background": "#fcd34d"},
                        ),
                        rx.cond(
                            TerramonState.release_ritual_auto_verify,
                            rx.text(
                                "⏳ Auto-checking payment… "
                                + TerramonState.release_ritual_verify_attempts.to_string()
                                + "/" + str(RITUAL_RELEASE_VERIFY_MAX_ATTEMPTS),
                                font_size="0.7em", color="#9ca3af",
                            ),
                            rx.vstack(
                                rx.button(
                                    "✅ I've paid — verify",
                                    on_click=TerramonState.verify_release_ritual,
                                    variant="solid", size="2", color_scheme="yellow",
                                    width="100%", _hover={"transform": "scale(1.02)"},
                                ),
                                rx.button(
                                    "🔄 Новый инвойс",
                                    on_click=TerramonState.refresh_ritual_invoice,
                                    variant="soft", size="1", color_scheme="gray",
                                    width="100%",
                                ),
                                rx.text(
                                    "Инвойс жив ~1 час — если оплата не прошла, создай новый.",
                                    font_size="0.65em", color="#6b7280", text_align="center",
                                ),
                                spacing="2",
                                align="center",
                                width="100%",
                            ),
                        ),
                        # Hidden periodic poller — mirrors the lightning gate:
                        # the cond gate unmounts it the moment auto-verify stops.
                        rx.cond(
                            TerramonState.release_ritual_auto_verify,
                            rx.moment(
                                interval=6000,
                                on_change=TerramonState.verify_release_ritual,
                                display="none",
                            ),
                            rx.fragment(),
                        ),
                        spacing="2",
                        align="center",
                        width="100%",
                    ),
                    rx.text(
                        "⚡ Lightning не настроен — используй Stars ниже.",
                        font_size="0.7em", color="#9ca3af", text_align="center",
                    ),
                ),
                rx.text("— or —", font_size="0.65em", color="#52525b"),
                rx.cond(
                    TerramonState.ritual_stars_pending,
                    rx.text(
                        "⏳ Ожидание оплаты Stars…",
                        font_size="0.75em", color="#9ca3af", text_align="center",
                    ),
                    rx.button(
                        rx.hstack(
                            rx.text("⭐", font_size="1em"),
                            rx.text(
                                "Оплатить ритуал · " + str(RITUAL_RELEASE_STARS) + " Stars",
                                font_size="0.8em",
                            ),
                            spacing="1",
                        ),
                        on_click=TerramonState.pay_ritual_stars,
                        variant="solid", size="2", color_scheme="amber",
                        width="100%", _hover={"transform": "scale(1.02)"},
                    ),
                ),
                rx.button(
                    "💨 Отпустить без ритуала (слова останутся с тобой)",
                    on_click=TerramonState.release_without_ritual,
                    variant="soft", size="2", color_scheme="gray",
                    width="100%",
                ),
                spacing="3",
                align="center",
                padding="2em",
                background="linear-gradient(145deg, #1a1a2e 0%, #141418 100%)",
                border="1px solid #fbbf2466",
                border_radius="20px",
                max_width="340px",
                width="100%",
            ),
            position="fixed",
            top="0", left="0", right="0", bottom="0",
            background="rgba(0,0,0,0.8)",
            display="flex",
            align_items="center",
            justify_content="center",
            z_index="960",
            padding="1em",
        ),
        rx.fragment(),
    )


def index() -> rx.Component:
    """GameBoy-style single-screen TMA. Everything visible at once, no scrolling.
    Three zones: TOP (creature), MIDDLE (stats+input), BOTTOM (nav).
    Like Pokémon Gold — all on one iPhone screen."""
    return rx.center(
        # CSS animations injected via html style tag
        rx.html(f"<style>{_CELEBRATION_STYLE}{_EVOLVE_STYLE}</style>"),
        # Tutorial overlay (first visit only, on top of everything)
        tutorial_overlay(),
        # I12: Release confirmation dialog
        release_dialog(),
        # 🪙 Ritual monetisation: the ACTUAL WIN's payment panel
        ritual_payment_panel(),
        # Outer container: fixed height = 100vh, no overflow
        rx.box(
            rx.vstack(
                # ── ZONE 0: Mini header bar ──
                rx.hstack(
                    rx.hstack(
                        rx.heading("🌍 TERRAMON", size="5", color="#f5f5f5"),
                        rx.cond(
                            TerramonState.goal_reached,
                            rx.text("★", color="#f59e0b", font_size="1.2em",
                                    text_shadow="0 0 12px rgba(245,158,11,0.6)"),
                            rx.fragment(),
                        ),
                        spacing="1",
                        align="center",
                    ),
                    rx.spacer(),
                    rx.hstack(
                        rx.text("Lv.", color="#9ca3af", font_size="0.7em"),
                        rx.text(TerramonState.level.to_string(), color="#f59e0b",
                                font_weight="bold", font_size="0.85em"),
                        # I09: Streak flame
                        rx.cond(
                            TerramonState.summon_streak >= 7,
                            rx.text("🔥🔥", font_size="0.8em",
                                    text_shadow="0 0 8px rgba(239,68,68,0.6)"),
                            rx.cond(
                                TerramonState.summon_streak >= 3,
                                rx.text("🔥", font_size="0.8em",
                                        text_shadow="0 0 6px rgba(239,68,68,0.4)"),
                                rx.cond(
                                    TerramonState.summon_streak > 0,
                                    rx.text("🔥", font_size="0.7em",
                                            color="#9ca3af"),
                                    rx.fragment(),
                                ),
                            ),
                        ),
                        # I12: ★ Wild Tamer badge
                        rx.cond(
                            TerramonState.wild_tamer_badge,
                            rx.hstack(
                                rx.text("★", color="#22c55e", font_size="0.8em",
                                        text_shadow="0 0 8px rgba(34,197,94,0.5)"),
                                rx.text("Wild Tamer", color="#22c55e",
                                        font_weight="bold", font_size="0.55em"),
                                spacing="1",
                                align="center",
                                border="1px solid #22c55e44",
                                border_radius="999px",
                                padding="0.1em 0.4em",
                                background="rgba(34,197,94,0.08)",
                            ),
                            rx.fragment(),
                        ),
                        # I05: progression tier badge + name
                        rx.cond(
                            TerramonState.distinct > 0,
                            rx.hstack(
                                rx.text(TerramonState.tier_badge.to_string(),
                                        color="#f59e0b", font_size="0.8em"),
                                rx.text(TerramonState.tier_name.to_string(),
                                        color="#f59e0b", font_weight="bold",
                                        font_size="0.7em"),
                                rx.cond(
                                    TerramonState.complete_releases >= 1,
                                    rx.text("★ Встретивший", color="#22c55e",
                                            font_weight="bold", font_size="0.65em"),
                                    rx.text(
                                        "Отпущено в мир: "
                                        + TerramonState.complete_releases.to_string(),
                                        color="#a78bfa", font_size="0.65em",
                                    ),
                                ),
                                spacing="1",
                                align="center",
                                border="1px solid #f59e0b44",
                                border_radius="999px",
                                padding="0.1em 0.4em",
                                background="rgba(245,158,11,0.08)",
                            ),
                            rx.fragment(),
                        ),
                        spacing="1",
                    ),
                    width="100%",
                    padding="0.4em 0.2em",
                ),

                # ── ZONE 1: Creature display (~35% viewport) ──
                rx.box(
                    rx.cond(
                        TerramonState.has_summoned,
                        # Compact creature card
                        rx.box(
                            rx.cond(
                                TerramonState.evolve_animating,
                                rx.box(
                                    # Shimmer sweep overlay
                                    rx.box(
                                        style={
                                            "position": "absolute",
                                            "inset": "0",
                                            "background": "linear-gradient(90deg, transparent 0%, rgba(245,158,11,0.15) 25%, rgba(255,255,200,0.25) 50%, rgba(245,158,11,0.15) 75%, transparent 100%)",
                                            "background_size": "300% 100%",
                                            "border_radius": "16px",
                                            "pointer_events": "none",
                                            "z_index": "5",
                                            "animation": "evolutionShimmer 1s ease-in-out 1",
                                        },
                                    ),
                                    # Emoji burst: ★★★★
                                    rx.text(
                                        "★★★★",
                                        position="absolute",
                                        top="-10px",
                                        right="-10px",
                                        font_size="1.4em",
                                        color="#f59e0b",
                                        text_shadow="0 0 20px rgba(245,158,11,0.8)",
                                        z_index="10",
                                        pointer_events="none",
                                        style={"animation": "evolutionBurst 1.2s ease-out 1"},
                                    ),
                                    position="relative",
                                ),
                                rx.fragment(),
                            ),
                            rx.vstack(
                                rx.cond(
                                    TerramonState.agent_portrait != "",
                                    rx.image(
                                        src=TerramonState.agent_portrait,
                                        width="170px",
                                        height="170px",
                                        object_fit="cover",
                                        border_radius="14px",
                                        border="1px solid #27272a",
                                        box_shadow="0 0 24px rgba(255,215,0,0.15)",
                                    ),
                                    rx.text(
                                        TerramonState.sigil,
                                        font_size="2.8em",
                                        color=rx.cond(TerramonState.goal_reached, "#f59e0b", TerramonState.color),
                                        text_shadow=rx.cond(
                                            TerramonState.goal_reached,
                                            "0 0 40px rgba(245,158,11,0.6)",
                                            TerramonState.rarity_glow_style,
                                        ),
                                    ),
                                ),
                                rx.text(TerramonState.agent, color=rx.cond(TerramonState.goal_reached, "#f59e0b", TerramonState.color),
                                        font_weight="bold", font_size="1em"),
                                rx.text('"' + TerramonState.thought[:40] + '"',
                                        font_size="0.7em", text_align="center",
                                        max_width="260px"),
                                # Phase 2: archetype lore on compact card
                                rx.text(TerramonState.lore, font_size="0.65em",
                                        color="#9ca3af", text_align="center",
                                        max_width="260px", font_style="italic",
                                        style={
                                            "display": "-webkit-box",
                                            "-webkit-line-clamp": "2",
                                            "-webkit-box-orient": "vertical",
                                            "overflow": "hidden",
                                        }),
                                # F1.1: Compact speech bubble
                                rx.cond(
                                    TerramonState.creature_greeting != "",
                                    rx.box(
                                        rx.text(TerramonState.creature_greeting,
                                                font_size="0.6em", color="#d8b4fe",
                                                font_style="italic", text_align="center",
                                                style={
                                                    "display": "-webkit-box",
                                                    "-webkit-line-clamp": "2",
                                                    "-webkit-box-orient": "vertical",
                                                    "overflow": "hidden",
                                                }),
                                        padding="0.3em 0.6em",
                                        background="#1e1e2a",
                                        border_radius="8px",
                                        border="1px solid #27272a",
                                        width="100%",
                                        max_width="260px",
                                        position="relative",
                                    ),
                                    rx.fragment(),
                                ),
                                # F1.2: Geo location on compact card
                                rx.cond(
                                    TerramonState.place != "",
                                    rx.hstack(
                                        rx.text("📍", font_size="0.6em"),
                                        rx.text(TerramonState.place, font_size="0.55em",
                                                color="#6b7280", font_style="italic"),
                                        spacing="1",
                                        align="center",
                                    ),
                                    rx.fragment(),
                                ),
                                # F1.3: Memory greeting (compact)
                                rx.cond(
                                    TerramonState.memory_greeting != "",
                                    rx.text(TerramonState.memory_greeting,
                                            font_size="0.55em", color="#a78bfa",
                                            text_align="center", font_style="italic",
                                            max_width="260px",
                                            style={
                                                "display": "-webkit-box",
                                                "-webkit-line-clamp": "1",
                                                "-webkit-box-orient": "vertical",
                                                "overflow": "hidden",
                                            }),
                                    rx.fragment(),
                                ),
                                # ── M7-funnel: home compact card mint area (same gate as Care panel) ──
                                rx.cond(
                                    TerramonState.price_sats > 0,
                                    rx.cond(
                                        TerramonState.can_mint,
                                        rx.vstack(
                                            rx.tooltip(
                                                rx.button(
                                                    "⚡ MINT · " + TerramonState.price_sats.to_string() + " Stars",
                                                    on_click=TerramonState.mint_creature,
                                                    background=TerramonState.color,
                                                    color="#0b0b0f",
                                                    size="1",
                                                    width="100%",
                                                    _hover={"transform": "scale(1.02)", "opacity": "0.9"},
                                                    style={"transition": "all 0.15s ease"},
                                                ),
                                                content="Mint this creature to Telegram Stars — tradable collectible on-chain",
                                            ),
                                            # '⚡ Mint via Lightning' — honest sats price via lightning_button_label
                                            rx.button(
                                                TerramonState.lightning_button_label,
                                                on_click=TerramonState.mint_lightning,
                                                variant="surface",
                                                size="1",
                                                color_scheme="yellow",
                                                width="100%",
                                            ),
                                            spacing="1",
                                            width="100%",
                                        ),
                                        rx.text("locked · train more", color="#6b7280", font_size="0.65em"),
                                    ),
                                    rx.fragment(),
                                ),
                                spacing="1",
                                align="center",
                            ),
                            width="100%",
                            max_height="100%",
                            overflow_y="auto",
                            style=rx.cond(
                                TerramonState.evolve_animating,
                                {"animation": "evolutionScale 1s ease-out 1"},
                                {},
                            ),
                        ),
                        # Empty state: compact shadow creature
                        rx.vstack(
                            rx.box(
                                rx.hstack(
                                    rx.box(width="8px", height="10px",
                                           border_radius="50%",
                                           background="radial-gradient(circle, #d8b4fe 30%, #a78bfa88)",
                                           box_shadow="0 0 8px #a78bfa"),
                                    rx.box(width="4px"),
                                    rx.box(width="8px", height="10px",
                                           border_radius="50%",
                                           background="radial-gradient(circle, #d8b4fe 30%, #a78bfa88)",
                                           box_shadow="0 0 8px #a78bfa"),
                                    spacing="2",
                                    align="center",
                                ),
                                padding="0.3em",
                                display="flex",
                                align_items="center",
                                justify_content="center",
                            ),
                            rx.text("Type a thought. Meet what emerges.",
                                    color="#9ca3af", font_size="0.7em",
                                    font_style="italic"),
                            spacing="1",
                            align="center",
                        ),
                    ),
                    height="35vh",
                    min_height="160px",
                    display="flex",
                    align_items="center",
                    justify_content="center",
                    width="100%",
                ),

                # ── ZONE 2: Compact stats + XP bar ──
                rx.box(
                    rx.hstack(
                        rx.text("XP", color="#6b7280", font_size="0.6em"),
                        rx.box(
                            rx.box(
                                style={"width": TerramonState.xp_into_level.to_string() + "%",
                                      "height": "100%",
                                      "background": "linear-gradient(90deg, #f59e0b, #d97706)",
                                      "border_radius": "999px",
                                      "transition": "width 0.4s ease"},
                            ),
                            width="100%", height="6px",
                            background="#27272a", border_radius="999px",
                            overflow="hidden",
                            flex="1",
                        ),
                        rx.text(TerramonState.xp_into_level.to_string() + "/100",
                                color="#6b7280", font_size="0.6em"),
                        rx.cond(
                            TerramonState.goal_reached,
                            rx.hstack(
                                rx.text("★", color="#f59e0b", font_size="0.8em"),
                                rx.text("Встретивший", color="#f59e0b", font_size="0.6em",
                                        font_weight="bold"),
                                spacing="1",
                                align="center",
                                border="1px solid #f59e0b44",
                                border_radius="999px",
                                padding="0.1em 0.4em",
                                background="rgba(245,158,11,0.08)",
                            ),
                            rx.fragment(),
                        ),
                        spacing="2",
                        align="center",
                        width="100%",
                    ),
                    width="100%",
                    max_width="360px",
                ),

                # ── ZONE 3: Input + Action buttons (or F3 payment gate) ──
                rx.cond(
                    # F3 — show payment gate after free summon used
                    # F3 gate: parentheses REQUIRED — "&" binds tighter than ">" in Python; without them unlocked is dead code.
                    (TerramonState.summon_count > 0) & ~TerramonState.unlocked,
                    payment_gate(),
                    # Normal input + action buttons
                    rx.vstack(
                        rx.input(
                            placeholder=rx.cond(
                                TerramonState.photo_mode,
                                "caption this moment...",
                                "i'm afraid of the interview...",
                            ),
                            value=TerramonState.thought,
                            on_change=TerramonState.set_thought,
                            width="100%",
                            size="2",
                            variant="soft",
                            color_scheme="gray",
                        ),
                        # G05: geo status line + re-anchor (compact, one line)
                        rx.cond(
                            TerramonState.geo_status != "",
                            rx.hstack(
                                rx.cond(
                                    TerramonState.geo_status == "granted",
                                    rx.hstack(
                                        rx.text("📍", font_size="0.6em"),
                                        rx.text(
                                            rx.cond(
                                                TerramonState.place != "",
                                                TerramonState.place,
                                                TerramonState.geo_lat.to_string() + ", "
                                                + TerramonState.geo_lon.to_string(),
                                            ),
                                            font_size="0.55em", color="#6b7280",
                                        ),
                                        rx.button("⟳",
                                                  on_click=TerramonState.capture_location,
                                                  size="1", variant="ghost",
                                                  color_scheme="gray",
                                                  padding="0 0.3em",
                                                  font_size="0.6em"),
                                        spacing="1",
                                        align="center",
                                    ),
                                    rx.text("📍 место не определено — существо родится "
                                            "«в неизвестном месте»",
                                            font_size="0.55em", color="#6b7280",
                                            font_style="italic"),
                                ),
                                width="100%",
                                justify="center",
                                padding="0.1em 0",
                            ),
                            rx.cond(
                                TerramonState.summon_count == 0,
                                rx.text("📍 первый призыв закрепит мысль на планете",
                                        font_size="0.55em", color="#6b7280",
                                        font_style="italic",
                                        padding="0.1em 0"),
                                rx.fragment(),
                            ),
                        ),
                        rx.hstack(
                            rx.button("📷", on_click=TerramonState.capture,
                                      size="2", variant="surface", width="20%",
                                      color_scheme="gray"),
                            rx.button(
                                rx.cond(TerramonState.summoning, "🔮", "✨ SUMMON"),
                                on_click=TerramonState.summon,
                                size="2", width="48%",
                                variant="solid", color_scheme="amber",
                                _hover={"transform": "scale(1.02)"},
                            ),
                            rx.button(
                                rx.cond(TerramonState.scout_running, "⏳", "🔍 Scout"),
                                on_click=TerramonState.run_scout,
                                size="2", width="30%",
                                variant="surface",
                                color_scheme="blue",
                                _hover={"transform": "scale(1.02)"},
                            ),
                            spacing="2",
                            width="100%",
                        ),
                        # Phase 19: Scout result display
                        rx.cond(
                            TerramonState.scout_result != "",
                            rx.box(
                                rx.text(TerramonState.scout_result,
                                        font_size="0.65em", color="#a78bfa",
                                        text_align="left",
                                        max_width="360px",
                                        white_space="pre-wrap",
                                ),
                                padding="0.4em 0.6em",
                                background="#1a1a2e",
                                border="1px solid #27272a",
                                border_radius="8px",
                                width="100%",
                                max_width="360px",
                            ),
                            rx.fragment(),
                        ),
                        spacing="2",
                        width="100%",
                        max_width="360px",
                    ),
                ),

                # ── ZONE 4: GameBoy-style bottom navigation ──
                rx.hstack(
                    rx.button(
                        rx.hstack(rx.text("🜨", font_size="1em"),
                                  rx.text("Terra", font_size="0.7em"),
                                  spacing="1"),
                        variant="soft", size="2", width="30%",
                        color_scheme=rx.cond(
                            TerramonState.active_tab == "terra", "amber", "gray",
                        ),
                        on_click=TerramonState.set_tab("terra"),
                    ),
                    rx.button(
                        rx.hstack(rx.text("🎮", font_size="1em"),
                                  rx.text("Care", font_size="0.7em"),
                                  spacing="1"),
                        variant="soft", size="2", width="30%",
                        color_scheme=rx.cond(
                            TerramonState.active_tab == "care", "amber", "gray",
                        ),
                        on_click=TerramonState.set_tab("care"),
                    ),
                    rx.button(
                        rx.hstack(rx.text("🗺️", font_size="1em"),
                                  rx.text("Map", font_size="0.7em"),
                                  spacing="1"),
                        variant="soft", size="2", width="30%",
                        color_scheme=rx.cond(
                            TerramonState.active_tab == "map", "amber", "gray",
                        ),
                        on_click=TerramonState.set_tab("map"),
                    ),
                    spacing="3",
                    width="100%",
                    max_width="360px",
                    padding="0.4em 0",
                ),

                # ── F2: Tamer Unlock celebration overlay ──
                rx.cond(
                    TerramonState.celebration_pending,
                    rx.cond(
                        TerramonState.celebration_dismissed,
                        rx.fragment(),
                        celebration_component(),
                    ),
                    rx.fragment(),
                ),

                # ── ZONE 5: Tab content (scrollable, GameBoy single-screen) ──
                rx.cond(
                    TerramonState.active_tab != "",
                    rx.box(
                        rx.cond(
                            TerramonState.active_tab == "terra",
                            rx.box(
                                rx.grid(
                                    rx.foreach(TerramonState.terra, terra_card),
                                    columns="2",
                                    spacing="2",
                                    width="100%",
                                ),
                                # Phase 19: Data stats footer
                                rx.cond(
                                    TerramonState.terra.length() > 0,
                                    rx.text(
                                        TerramonState.distinct.to_string() + " unique · "
                                        + TerramonState.terra.length().to_string() + " total",
                                        font_size="0.6em", color="#6b7280",
                                        text_align="center", padding_top="0.5em",
                                    ),
                                    rx.fragment(),
                                ),
                                width="100%",
                                max_width="380px",
                                style={"overflow_y": "auto", "max_height": "30vh"},
                            ),
                            rx.cond(
                                TerramonState.active_tab == "care",
                                creature_care_panel(),
                                rx.cond(
                                    TerramonState.active_tab == "map",
                                    earth_map(),
                                    rx.fragment(),
                                ),
                            ),
                        ),
                        width="100%",
                    ),
                    rx.fragment(),
                ),

                spacing="1",
                align="center",
                padding="0.5em 1em",
                height="100vh",
                width="100%",
                max_width="400px",
            ),
            background="linear-gradient(180deg, #0b0b0f 0%, #101018 50%, #0b0b0f 100%)",
            height="100vh",
            width="100%",
            style={"overflow": "hidden", "padding_bottom": "env(safe-area-inset-bottom)"},  # NO SCROLLING — GameBoy style
        ),
        width="100%",
        height="100vh",
    )


app = rx.App(
    # theme= deprecatd in 0.9.0 — setting dark theme via style instead
)
app.style = {
    "body": {
        "background_color": "#0b0b0f",
        "color": "#f5f5f5",
        "font_family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    }
}
# Hide Reflex branding badge in TMA
app._disable_reflex_branding = True
app.add_page(index, title="Terramon — summon your thoughts", on_load=TerramonState.load_terra)


# ── Healthcheck endpoint (Phase 19: JSON) ──────────────────
# Railway's healthcheckPath="/health" pings this route to verify the
# container is ready to serve traffic.
# Using Starlette route directly (Reflex 0.9.x compat)
def health(request):
    """Return JSON health status for Railway healthcheckPath.

    M7 (KPI cron): ``mint_count`` = number of creatures with a real mint
    record. Read from the PERSISTED seeds (not the in-memory progress,
    which resets on every page load) so the value is correct even when the
    cron probes /health without an active browser session.
    """
    from starlette.responses import JSONResponse
    try:
        # True only if the data/ dir survived the previous boot (Railway
        # volume actually attached); False when it was wiped on redeploy.
        data_persisted = DATA_PERSISTED
        seed_count = len(_MEMORY.load_all_seeds())
        # Depth win (Lens #97, prism roast 2026-08-13): complete releases —
        # seeds released WITH final words AND a real geo anchor. The KPI
        # loop scores win-path on this (1 complete release = 100%), not on
        # archetype breadth.
        complete_releases = sum(
            1 for s in _MEMORY.load_all_seeds()
            if getattr(s, "status", "") == "released"
            and (getattr(s, "final_words", "") or "").strip()
            and getattr(s, "lat", None) not in (None, 0)
            and getattr(s, "lon", None) not in (None, 0)
        )
        mint_count = sum(
            1 for s in _MEMORY.load_all_seeds() if getattr(s, "minted", False)
        )
        # Player identity (D7 retention): read from the PERSISTED players
        # registry so the KPI cron gets cohort-adjacent metrics without an
        # active browser session (same pattern as mint_count above).
        player_count = _MEMORY.count_unique_players()
        returning_players_7d = _MEMORY.count_returning_players(days=7)
        # M6 share counter: persisted share registry (JsonMemory).
        share_count = _MEMORY.count_shares()
        shares_7d = _MEMORY.count_shares_since(days=7)
        # D7 cohort + kill-condition: d7_cohort_stats() /
        # days_since_last_mint() / days_since_first_seed() land in
        # JsonMemory via a parallel task — degrade gracefully to None/False
        # while they are absent (getattr + callable fallback).
        try:
            _d7 = getattr(_MEMORY, "d7_cohort_stats", None)
            d7_stats = _d7(days=7) if callable(_d7) else None
            _dslm = getattr(_MEMORY, "days_since_last_mint", None)
            days_since_last_mint = _dslm() if callable(_dslm) else None
            _dsfs = getattr(_MEMORY, "days_since_first_seed", None)
            days_since_first_seed = _dsfs() if callable(_dsfs) else None
        except Exception:
            d7_stats = None
            days_since_last_mint = None
            days_since_first_seed = None
        # Alby Hub adapter config presence (url + api_key both set).
        alby_configured = bool(
            getattr(_ALBY, "url", None) and getattr(_ALBY, "api_key", None)
        )
        # Snapshot restore baseline (iter-19): when the data dir was wiped
        # on redeploy (volume not attached) the LOOP's git-committed
        # snapshot is the only surviving copy of the app's real counters.
        # Additive ONLY while _SNAPSHOT_RESTORED is true — a replay of the
        # app's own previously-observed counts, never fabricated data.
        _restored_mint = 0
        _restored_seed = 0
        _restored_share = 0
        if getattr(sys.modules.get(__name__), "_SNAPSHOT_RESTORED", False):
            try:
                _restored_counts = getattr(
                    sys.modules.get(__name__), "_RESTORED_COUNTS", None
                ) or {}
                _restored_mint = int(_restored_counts.get("mint_count", 0) or 0)
                _restored_seed = int(_restored_counts.get("seed_count", 0) or 0)
                _restored_share = int(_restored_counts.get("share_count", 0) or 0)
            except Exception:
                _restored_mint = 0
                _restored_seed = 0
                _restored_share = 0
        mint_count += _restored_mint
        seed_count += _restored_seed
        share_count += _restored_share
    except Exception:
        data_persisted = False
        mint_count = 0
        seed_count = 0
        complete_releases = 0
        player_count = 0
        returning_players_7d = 0
        share_count = 0
        shares_7d = 0
        alby_configured = False
        d7_stats = None
        days_since_last_mint = None
        days_since_first_seed = None
        # Degraded path: derived counters are 0, but the restored baseline
        # (if any) still surfaces so evidence survives even here.
        _restored_mint = 0
        _restored_seed = 0
        _restored_share = 0
        if getattr(sys.modules.get(__name__), "_SNAPSHOT_RESTORED", False):
            try:
                _restored_counts = getattr(
                    sys.modules.get(__name__), "_RESTORED_COUNTS", None
                ) or {}
                _restored_mint = int(_restored_counts.get("mint_count", 0) or 0)
                _restored_seed = int(_restored_counts.get("seed_count", 0) or 0)
                _restored_share = int(_restored_counts.get("share_count", 0) or 0)
            except Exception:
                _restored_mint = 0
                _restored_seed = 0
                _restored_share = 0
        mint_count = _restored_mint
        seed_count = _restored_seed
        share_count = _restored_share
    # Kill-condition watchdog: 'mint=0 for 30 days'. When no mint has EVER
    # happened (days_since_last_mint None) the clock anchors to
    # days_since_first_seed — the FIRST summon / game launch — so the kill
    # decision can still fire; it stays None only when there is no mint AND
    # no seed at all. share_rate is the lifetime share-per-summon funnel
    # (informational; None when there are no summoners).
    days_mint_zero = (
        days_since_last_mint if days_since_last_mint is not None else days_since_first_seed
    )
    share_rate = (share_count / seed_count) if seed_count > 0 else None
    return JSONResponse({
        "status": "ok",
        "tests": 527,  # pytest count, synced at iter-27 (evolve plain-handler gate: +5 tests)
        "data_persisted": data_persisted,
        "data_restored_from_snapshot": bool(
            getattr(sys.modules.get(__name__), "_SNAPSHOT_RESTORED", False)
        ),
        "restored_mint_count": _restored_mint,
        "restored_seed_count": _restored_seed,
        "restored_share_count": _restored_share,
        "snapshot_ts": getattr(sys.modules.get(__name__), "_SNAPSHOT_TS", "") or "",
        "mint_count": mint_count,
        "seed_count": seed_count,
        "complete_releases": complete_releases,
        "player_count": player_count,
        "returning_players_7d": returning_players_7d,
        "share_count": share_count,
        "shares_7d": shares_7d,
        "d7_eligible": (d7_stats or {}).get("eligible"),
        "d7_retained": (d7_stats or {}).get("retained"),
        "d7_retention": (d7_stats or {}).get("retention_rate"),
        "days_since_last_mint": days_since_last_mint,
        "kill_condition": {
            "days_mint_zero": days_mint_zero,
            "share_rate": share_rate,
            "triggered": bool(
                days_mint_zero is not None and days_mint_zero >= 30
            ),
        },
        "alby_configured": alby_configured,
    })


def static_map(request):
    """G04: self-hosted OSM static map (replaces Yandex Static Maps).

    Query params: lat, lon, zoom (default 14), w, h (default 300x200).
    Returns a PNG stitched from OSM tiles with a marker at the point.
    """
    from starlette.responses import Response

    try:
        lat = float(request.query_params.get("lat", "0"))
        lon = float(request.query_params.get("lon", "0"))
        zoom = int(request.query_params.get("zoom", "14"))
        w = int(request.query_params.get("w", "300"))
        h = int(request.query_params.get("h", "200"))
    except ValueError:
        return Response(status_code=400, content=b"bad params")

    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return Response(status_code=400, content=b"coords out of range")

    try:
        png = render_static_map(lat, lon, zoom=zoom, width=w, height=h)
    except Exception as exc:
        return Response(status_code=500, content=str(exc).encode())
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=604800"},
    )


def creature_art(request):
    """Lesson 13: serve a generated creature portrait PNG (traversal-safe).

    Query param: name=portrait_<32-hex>.png | thumb_<32-hex>.png. Files live
    on the Railway volume under data/creatures/; content-addressed filenames
    are immutable, so a 7-day Cache-Control is safe.
    """
    from starlette.responses import Response

    name = request.query_params.get("name", "")
    fp = portrait_file_path(name, os.environ.get("TERRAMON_DATA_DIR", "data"))
    if fp is None:
        return Response(status_code=404, content=b"not found")
    try:
        png = fp.read_bytes()
    except Exception as exc:
        return Response(status_code=500, content=str(exc).encode())
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=604800"},
    )


# Register the health endpoint on the underlying Starlette app
app._api.add_route("/health", health, methods=["GET"])
app._api.add_route("/static-map", static_map, methods=["GET"])
app._api.add_route("/creature-art", creature_art, methods=["GET"])

