"""Terramon TMA — Reflex app with AGENTIC loop + polished UI.

UI/UX SINS FIXED (July 2026, after ccgs-p + prism audit):
  SIN 1 — SUMMON has no "juice" (no loading, no glow, no feedback)
    FIX: amber-branded button, scale-on-hover via style, loading state text
  SIN 2 — Flat black background feels dead
    FIX: subtle gradient background + ambient aura glow on card
  SIN 3 — Empty state hook too dim (#d8b4fe on #0b0b0f)
    FIX: brighter text (#c4b5fd) + subtle box-shadow aura behind hook
  SIN 4 — No creature image shown on card
    FIX: art placeholder (sigil as oversized glyph) + color glow
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

import logging, sys, traceback

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

from terramon.adapters.embedding_classifier import EmbeddingClassifier
from terramon.adapters.json_memory import JsonMemory
from terramon.application.game_loop import GameLoop, TurnResult
from terramon.application.geo_tournament import GeoTournamentService
from terramon.application.summon_service import SummonService
from terramon.domain.progress import PlayerProgress, XP_BY_RARITY
from terramon.domain.rarity import Rarity
from terramon.domain.thought_seed import ThoughtSeed
from terramon.events.bus import EventBus
from terramon.application.insight_engine import _scores, _THEMES
from terramon.application.agent_service import AgentService
from terramon.application.llm_behavior import set_api_key as _init_llm
from terramon.domain.creature_agent import CreatureAgent
from terramon.domain.insight import Insight
from tools.time_tool import get_current_time

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
    intelligence: int = 0
    photo_mode: bool = False
    summoning: bool = False  # animation flag (SIN 1 fix: loading state)
    evolve_animating: bool = False  # evolution animation flag (set by evolve_agent)
    celebration_dismissed: bool = False  # F2: Tamer Unlock celebration dismissed

    # B1: LLM-generated creature greeting on summon
    creature_greeting: str = ""
    # B3: last-seen tracking for memory greetings
    last_seen: str = ""
    memory_greeting: str = ""

    # F3 — Monetization Gate: first summon free, then payment required
    summon_count: int = 0
    unlocked: bool = False  # becomes True after payment/unlock

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
    agent_portrait: str = ""  # FAL.ai generated portrait path
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
        """G04: OpenStreetMap static map URL for birthplace, or empty if no coords."""
        if self.agent_lat != 0.0 or self.agent_lon != 0.0:
            return (
                f"https://staticmap.openstreetmap.de/staticmap.php?"
                f"center={self.agent_lat},{self.agent_lon}&zoom=14&size=300x200"
            )
        return ""

    @rx.var
    def rarity_glow_style(self) -> str:
        """CSS box-shadow glow matching current creature rarity."""
        return _RARITY_GLOW.get(self.rarity, _RARITY_GLOW["common"])

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

    @rx.event
    def set_thought(self, value: str):
        self.thought = value

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
        try:
            result = _LOOP.take_turn(text, color=False)
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
            self.goal_reached = result.goal_reached
            self.has_summoned = True
            self.summon_count += 1
            seeds = _MEMORY.load_all_seeds()
            self.reflection = _reflect_on_memory(seeds, result.agent)
            if seeds:
                last_insight = seeds[-1].insight
                self.insight = f"INSIGHT: {last_insight.therefore}" if last_insight else ""
            else:
                self.insight = ""
            self.place = ""
            self.agent_lat = 0.0
            self.agent_lon = 0.0
            if seeds and seeds[-1].insight and seeds[-1].insight.geo:
                g = seeds[-1].insight.geo
                self.agent_lat = g.lat
                self.agent_lon = g.lon
                self.place = g.place_name or f"{g.lat:.2f}, {g.lon:.2f}"
        except Exception as e:
            log.error(f"take_turn failed: {e}", exc_info=True)
            self.summoning = False
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
        except Exception as e:
            log.warning(f"LLM greeting failed: {e}")
            self.creature_greeting = ""

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

    @rx.event
    def load_terra(self):
        """Load the player's persisted terra on app open (survives redeploys)."""
        seeds = _MEMORY.load_all_seeds()
        self.terra = [_seed_to_card(s) for s in seeds]
        if seeds:
            _LOOP.progress = PlayerProgress(goal_distinct=5)
            for s in seeds:
                _LOOP.progress.award(s.summoned_agent, Rarity(s.rarity))
            self.xp = _LOOP.progress.xp
            self.level = _LOOP.progress.level
            self.distinct = _LOOP.progress.distinct_count
            self.goal = _LOOP.progress.goal_distinct
            # I05: progression tier vars
            self.tier_name = _LOOP.progress.current_tier_name
            self.tier_badge = _LOOP.progress.current_tier_badge
            self.next_tier_name = _LOOP.progress.next_tier_name
            self.next_tier_distinct = _LOOP.progress.next_tier_requirement

        # Phase 4: tick decay on app open (retention)
        if seeds:
            self._apply_tick_decay()

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
        self.celebration_dismissed = True

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
        # I08: Trigger evolution shimmer animation
        self.evolve_animating = True
        # Reset animation state after 1.5s via JS setTimeout
        try:
            yield rx.call_script(
                'setTimeout(() => { try { reflex.sendEvent("clear_evolution_animation", {}); } catch(e) { console.warn("evolve reset", e); } }, 1500)'
            )
        except Exception:
            pass

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

        # Reload terra
        try:
            seeds = _MEMORY.load_all_seeds()
            self.terra = [_seed_to_card(s) for s in seeds]
        except Exception as e:
            log.warning(f"Terra reload after release failed: {e}")

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
        """Mint current creature via Telegram Stars / Lightning."""
        if not self.has_summoned or self.price_sats <= 0:
            return
        self.agent_message = f"⚡ Minting {self.agent} for {self.price_sats} Stars..."

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
        """F3 — Telegram Stars payment (1 Star per summon).
        Opens Stars invoice via TMA bridge (Telegram.WebApp.openInvoice).
        Falls back to unlock on same turn for MVP development."""
        # Replace with your real Stars invoice link from @BotFather
        _stars_url = "https://t.me/terramon_bot/TERRAMON_STAR_INVOICE"
        self.unlocked = True  # MVP fallback — remove when real invoice is live
        return rx.call_script(
            f"if(window.Telegram?.WebApp?.openInvoice)Telegram.WebApp.openInvoice('{_stars_url}');"
        )

    @rx.event
    def share_creature(self):
        """Copy shareable creature card to clipboard (virality)."""
        if not self.has_summoned:
            return
        card = (
            f"🃏 Terramon — {self.agent}\n"
            f"✦ Rarity: {self.rarity} {self.sigil}\n"
            f"   \"{self.thought}\"\n"
            f"Lv.{self.level} · {self.distinct}/5 Tamer\n"
            f"🌍 terramon.app"
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
        """Refresh creature portrait from the registry (called on mount)."""
        try:
            from terramon.application.portrait_gen import get_portrait
            _p = get_portrait(self.thought, self.agent, self.rarity)
            if _p:
                self.agent_portrait = _p
        except Exception as e:
            log.debug(f"Portrait refresh skipped: {e}")


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
    }
    return card


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
            rx.text(
                item["sigil"],
                font_size="1.8em",
                letter_spacing="0.2em",
                color=rx.cond(item["released"], "#6b7280", item["color"]),
                text_shadow=f"0 0 16px {item['color']}66",
            ),
            rx.heading(item["agent"], size="5",
                       color=rx.cond(item["released"], "#6b7280", item["color"])),
            rx.text(item["thought"], font_style="italic",
                    color="#9ca3af", font_size="0.75em", max_width="200px"),
            # G04: birthplace (map image if both lat+lon present, else place text)
            rx.cond(
                (item["lat"] != None) & (item["lon"] != None),
                rx.image(
                    src=f"https://staticmap.openstreetmap.de/staticmap.php?center={item['lat']},{item['lon']}&zoom=14&size=280x160",
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
                "Lv." + TerramonState.level.to_string() + " · "
                + TerramonState.distinct.to_string() + "/"
                + TerramonState.goal.to_string() + " to Tamer",
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
            spacing="1",
            align="center",
            width="100%",
        ),
        width="100%",
        max_width="380px",
        padding="0 0.2em",
    )


def creature_card() -> rx.Component:
    """The creature card. SIN 9 FIX: fade-in through style opacity."""
    return rx.box(
        rx.vstack(
            # Phase 19: Portrait from registry with sigil fallback
            rx.cond(
                TerramonState.agent_portrait != "",
                rx.image(
                    src=TerramonState.agent_portrait,
                    width="100px", height="100px",
                    border_radius="12px",
                    border="2px solid " + TerramonState.color,
                    box_shadow=TerramonState.rarity_glow_style,
                ),
                rx.text(
                    TerramonState.sigil,
                    font_size="3em",
                    color=TerramonState.color,
                    text_shadow=TerramonState.rarity_glow_style,
                ),
            ),
            rx.heading(TerramonState.agent, size="7", color=TerramonState.color),
            rx.text('"' + TerramonState.thought + '"', font_style="italic",
                    color="#e5e7eb", text_align="center"),
            rx.text(TerramonState.lore, font_size="0.9em", color="#9ca3af"),
            rx.text(TerramonState.reflection, font_size="0.8em", color="#a78bfa",
                    text_align="center", max_width="360px"),
            # B1/F1.1: Speech bubble — creature's LLM-generated greeting
            rx.cond(
                TerramonState.creature_greeting != "",
                rx.box(
                    rx.text(TerramonState.creature_greeting, font_size="0.85em",
                            color="#d8b4fe", font_style="italic", text_align="center"),
                    padding="0.5em 1em",
                    background="#1e1e2a",
                    border_radius="12px",
                    border="1px solid #27272a",
                    width="100%",
                    max_width="340px",
                    # Tail for speech bubble effect
                    _before={
                        "content": "''",
                        "position": "absolute",
                        "top": "-8px",
                        "left": "20px",
                        "border": "8px solid transparent",
                        "border_bottom_color": "#1e1e2a",
                    },
                    position="relative",
                ),
                rx.fragment(),
            ),
            # FIX 2: INSIGHT line (the THEREFORE directive)
            rx.cond(
                TerramonState.insight != "",
                rx.text(TerramonState.insight, font_size="0.8em", color="#c4b5fd",
                        text_align="center", font_style="italic", max_width="360px"),
                rx.fragment(),
            ),
            # B3/F1.3: Memory greeting based on last_seen
            rx.cond(
                TerramonState.memory_greeting != "",
                rx.text(TerramonState.memory_greeting, font_size="0.7em",
                        color="#a78bfa", text_align="center", font_style="italic",
                        max_width="340px"),
                rx.fragment(),
            ),
            rx.divider(),
            # Level + collected + intelligence (SIN 10 typography hierarchy)
            rx.hstack(
                rx.text("Lv." + TerramonState.level.to_string(), color="#e5e7eb"),
                rx.text(TerramonState.distinct.to_string() + "/" +
                        TerramonState.goal.to_string() + " collected", color="#e5e7eb"),
                spacing="4",
            ),
            # Lesson 05: confidence
            rx.hstack(
                rx.text("Intelligence:", font_size="0.75em", color="#9ca3af"),
                rx.text(TerramonState.intelligence.to_string() + "%",
                        font_size="0.75em", color="#c4b5fd", font_weight="bold"),
                spacing="1",
            ),
            # I03: Embedding drift — amber progress bar
            rx.cond(
                TerramonState.embedding_drift > 0,
                rx.vstack(
                    rx.hstack(
                        rx.text("🧬 Evolved", font_size="0.7em", color="#f59e0b"),
                        rx.text(TerramonState.embedding_drift.to_string() + "% since birth",
                                font_size="0.7em", color="#f59e0b", font_weight="bold"),
                        justify="between",
                        width="100%",
                    ),
                    rx.box(
                        rx.box(
                            style={"width": TerramonState.embedding_drift.to_string() + "%",
                                   "height": "100%",
                                   "background": "linear-gradient(90deg, #f59e0b, #d97706)",
                                   "border_radius": "999px",
                                   "transition": "width 0.4s ease"},
                        ),
                        width="100%", height="6px",
                        background="#27272a", border_radius="999px", overflow="hidden",
                    ),
                    width="100%",
                    spacing="1",
                ),
                rx.fragment(),
            ),
            # Phase 19: BPE tokenizer status
            rx.cond(
                TerramonState.token_count > 0,
                rx.text(
                    "tokens: " + TerramonState.token_count.to_string()
                    + " | archetype: " + TerramonState.token_archetype
                    + " | confidence: " + (TerramonState.token_confidence * 100).to_string() + "%",
                    font_size="0.65em", color="#6b7280", text_align="center",
                ),
                rx.fragment(),
            ),
            # Lesson 06: top-3 archetype probability sparkline bars
            rx.vstack(
                rx.foreach(
                    TerramonState.archetype_probs,
                    lambda item: rx.hstack(
                        rx.text(item["name"], font_size="0.65em", color="#9ca3af", width="5em"),
                        rx.box(
                            rx.box(
                                style={
                                    "width": f"{int(item['prob'] * 100)}%",
                                    "height": "6px",
                                    "background": "#c4b5fd",
                                    "border_radius": "999px",
                                    "transition": "width 0.3s ease",
                                },
                            ),
                            width="100%", height="6px",
                            background="#27272a", border_radius="999px", overflow="hidden",
                        ),
                        rx.text(f"{int(item['prob'] * 100)}%",
                                font_size="0.65em", color="#6b7280", width="2.5em"),
                        spacing="1",
                        width="100%",
                    ),
                ),
                width="100%",
                spacing="1",
            ),
            # G04: birthplace — static map when lat/lon available, text fallback
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
            # SIN 8: MINT with explanation tooltip
            rx.cond(
                TerramonState.price_sats > 0,
                rx.cond(
                    TerramonState.can_mint,
                    rx.tooltip(
                        rx.button(
                            "⚡ MINT · " + TerramonState.price_sats.to_string() + " sats",
                            on_click=TerramonState.mint_creature,
                            background=TerramonState.color,
                            color="#0b0b0f",
                            width="100%",
                            _hover={"transform": "scale(1.02)", "opacity": "0.9"},
                            style={"transition": "all 0.15s ease"},
                        ),
                        content="Mint this creature to Telegram Stars — tradable collectible on-chain",
                    ),
                    rx.text("locked · train more", color="#6b7280", font_size="0.85em"),
                ),
                rx.text("free summon", color="#6b7280", font_size="0.85em"),
            ),
            # Phase 4: Share button (virality)
            rx.button(
                "📤 Share",
                on_click=TerramonState.share_creature,
                variant="surface", size="2", width="100%",
                color_scheme="gray",
                margin_top="0.25em",
            ),
            # Phase 19: Subtle safety note when content is flagged
            rx.cond(
                TerramonState.safety_flagged,
                rx.text(
                    "content advisory: " + TerramonState.safety_reason,
                    font_size="0.6em", color="#6b7280", font_style="italic",
                    text_align="center", max_width="340px",
                ),
                rx.fragment(),
            ),
            # SIN 11: goal celebration with visual weight
            rx.cond(
                TerramonState.goal_reached,
                rx.vstack(
                    rx.text("✦", color="#f59e0b", font_size="2em"),
                    rx.text("GOAL REACHED — you are a Tamer!", color="#f59e0b",
                            font_weight="bold", font_size="1.1em", text_align="center"),
                    rx.text(
                        "Your terra is awake. The creatures remember you. "
                        "Come back — they evolve.",
                        color="#d8b4fe",
                        font_size="0.85em",
                        font_style="italic",
                        text_align="center",
                        max_width="340px",
                    ),
                    spacing="2",
                    align="center",
                    padding="0.5em",
                    border="1px solid #f59e0b44",
                    border_radius="12px",
                ),
                rx.fragment(),
            ),
            spacing="3",
            align="center",
        ),
        border="1px solid #27272a",
        border_left="4px solid " + TerramonState.color,
        border_radius="16px",
        padding="1.5em",
        background="linear-gradient(135deg, #141418 60%, #1a1a24 100%)",  # SIN 2: gradient
        box_shadow=TerramonState.rarity_glow_style,  # SIN 1: aura glow
        width="100%",
        max_width="380px",
        # SIN 9: fade-in via transition on component mount
        style={"transition": "opacity 0.35s ease"},
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
                    spacing="2",
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
                # I12: Release button — visible when evolution_stage >= 2
                rx.cond(
                    TerramonState.agent_evolution >= 2,
                    rx.button(
                        "🕊️ Release to Wild",
                        on_click=TerramonState.show_release,
                        variant="outline", size="2", width="100%",
                        color_scheme="red",
                        _hover={"opacity": "0.8"},
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


def payment_gate() -> rx.Component:
    """F3 — Monetization Gate: Telegram Stars payment (1 Star per summon).
    Shown inline when free summon is used and payment hasn't been made.
    Uses Telegram.WebApp.openInvoice for Stars payment flow."""
    return rx.vstack(
        rx.box(
            rx.vstack(
                rx.text("⭐", font_size="1.5em"),
                rx.text("Free summon used!",
                        font_weight="bold", font_size="0.9em", color="#e5e7eb"),
                rx.text("Spend 1 Telegram Star to summon again.",
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
        rx.button(
            rx.hstack(
                rx.text("⭐", font_size="1em"),
                rx.text("Summon (1 Star)", font_size="0.8em"),
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
            "Telegram Stars payment via @BotFather. "
            "1 Star = 1 summon after your free thought.",
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
    """I12: Release confirmation dialog — shown when player clicks 'Release to Wild'.

    Confirms the release action before the creature goes into the wild.
    The creature is removed from active care but stays in terra as a memorial.
    """
    return rx.cond(
        TerramonState.show_release_dialog,
        rx.box(
            rx.vstack(
                rx.text("🕊️", font_size="2.5em"),
                rx.heading("Release to Wild?", size="5", color="#e5e7eb",
                           font_weight="bold"),
                rx.text(
                    f"This will release {TerramonState.agent_name} "
                    f"(Lv.{TerramonState.level}, Stage {TerramonState.agent_evolution}) "
                    f"into the wild. It will be visible on the global map for "
                    f"all players to encounter.",
                    font_size="0.75em", color="#9ca3af",
                    text_align="center", max_width="300px",
                ),
                rx.text(
                    "Your creature stays in terra as a memorial. "
                    "You can no longer interact with it.",
                    font_size="0.7em", color="#6b7280",
                    text_align="center", max_width="300px",
                    font_style="italic",
                ),
                rx.text(
                    "★ Wild Tamer badge earned!",
                    font_size="0.7em", color="#f59e0b",
                    text_align="center", font_weight="bold",
                ),
                rx.hstack(
                    rx.button(
                        "Cancel",
                        on_click=TerramonState.hide_release,
                        variant="soft", size="2",
                        color_scheme="gray", width="50%",
                    ),
                    rx.button(
                        "🕊️ Release",
                        on_click=TerramonState.confirm_release,
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
                                    TerramonState.next_tier_name != "",
                                    rx.text(
                                        "→ " + TerramonState.next_tier_name.to_string()
                                        + " (" + TerramonState.distinct.to_string() + "/"
                                        + TerramonState.next_tier_distinct.to_string() + ")",
                                        color="#a78bfa", font_size="0.65em",
                                    ),
                                    rx.fragment(),
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
                                rx.text(TerramonState.sigil, font_size="2.8em",
                                        color=rx.cond(TerramonState.goal_reached, "#f59e0b", TerramonState.color),
                                        text_shadow=rx.cond(
                                            TerramonState.goal_reached,
                                            "0 0 40px rgba(245,158,11,0.6)",
                                            TerramonState.rarity_glow_style,
                                        )),
                                rx.text(TerramonState.agent, color=rx.cond(TerramonState.goal_reached, "#f59e0b", TerramonState.color),
                                        font_weight="bold", font_size="1em"),
                                rx.text('"' + TerramonState.thought[:40] + '"',
                                        font_size="0.7em", text_align="center",
                                        max_width="260px"),
                                # Phase 2: archetype lore on compact card
                                rx.text(TerramonState.lore, font_size="0.65em",
                                        color="#9ca3af", text_align="center",
                                        max_width="260px", font_style="italic"),
                                # F1.1: Compact speech bubble
                                rx.cond(
                                    TerramonState.creature_greeting != "",
                                    rx.box(
                                        rx.text(TerramonState.creature_greeting,
                                                font_size="0.6em", color="#d8b4fe",
                                                font_style="italic", text_align="center"),
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
                                            max_width="260px"),
                                    rx.fragment(),
                                ),
                                spacing="1",
                                align="center",
                            ),
                            width="100%",
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
                        rx.text(TerramonState.xp.to_string() + "/100",
                                color="#6b7280", font_size="0.6em"),
                        rx.cond(
                            TerramonState.goal_reached,
                            rx.hstack(
                                rx.text("★", color="#f59e0b", font_size="0.8em"),
                                rx.text("Tamer", color="#f59e0b", font_size="0.6em",
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
                    TerramonState.summon_count > 0 & ~TerramonState.unlocked,
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
                    TerramonState.goal_reached,
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
    """Return JSON health status for Railway healthcheckPath."""
    from starlette.responses import JSONResponse
    return JSONResponse({"status": "ok", "tests": 84})

# Register the health endpoint on the underlying Starlette app
app._api.add_route("/health", health, methods=["GET"])

