"""
terramon_wbs.py — Production WBS for Terramon Neural Network Game.

Derived from 100 Schell Lenses × book text → TRIZ → VOID → agentic-coding → ai-engineering-loop.
Each task = one dispatchable subagent unit. Sequential execution (rate-limit safe).

Pillars:
  🧬 P1: Thought → unique self-learning AI agent  (tasks T01-T40)
  🌍 P2: Real planet Earth (geo-anchored)          (tasks G01-G15)
  🤝 P3: Multiplayer inter-creature interaction    (tasks M01-M20)
  🧠 P4: Infrastructure for self-learning          (tasks I01-I25)

Priority: 🔴 CRITICAL > 🟡 HIGH > 🔵 MEDIUM > 🟢 NICE

Core insight: Terramon IS the neural network. Creatures ARE the MoE experts.
Players TRAIN the model by summoning. One system, not two.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════
# Types
# ═══════════════════════════════════════════════════════════════════════

class Priority(Enum):
    CRITICAL = "🔴"
    HIGH     = "🟡"
    MEDIUM   = "🔵"
    NICE     = "🟢"

class Pillar(Enum):
    P1_AGENT      = "🧬 P1"
    P2_GEO        = "🌍 P2"
    P3_MULTIPLAYER = "🤝 P3"
    P4_INFRA      = "🧠 P4"

class Category(Enum):
    BUG           = "BUG"
    HARDCODED     = "HARDCODED"
    DEAD          = "DEAD"
    MISSING_UX    = "MISSING_UX"
    PHILOSOPHICAL = "PHILOSOPHICAL"


@dataclass
class WBSTask:
    """One dispatchable unit of work for a subagent."""
    id: str                    # e.g. "T01", "G05", "M12"
    title: str
    description: str
    pillar: Pillar
    priority: Priority
    category: Category
    lens_nums: list[int]       # Schell lens numbers that drove this
    files_to_modify: list[str]
    acceptance_criteria: list[str]
    depends_on: list[str] = field(default_factory=list)  # task IDs that must be done first
    estimated_complexity: str = "M"  # S/M/L/XL
    subagent_context: str = ""       # extra context for the subagent prompt

    def dispatch_prompt(self) -> str:
        """Generate the full prompt for a subagent dispatch."""
        deps = f" Depends on: {', '.join(self.depends_on)}" if self.depends_on else ""
        return (
            f"## {self.priority.value} {self.pillar.value} | {self.id}: {self.title}\n"
            f"{self.description}\n"
            f"**Files:** {', '.join(self.files_to_modify)}\n"
            f"**Acceptance:**\n" +
            "\n".join(f"  ✅ {a}" for a in self.acceptance_criteria) +
            f"\n{deps}\n"
            f"{self.subagent_context}\n"
            f"Read files before editing. Run `python3 -m pytest tests/ -q` after changes. 84 tests must pass."
        )


# ═══════════════════════════════════════════════════════════════════════
# TASKS
# ═══════════════════════════════════════════════════════════════════════

WBS: list[WBSTask] = []

# ───────────────────────────────────────────────────────────────────────
# 🔴 PHASE 0: CRITICAL BUGS — Fix things that are BROKEN right now
# ───────────────────────────────────────────────────────────────────────

WBS.append(WBSTask(
    id="T01",
    title="Bond persistence — stop bond reset on every summon",
    description="Bond level, player_affinity, milestone_memory, player_journal are created as throwaway "
                "CreatureAgent instances in summon() and care handlers. The bond data is LOST every time. "
                "Must persist to JsonMemory and reload on app open.",
    pillar=Pillar.P1_AGENT,
    priority=Priority.CRITICAL,
    category=Category.BUG,
    lens_nums=[84, 75, 88, 100],
    files_to_modify=["terramon_tma/terramon_tma.py", "terramon/adapters/json_memory.py",
                     "terramon/domain/creature_agent.py", "terramon/application/agent_service.py"],
    acceptance_criteria=[
        "bond_level persists across app restarts (save to JsonMemory)",
        "player_affinity vector survives save/load round-trip",
        "milestone_memory list persists and grows with interactions",
        "CreatureAgent in care handlers uses PERSISTED instance, not throwaway '_tmp'",
        "84/84 tests pass"
    ],
    subagent_context="The domain model already has bond_level, player_affinity, milestone_memory fields "
                     "on CreatureAgent (added by Cluster 6 prism). They just need SERIALIZATION in JsonMemory "
                     "and RELOAD in the TMA state. Don't modify the existing 7 new fields — add serialization."
))

WBS.append(WBSTask(
    id="T02",
    title="Unique THEREFORE from embedding — not 1 of 12 templates",
    description="Currently THEREFORE is 1 of 12 hardcoded strings per archetype (BEHAVIOR_BY_BARRIER). "
                "Should be LLM-generated from the 512-dim embedding + archetype + geo. "
                "The embedding is now persisted on Insight (from Cluster 5). Use it.",
    pillar=Pillar.P1_AGENT,
    priority=Priority.CRITICAL,
    category=Category.PHILOSOPHICAL,
    lens_nums=[65, 70, 100, 73, 23],
    files_to_modify=["terramon/application/k3_insight_engine.py",
                     "terramon/application/llm_behavior.py",
                     "terramon/domain/insight.py"],
    acceptance_criteria=[
        "extract_insight() passes embedding to Insight",
        "LLM generate_response() receives embedding + archetype + geo",
        "THEREFORE references something from the embedding (not archetype template)",
        "Fallback: if LLM unavailable, use archetype template (no crash)",
        "84/84 tests pass"
    ],
    subagent_context="embedding dict is now on Insight (512-dim sparse). Add a prompt builder that "
                     "serializes top-10 embedding features as words. embedding IS the uniqueness."
))

WBS.append(WBSTask(
    id="T03",
    title="NostrPublisher wiring — dead adapter to live channel",
    description="Full BIP-340 Schnorr implementation with WebSocket relays exists but has ZERO callers. "
                "SummonService publishes AgentSummoned event but NostrPublisher never receives it. "
                "Wire: AgentSummoned → NostrPublisher.publish() → creature card on Nostr relay.",
    pillar=Pillar.P3_MULTIPLAYER,
    priority=Priority.CRITICAL,
    category=Category.DEAD,
    lens_nums=[86, 85, 46, 96],
    files_to_modify=["terramon/events/bus.py", "terramon/events/agent_summoned.py",
                     "terramon/adapters/nostr_publisher.py",
                     "terramon/application/summon_service.py"],
    acceptance_criteria=[
        "NostrPublisher.subscribe(AgentSummoned) registered in app init",
        "On summon: Nostr event created with creature card data (archetype, insight, geo)",
        "Event signed with BIP-340 and broadcast to 3+ relays",
        "No crash if relay unreachable (graceful fail)",
        "84/84 tests pass"
    ],
    subagent_context="nostr_publisher.py has full Schnorr signing + WebSocket. It's just not CALLED. "
                     "Wire it into the EventBus middleware chain. The agent_summoned.py already has "
                     "share_code, archetype, geo_hint fields (added by Cluster 6 prism)."
))

# ───────────────────────────────────────────────────────────────────────
# 🟡 PHASE 1: HIGH — Core mechanics that should exist
# ───────────────────────────────────────────────────────────────────────

WBS.append(WBSTask(
    id="T04",
    title="Per-archetype mechanical stats — Hero ≠ Sage in decay",
    description="All 12 archetypes have identical stats (80/80/60), decay rates (5/3/2), "
                "and evolution requirements (Lv10/❤️70/XP500). Must differ by archetype. "
                "Hero = high energy, low hunger. Orphan = low happiness, needy. Sage = slow decay.",
    pillar=Pillar.P1_AGENT,
    priority=Priority.HIGH,
    category=Category.HARDCODED,
    lens_nums=[77, 44, 47, 31],
    files_to_modify=["terramon/domain/creature_agent.py"],
    acceptance_criteria=[
        "_ARCHETYPE_STATS dict defines per-archetype starting stats (all 12)",
        "_ARCHETYPE_DECAY dict defines per-archetype decay rates",
        "EvolutionRequirement varies by archetype (Hero evolves faster, Sage slower)",
        "STATE_MOD system enhanced with archetype-specific multipliers",
        "Backward compat: if archetype not in dict, use defaults",
        "84/84 tests pass"
    ],
    subagent_context="creature_agent.py already has DECAY_HUNGER etc. as module constants. "
                     "Replace with per-archetype dicts. The STATE_MOD system from Core Experience "
                     "prism is the right pattern to extend."
))

WBS.append(WBSTask(
    id="T05",
    title="embedding-driven THEREFORE via LLM — wire the full pipeline",
    description="The embedding is persisted on Insight but not used by LLM. Need to: "
                "(1) build a prompt from embedding features, (2) call LLM with it, "
                "(3) parse the unique THEREFORE, (4) fall back to template if LLM fails.",
    pillar=Pillar.P1_AGENT,
    priority=Priority.HIGH,
    category=Category.MISSING_UX,
    lens_nums=[65, 100, 23, 73],
    files_to_modify=["terramon/application/k3_insight_engine.py",
                     "terramon/application/llm_behavior.py",
                     "terramon/domain/insight.py"],
    acceptance_criteria=[
        "Insight.embedding serialized to prompt for LLM",
        "LLM returns unique THEREFORE (validated: not in 12-template set)",
        "If LLM fails, falls back to archetype template without crash",
        "THEREFORE stored in ThoughtSeed and displayed on creature card",
        "84/84 tests pass"
    ],
    subagent_context="embedding is a dict[int, float] on Insight. Top-K features can be mapped to "
                     "words via a lookup table (hash → nearest prototype word). Full embedding → "
                     "LLM prompt is the final goal."
))

WBS.append(WBSTask(
    id="G01",
    title="Geo → embedding modifier — where on Earth matters",
    description="A creature born in Kraków should differ from one born in Tokyo. "
                "Geo context (lat/lon/place_name) should MODIFY the embedding before MoE routing. "
                "Simple approach: add geo-derived features to the encoding vector.",
    pillar=Pillar.P2_GEO,
    priority=Priority.HIGH,
    category=Category.MISSING_UX,
    lens_nums=[74, 44, 75, 21],
    files_to_modify=["terramon/application/insight_engine.py",
                     "terramon/adapters/embedding_classifier.py",
                     "terramon/domain/insight.py"],
    acceptance_criteria=[
        "GeoContext features encoded as additional dimensions in the 512-dim vector",
        "Same thought at different geos produces different archetype/insight",
        "If no geo available (lat=0, lon=0), encoding unchanged (backward compat)",
        "84/84 tests pass"
    ],
    subagent_context="embedding_classifier._encode() returns 512-dim dict. Add geo-derived "
                     "features: climate zone, continent hash, urban/rural flag. Use geopy or a "
                     "simple lookup. Keep it additive so no-geo still works."
))

WBS.append(WBSTask(
    id="T06",
    title="creature_agent.py direct tests — 0 tests → 20+ tests",
    description="The core gameplay file (creature_agent.py, 579 lines) has ZERO direct tests. "
                "Feed, play, rest, talk, tick, _apply_tick, _compute_state, _compute_mood, "
                "can_evolve, evolve — none tested.",
    pillar=Pillar.P1_AGENT,
    priority=Priority.HIGH,
    category=Category.MISSING_UX,
    lens_nums=[91, 14, 92],
    files_to_modify=["tests/test_creature_agent.py"],
    acceptance_criteria=[
        "test_feed_updates_stats_hunger_energy",
        "test_play_uses_state_mod_when_tired",
        "test_rest_restores_energy",
        "test_talk_increases_happiness",
        "test_tick_ema_decay_approaches_zero",
        "test_state_transition_hungry_below_threshold",
        "test_mood_computed_from_moving_average",
        "test_evolution_probability_sigmoid_monotonic",
        "test_can_evolve_returns_true_above_threshold",
        "test_archetype_verb_feeling_sound_nonempty",
        "test_apply_tick_day_night_modifier",
        "test_tick_gradient_clip_max_delta_15",
        "All 84 existing tests + 20+ new = 104+ passing"
    ],
    subagent_context="New file: tests/test_creature_agent.py. The domain model is pure (no I/O). "
                     "Instantiate CreatureAgent with various params, call methods, assert stat changes. "
                     "Use pytest. No mocks needed — all stat math is deterministic."
))

WBS.append(WBSTask(
    id="T07",
    title="MINT based on embedding uniqueness — value = rarity of thought",
    description="Current MINT price is hardcoded by rarity tier (0/0/15/25 Stars). "
                "Instead: price = f(embedding uniqueness, rarity, bond_level). "
                "Embedding nearest-neighbor distance to all existing creatures = scarcity.",
    pillar=Pillar.P1_AGENT,
    priority=Priority.HIGH,
    category=Category.HARDCODED,
    lens_nums=[46, 96, 28, 40],
    files_to_modify=["terramon/application/payment_gate.py",
                     "terramon/domain/rarity.py",
                     "terramon_tma/terramon_tma.py",
                     "terramon/adapters/json_memory.py"],
    acceptance_criteria=[
        "report_stats() computes nearest-neighbor distance in embedding space",
        "MINT price = base_price × (1 + uniqueness_bonus)",
        "uniqueness_bonus from 1.0 (common thought) to 10.0 (one-of-a-kind)",
        "Embedding distance metric: cosine over 512-dim vectors",
        "84/84 tests pass"
    ],
    subagent_context="JsonMemory.report_stats() was added by Phase 9. Extend it to load all "
                     "embeddings and compute pairwise cosine distances. The MIN distance to any "
                     "existing creature = uniqueness score."
))

# ───────────────────────────────────────────────────────────────────────
# 🌍 PHASE 2: GEO — Real planet Earth features
# ───────────────────────────────────────────────────────────────────────

WBS.append(WBSTask(
    id="G02",
    title="Creature map view — see creatures on real Earth",
    description="Every creature has lat/lon/place_name. Show them on a map. "
                "Use Leaflet.js or a simple SVG world map in the TMA. "
                "Each creature = a dot at its birth coordinates.",
    pillar=Pillar.P2_GEO,
    priority=Priority.HIGH,
    category=Category.MISSING_UX,
    lens_nums=[74, 21, 86, 59],
    files_to_modify=["terramon_tma/terramon_tma.py"],
    acceptance_criteria=[
        "TMA has a Map tab that shows creature locations",
        "Each creature rendered as a colored dot (rarity color) at lat/lon",
        "Tap dot → show creature card summary",
        "Player's current creature highlighted",
        "84/84 tests pass"
    ],
    subagent_context="Use an rx.image with an SVG world map and overlay dots, or embed a "
                     "Leaflet iframe. Keep it simple — SVG overlay is safer for TMA. "
                     "Coordinates come from ThoughtSeed.lat/lon."
))

WBS.append(WBSTask(
    id="G03",
    title="Proximity discovery — what creatures exist within 1km of me?",
    description="When player opens the app, compute which creatures (from ALL players) are "
                "within 1km of their current location. Show as 'Nearby creatures'.",
    pillar=Pillar.P2_GEO,
    priority=Priority.MEDIUM,
    category=Category.MISSING_UX,
    lens_nums=[86, 84, 79, 74],
    files_to_modify=["terramon/adapters/json_memory.py",
                     "terramon_tma/terramon_tma.py"],
    acceptance_criteria=[
        "report_stats() includes proximity query: lat/lon → nearby creatures",
        "Nearby creatures shown on Map tab or in a 'Nearby' section",
        "Distance in km shown for each nearby creature",
        "Only shows if player shares location (Telegram.LocationButton)",
        "84/84 tests pass"
    ],
    subagent_context="Haversine formula for distance. Currently all creatures are in "
                     "JsonMemory (single-player). For cross-player proximity, need either "
                     "a shared DB or Nostr-based directory."
))

WBS.append(WBSTask(
    id="G04",
    title="Street View birthplace — visit where your creature was born",
    description="Show a Street View / satellite image of the GPS coordinate where the "
                "creature was born. Embed as an iframe or image from a mapping API.",
    pillar=Pillar.P2_GEO,
    priority=Priority.NICE,
    category=Category.MISSING_UX,
    lens_nums=[74, 64, 75, 63],
    files_to_modify=["terramon_tma/terramon_tma.py"],
    acceptance_criteria=[
        "Creature card has '📍 Born here' link/image",
        "Shows static map or satellite image of lat/lon",
        "Fallback: place name text if no map available",
        "84/84 tests pass"
    ],
    subagent_context="Use OpenStreetMap static map API (free, no key needed). "
                     "Format: https://staticmap.openstreetmap.de/staticmap.php?center=lat,lon&zoom=14&size=300x200"
))

# ───────────────────────────────────────────────────────────────────────
# 🤝 PHASE 3: MULTIPLAYER INTER-CREATURE
# ───────────────────────────────────────────────────────────────────────

WBS.append(WBSTask(
    id="M01",
    title="Cross-player creature proximity events",
    description="When two creatures from different players exist within 1km on the real map, "
                "trigger a proximity event: both players get a notification, creatures exchange "
                "resonance data, bond level gets a small bonus.",
    pillar=Pillar.P3_MULTIPLAYER,
    priority=Priority.HIGH,
    category=Category.MISSING_UX,
    lens_nums=[79, 84, 86, 36, 37],
    files_to_modify=["terramon/events/bus.py",
                     "terramon/events/agent_summoned.py",
                     "terramon/application/game_loop.py",
                     "terramon/adapters/nostr_publisher.py"],
    acceptance_criteria=[
        "Proximity check runs on summon (query nearby creatures from other players)",
        "If proximity found → emit ProximityEvent with both creatures",
        "Both players receive notification (via TMA or Nostr DM)",
        "Bond level bonus applied to both creatures",
        "Minimum distance configurable (default 1km)",
        "84/84 tests pass"
    ],
    subagent_context="This is the FIRST cross-player feature. Use Nostr as the communication "
                     "channel: creature A's relay broadcasts presence at lat/lon. Creature B's "
                     "relay receives it. Proximity = haversine < 1km."
))

WBS.append(WBSTask(
    id="M02",
    title="Geo-tournament — creatures compete by proximity",
    description="When two creatures of the same archetype meet on the map, trigger a "
                "geo-tournament: whose Hero is stronger? Winner determined by bond_level + "
                "evolution_stage + embedding_score.",
    pillar=Pillar.P3_MULTIPLAYER,
    priority=Priority.MEDIUM,
    category=Category.MISSING_UX,
    lens_nums=[36, 33, 80, 30],
    files_to_modify=["terramon/application/game_loop.py",
                     "terramon_tma/terramon_tma.py"],
    acceptance_criteria=[
        "Same-archetype proximity triggers tournament offer",
        "Both players must accept within 24h",
        "Winner determined by composite score (bond×0.4 + evolution×0.3 + embedding×0.3)",
        "Winner gets XP bonus. Loser gets consolation XP.",
        "84/84 tests pass"
    ],
    subagent_context="Keep it async (Nostr-based). No real-time connection needed. "
                     "Tournament result computed server-side in Python."
))

WBS.append(WBSTask(
    id="M03",
    title="Fusion summon — two players, one creature",
    description="Two players can combine their thoughts into one fusion creature. "
                "Both type a thought → embeddings averaged → MoE on the average → "
                "fusion creature with both players as 'parents'. Persisted to both accounts.",
    pillar=Pillar.P3_MULTIPLAYER,
    priority=Priority.MEDIUM,
    category=Category.MISSING_UX,
    lens_nums=[37, 88, 38, 65, 23],
    files_to_modify=["terramon/application/summon_service.py",
                     "terramon/application/k3_insight_engine.py",
                     "terramon/adapters/json_memory.py"],
    acceptance_criteria=[
        "New Endpoint: POST /fusion with two thought texts + two player IDs",
        "Embeddings averaged: fused_vector = (emb_a + emb_b) / 2",
        "MoE forward pass on fused_vector",
        "Fusion creature saved to BOTH players' memory",
        "Fusion creature marked with 'fusion: True' and both player IDs",
        "84/84 tests pass"
    ],
    subagent_context="Fusion = 2-player summon. The k3_insight_engine already has "
                     "extract_insight() — create extract_fusion_insight(t1, t2) that "
                     "encodes both, averages, runs MoE."
))

WBS.append(WBSTask(
    id="M04",
    title="Creature trading — MINT → Nostr → trade",
    description="Players can list their creatures for trade. MINT creates a Nostr event "
                "with the creature data. Other players can bid with their own creatures or Stars. "
                "Trade execution transfers ownership.",
    pillar=Pillar.P3_MULTIPLAYER,
    priority=Priority.MEDIUM,
    category=Category.MISSING_UX,
    lens_nums=[46, 96, 94, 95, 28],
    files_to_modify=["terramon/adapters/nostr_publisher.py",
                     "terramon/application/payment_gate.py",
                     "terramon_tma/terramon_tma.py"],
    acceptance_criteria=[
        "MintCreature event published to Nostr relay",
        "TradeOffer event format: {creature_id, ask_price_or_creature, seller_pubkey}",
        "Trade execution transfers creature ownership in JsonMemory",
        "Minimum price = embedding_uniqueness_score × base_price",
        "84/84 tests pass"
    ],
    subagent_context="This builds on T03 (Nostr wiring). The Nostr event is the order book. "
                     "No central server needed — peer-to-peer trading via relays."
))

# ───────────────────────────────────────────────────────────────────────
# 🧠 PHASE 4: INFRASTRUCTURE FOR SELF-LEARNING
# ───────────────────────────────────────────────────────────────────────

WBS.append(WBSTask(
    id="I01",
    title="SQLite migration — replace full-file JSON reads",
    description="JsonMemory.load_all_seeds() reads the ENTIRE file into memory. "
                "After 10K+ summons, this OOMs. Migrate to SQLite for streaming reads, "
                "indexed queries, and proximity searches.",
    pillar=Pillar.P4_INFRA,
    priority=Priority.HIGH,
    category=Category.BUG,
    lens_nums=[14, 92, 93],
    files_to_modify=["terramon/adapters/json_memory.py",
                     "terramon/domain/thought_seed.py",
                     "requirements.txt"],
    acceptance_criteria=[
        "SqliteMemory class with same MemoryPort interface as JsonMemory",
        "save_seed() INSERTs into sqlite (NOT append to JSONL)",
        "load_all_seeds() SELECTs with pagination (LIMIT/OFFSET)",
        "report_stats() uses SQL COUNT/GROUP BY",
        "Embedding proximity query uses sqlite RTree or in-memory cosine",
        "Backward compat: old JSONL data migrated on first run",
        "84/84 tests pass"
    ],
    subagent_context="Keep JsonMemory working during transition. Add SqliteMemory in the "
                     "same file. Add a migrate() function. The MemoryPort protocol makes "
                     "this a drop-in replacement."
))

WBS.append(WBSTask(
    id="I02",
    title="Circuit breaker for external APIs (LLM, FAL, HF)",
    description="If OpenRouter, FAL.ai, or HuggingFace are down, the system should "
                "stop trying for 60 seconds after 3 consecutive failures. "
                "Currently every summon tries the API and waits 30s timeout.",
    pillar=Pillar.P4_INFRA,
    priority=Priority.HIGH,
    category=Category.BUG,
    lens_nums=[14, 92],
    files_to_modify=["terramon/application/llm_behavior.py",
                     "terramon/adapters/fal_art.py",
                     "terramon/adapters/hf_adapter.py"],
    acceptance_criteria=[
        "CircuitBreaker class: max_failures=3, cooldown=60s",
        "LLM _call_with_retry uses circuit breaker",
        "FAL.ai request uses circuit breaker",
        "After cooldown, first success resets counter",
        "84/84 tests pass"
    ],
    subagent_context="Simple state machine: CLOSED → OPEN (3 failures) → HALF_OPEN (after 60s) → "
                     "CLOSED (first success) or OPEN (another failure)."
))

WBS.append(WBSTask(
    id="I03",
    title="Embedding drift tracking — creature learns over time",
    description="As the player types more thoughts, their 512-dim embedding space evolves. "
                "Track embedding drift: cosine distance between first summon and current summon. "
                "Show 'Your creature has grown X% since birth'.",
    pillar=Pillar.P4_INFRA,
    priority=Priority.MEDIUM,
    category=Category.MISSING_UX,
    lens_nums=[39, 49, 64, 81],
    files_to_modify=["terramon/adapters/json_memory.py",
                     "terramon/domain/creature_agent.py",
                     "terramon_tma/terramon_tma.py"],
    acceptance_criteria=[
        "First summon's embedding stored as 'birth_embedding' on ThoughtSeed",
        "Embedding drift = cosine(birth_embedding, latest_embedding)",
        "Drift shown on creature card: 'Evolved X% since birth'",
        "Drift displayed as a progress ring or percentage",
        "84/84 tests pass"
    ],
    subagent_context="Embedding is already persisted on Insight (Cluster 5 prism). "
                     "Store the FIRST embedding separately as birth_embedding on CreatureAgent. "
                     "Drift = 1 - cosine(birth, current)."
))

WBS.append(WBSTask(
    id="I04",
    title="Multi-creature squad — 3 creatures, one team",
    description="Players can form a squad of up to 3 creatures. Squad members have "
                "cross-creature resonances that grant passive bonuses. "
                "E.g., Hero + Caregiver = 'Protector' resonance: both get +10% happiness.",
    pillar=Pillar.P1_AGENT,
    priority=Priority.MEDIUM,
    category=Category.MISSING_UX,
    lens_nums=[50, 79, 89, 37],
    files_to_modify=["terramon/domain/progress.py",
                     "terramon/domain/creature_agent.py",
                     "terramon_tma/terramon_tma.py"],
    acceptance_criteria=[
        "SquadState dataclass with up to 3 creature IDs",
        "Resonance pairs defined: 8 pairs (Cluster 2 prism)",
        "Active squad members get resonance bonuses (stat mods)",
        "Squad selectable in TMA (tap creature → 'Add to squad')",
        "84/84 tests pass"
    ],
    subagent_context="8 cross-creature resonances already defined by Cluster 2 prism. "
                     "Store squad in PlayerProgress or a new domain object."
))

WBS.append(WBSTask(
    id="I05",
    title="Post-goal progression — infinite horizon",
    description="After reaching Tamer (5/5), the game dead-ends. Need: "
                "★ Tamer → ★★ Master (12/12) → ★★★ Legend (all archetypes on 3 continents). "
                "Each tier unlocks: Scout permanently, World map, Squad feature.",
    pillar=Pillar.P1_AGENT,
    priority=Priority.MEDIUM,
    category=Category.MISSING_UX,
    lens_nums=[61, 25, 49, 97],
    files_to_modify=["terramon/domain/progress.py",
                     "terramon_tma/terramon_tma.py"],
    acceptance_criteria=[
        "Tier system: Tamer (5) → Master (12) → Legend (36 = 12×3 continents)",
        "Each tier unlocks a new feature (Scout, Map, Squad)",
        "Post-goal player sees next tier requirements, not dead end",
        "84/84 tests pass"
    ],
    subagent_context="PlayerProgress already has goal_distinct. Add tier progression: "
                     "goal_tiers = [5, 12, 36] with tier_names and tier_unlocks."
))

WBS.append(WBSTask(
    id="I06",
    title="3-phase summon animation — input → portal → creature",
    description="Summon is currently instant: button click → creature card appears. "
                "Should be: (1) text dissolves upward, (2) expanding portal glow, "
                "(3) creature card slides in from bottom. Each phase 0.3-0.4s.",
    pillar=Pillar.P1_AGENT,
    priority=Priority.MEDIUM,
    category=Category.MISSING_UX,
    lens_nums=[58, 61, 57, 59],
    files_to_modify=["terramon_tma/terramon_tma.py"],
    acceptance_criteria=[
        "summon_phase: int state var (0=idle, 1=dissolve, 2=portal, 3=reveal, 4=done)",
        "Phase 1: input text fades+translates up (0.3s)",
        "Phase 2: expanding circle glow from center (0.4s)",
        "Phase 3: creature card slides up from bottom (0.3s)",
        "SUMMON button disabled during all phases",
        "84/84 tests pass"
    ],
    subagent_context="Use CSS keyframe animations + state var timing. The prism cluster 1 "
                     "found that fadeIn keyframe is referenced but undefined — fix that too."
))

WBS.append(WBSTask(
    id="I07",
    title="Haptic feedback on all primary actions",
    description="Telegram WebApp supports HapticFeedback. No action currently triggers it. "
                "Add impactOccurred on SUMMON, FEED, PLAY, EVOLVE, MINT.",
    pillar=Pillar.P4_INFRA,
    priority=Priority.MEDIUM,
    category=Category.MISSING_UX,
    lens_nums=[57, 58, 53],
    files_to_modify=["terramon_tma/terramon_tma.py"],
    acceptance_criteria=[
        "SUMMON → haptic 'medium'",
        "FEED/PLAY/REST/TALK → haptic 'light'",
        "EVOLVE → haptic 'heavy'",
        "MINT → haptic 'rigid'",
        "Fallback: no crash if Telegram.WebApp unavailable",
        "84/84 tests pass"
    ],
    subagent_context="Use rx.call_script('Telegram.WebApp.HapticFeedback.impactOccurred(\"medium\")') "
                     "wrapped in try/except. The prism found this as missing UX."
))

WBS.append(WBSTask(
    id="I08",
    title="Evolution shimmer animation — visual payoff for evolving",
    description="EVOLVE button triggers stat change + message text but NO visual animation. "
                "Add: 1s gold shimmer overlay, scale 1.1x → 1.0x, emoji burst (★★★★), "
                "then show new evolution stage with glow upgrade.",
    pillar=Pillar.P1_AGENT,
    priority=Priority.MEDIUM,
    category=Category.MISSING_UX,
    lens_nums=[58, 57, 63],
    files_to_modify=["terramon_tma/terramon_tma.py"],
    acceptance_criteria=[
        "Evolve triggers gold shimmer CSS animation (1s)",
        "Creature card scales to 1.1x then back to 1.0x",
        "Emoji burst: ★★★★ appears and fades",
        "Evolution stage badge updates with new color",
        "84/84 tests pass"
    ],
    subagent_context="Use @keyframes already available or add new ones. The prism cluster 1 "
                     "found fadeIn is undefined — define it and evolutionShimmer."
))

WBS.append(WBSTask(
    id="I09",
    title="Summon streak counter — escalation loop",
    description="No reward for returning. Add streak: consecutive days summoning → "
                "multiplier. Day 3: 1.5x XP. Day 7: 2x XP + increased rare chance. "
                "Display streak flame in header.",
    pillar=Pillar.P1_AGENT,
    priority=Priority.MEDIUM,
    category=Category.MISSING_UX,
    lens_nums=[61, 40, 49, 97],
    files_to_modify=["terramon/domain/progress.py",
                     "terramon_tma/terramon_tma.py"],
    acceptance_criteria=[
        "summon_streak: int counter in PlayerProgress",
        "Streak increments on daily summon, resets on missed day",
        "1.5x XP at streak≥3, 2x XP at streak≥7",
        "+5% rare probability at streak≥7",
        "Streak flame emoji displayed in TMA header",
        "84/84 tests pass"
    ],
    subagent_context="Check last_summon_date against today. Reset streak if >24h gap. "
                     "Multiplier applied in game_loop.take_turn() reward calc."
))

WBS.append(WBSTask(
    id="I10",
    title="Auto-care while away — terra caretaker system",
    description="Creatures decay when app is closed (48 tick cap = 2 days). "
                "Add passive auto-care: if creature was happy when player left, "
                "auto-grazing slows decay by 50%. Add '❄️ Stasis' button (24h cooldown).",
    pillar=Pillar.P1_AGENT,
    priority=Priority.NICE,
    category=Category.MISSING_UX,
    lens_nums=[61, 66, 39],
    files_to_modify=["terramon/domain/creature_agent.py",
                     "terramon_tma/terramon_tma.py"],
    acceptance_criteria=[
        "Auto-graze: if happiness≥70 at last_tick, decay rate halved",
        "Stasis: pause all decay for 24h, 7-day cooldown",
        "Player notified on return: 'Your creature was fine. It grazed.'",
        "84/84 tests pass"
    ],
    subagent_context="_apply_tick_decay() in TMA already computes ticks from elapsed hours. "
                     "Add auto-graze logic before the decay loop."
))

WBS.append(WBSTask(
    id="I11",
    title="Global creature map — all creatures on Earth",
    description="Show ALL creatures from ALL players on a world map. "
                "Each creature = dot at birth coordinates. Aggregated view: heatmap of "
                "where thoughts become creatures. Most creatures in Kraków? Tokyo? NYC?",
    pillar=Pillar.P3_MULTIPLAYER,
    priority=Priority.NICE,
    category=Category.PHILOSOPHICAL,
    lens_nums=[74, 86, 83, 69],
    files_to_modify=["terramon/adapters/nostr_publisher.py",
                     "terramon_tma/terramon_tma.py"],
    acceptance_criteria=[
        "Global map aggregates creature locations from Nostr relays",
        "Heatmap overlay shows creature density by region",
        "Tap region → see recent creatures from that area",
        "84/84 tests pass"
    ],
    subagent_context="Nostr relays = distributed database. Each creature MINT event includes "
                     "lat/lon. Aggregate by reading relay events. No central server needed."
))

WBS.append(WBSTask(
    id="I12",
    title="Release mechanic — creature goes into the wild",
    description="Player can RELEASE a fully evolved creature into the wild. "
                "It becomes a wild creature visible on the global map. "
                "Other players can encounter it. The original player gets a '★ Wild Tamer' badge.",
    pillar=Pillar.P3_MULTIPLAYER,
    priority=Priority.NICE,
    category=Category.PHILOSOPHICAL,
    lens_nums=[97, 68, 75, 88],
    files_to_modify=["terramon/domain/creature_agent.py",
                     "terramon_tma/terramon_tma.py",
                     "terramon/adapters/nostr_publisher.py"],
    acceptance_criteria=[
        "ReleaseCreature event published to Nostr",
        "Creature removed from player's terra (read-only memorial)",
        "Wild creature visible on global map",
        "Other players can 'encounter' it (view card, bond gesture)",
        "Original player gets '★ Wild Tamer' badge",
        "84/84 tests pass"
    ],
    subagent_context="This completes the Hero's Journey: summon → bond → evolve → release. "
                     "The creature achieves independence. Most emotional moment in the game."
))

WBS.append(WBSTask(
    id="I13",
    title="Per-archetype evolution requirements — different paths for different creatures",
    description="Currently all archetypes evolve at Lv10/❤️70/XP500. Hero should evolve "
                "faster (Lv7) but need higher happiness (❤️85). Sage needs level 15 but "
                "only ❤️50. Orphan needs all 3 conditions EXACTLY balanced.",
    pillar=Pillar.P1_AGENT,
    priority=Priority.MEDIUM,
    category=Category.HARDCODED,
    lens_nums=[77, 31, 44, 81],
    files_to_modify=["terramon/domain/creature_agent.py"],
    acceptance_criteria=[
        "EvolutionRequirement per archetype in _ARCHETYPE_EVOLUTION dict",
        "Hero: min_level=7, min_happiness=85",
        "Sage: min_level=15, min_happiness=50",
        "Orphan: min_level=10, min_happiness=70, min_xp=600",
        "Default: current requirements (backward compat)",
        "84/84 tests pass"
    ],
    subagent_context="CreatureAgent.evolution_requirement is instance-level. Move to "
                     "class-level per archetype. The can_evolve property uses it."
))

WBS.append(WBSTask(
    id="I14",
    title="Stat bar numeric overlays — see exact values",
    description="Stat bars show width only, no numeric value. Player must guess "
                "hunger=42 vs hunger=58 from bar width. Add number on or next to bar.",
    pillar=Pillar.P4_INFRA,
    priority=Priority.NICE,
    category=Category.MISSING_UX,
    lens_nums=[55, 56, 57],
    files_to_modify=["terramon_tma/terramon_tma.py"],
    acceptance_criteria=[
        "Each stat bar shows '🍽️ Hunger: 67/100' or overlay number",
        "Number updates with transition (same 0.3s as bar width)",
        "No layout shift when number changes length",
        "84/84 tests pass"
    ],
    subagent_context="Add rx.text with the state var inside or after the bar. "
                     "Lens #55-C found this as missing UX."
))

WBS.append(WBSTask(
    id="I15",
    title="Safe area insets for modern phones",
    description="The TMA has no safe-area-inset padding. Bottom nav buttons may be "
                "hidden behind system navigation bar on iPhones/Android. "
                "Add env(safe-area-inset-bottom) and env(safe-area-inset-top).",
    pillar=Pillar.P4_INFRA,
    priority=Priority.NICE,
    category=Category.MISSING_UX,
    lens_nums=[54, 55, 53],
    files_to_modify=["terramon_tma/terramon_tma.py"],
    acceptance_criteria=[
        "Outer container has padding_bottom='env(safe-area-inset-bottom)'",
        "padding_top='env(safe-area-inset-top)' for Dynamic Island",
        "No visual regression on desktop/non-notched devices",
        "84/84 tests pass"
    ],
    subagent_context="CSS env() variables. Lens #54-D found this. Apply to the main "
                     "container style. Reflex supports env() through style props."
))

WBS.append(WBSTask(
    id="I16",
    title="color_schema typo fix — silent broken styling",
    description="Line 1713: color_schema='gray' — typo for color_scheme. "
                "Reflex silently ignores unknown props, so the text input has no theme.",
    pillar=Pillar.P4_INFRA,
    priority=Priority.NICE,
    category=Category.BUG,
    lens_nums=[47, 55],
    files_to_modify=["terramon_tma/terramon_tma.py"],
    acceptance_criteria=[
        "color_schema → color_scheme",
        "Input field has correct dark theme styling",
        "84/84 tests pass"
    ],
    subagent_context="Simple one-line fix. Lens #47-D found it."
))


# ═══════════════════════════════════════════════════════════════════════
# ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════

def tasks_by_priority() -> list[WBSTask]:
    """Return tasks sorted by priority (CRITICAL → HIGH → MEDIUM → NICE)."""
    order = {Priority.CRITICAL: 0, Priority.HIGH: 1, Priority.MEDIUM: 2, Priority.NICE: 3}
    return sorted(WBS, key=lambda t: (order[t.priority], t.id))


def tasks_by_pillar() -> dict[Pillar, list[WBSTask]]:
    """Group tasks by pillar."""
    groups: dict[Pillar, list[WBSTask]] = {}
    for t in WBS:
        groups.setdefault(t.pillar, []).append(t)
    return groups


def print_wbs():
    """Print full WBS as a tree."""
    for p in [Priority.CRITICAL, Priority.HIGH, Priority.MEDIUM, Priority.NICE]:
        pts = [t for t in WBS if t.priority == p]
        if not pts:
            continue
        print(f"\n{'='*60}")
        print(f"  {p.value} {p.name} ({len(pts)} tasks)")
        print(f"{'='*60}")
        for t in pts:
            deps = f" ← {','.join(t.depends_on)}" if t.depends_on else ""
            print(f"  {t.priority.value} {t.id}: {t.title}{deps}")
            print(f"     {t.pillar.value} | {t.category.value} | {t.estimated_complexity}")
            print(f"     Lens: {', '.join(f'#{n}' for n in t.lens_nums)}")
            for a in t.acceptance_criteria[:2]:
                print(f"     ✅ {a}")
    print(f"\n{'='*60}")
    print(f"  TOTAL: {len(WBS)} tasks")
    print(f"  {Priority.CRITICAL.value} CRITICAL: {len([t for t in WBS if t.priority==Priority.CRITICAL])}")
    print(f"  {Priority.HIGH.value} HIGH:     {len([t for t in WBS if t.priority==Priority.HIGH])}")
    print(f"  {Priority.MEDIUM.value} MEDIUM:   {len([t for t in WBS if t.priority==Priority.MEDIUM])}")
    print(f"  {Priority.NICE.value} NICE:     {len([t for t in WBS if t.priority==Priority.NICE])}")


def next_tasks(completed: list[str]) -> list[WBSTask]:
    """Return tasks whose dependencies are all satisfied."""
    done = set(completed)
    ready = []
    for t in WBS:
        if t.id in done:
            continue
        if all(d in done for d in t.depends_on):
            ready.append(t)
    return sorted(ready, key=lambda t: t.id)


if __name__ == "__main__":
    print_wbs()
    print("\n\nNext dispatchable tasks: (none completed)")
    for t in next_tasks([]):
        print(f"  {t.priority.value} {t.id}: {t.title}")
