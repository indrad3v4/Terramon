# PRISM Analysis: Narrative & Emotion Lens Cluster (9 Lenses)

**Applied to:** Terramon (`/root/Terramon/terramon/`)
**Date:** 2026-07-28
**Files analyzed:** `creature_agent.py`, `llm_behavior.py`, `insight.py`, `k3_insight_engine.py`, `agent_service.py`, `progress.py`

---

## 🔷 Lens #65 — Story Machine

> *"Does the game's engine itself generate stories? Is every playthrough unique?"*

### Finding: STATIC_INSIGHT (file:line)
**`k3_insight_engine.py:445-515`** — `extract_insight()` produces a **static Insight** at summon time. The creature's `driver`, `barrier`, and `therefore` are set once and **never re-evaluated**. The creature says the same `therefore` response every `talk()` interaction, regardless of how the player has changed or what journey they've been on.
**`creature_agent.py:212`** — `insight: Optional[Insight] = None` — a field set at construction, never mutated.
**`creature_agent.py:361-365`** — `talk()` returns `self.insight.therefore` verbatim every time. No variation, no evolution.

### Fix
- Add `re_evaluate_insight()` to `CreatureAgent` that updates the Insight's `therefore` based on accumulated interaction history.
- Call it at evolution boundaries so each evolution stage has a unique narrative voice.

---

## 🔷 Lens #68 — Hero's Journey

> *"Does the player's journey follow a narrative arc: call → trials → transformation → return?"*

### Finding: NO_JOURNEY_ARC (file:line)
**`creature_agent.py:250-259`** — `can_evolve` is a pure logistic probability check. There is **no quest, ordeal, or trial** required for evolution. The player just... waits for stats to cross a threshold.
**`progress.py:89-139`** — `PlayerProgress` tracks XP and collection count but has **no narrative phase** (no "call," "threshold," "transformation," "return").
**`agent_service.py:27-46`** — `create_agent()` — summon has no special "call to adventure" framing. It's just a mechanical creation.

### Fix
- Add journey phase tracking to `PlayerProgress` (Call → Threshold → Transformation → Return).
- Evolution should require a quest-like condition (not just stat check).
- Each phase changes how the creature speaks and what the player sees.

---

## 🔷 Lens #70 — Story

> *"Is the story embedded in the mechanics or pasted on top?"*

### Finding: PASTED_STORY (file:line)
**`creature_agent.py:373-479`** — `_apply_tick()` — stat decay is **pure math** (EMA × gradient clipping × state gates). Zero narrative framing. The creature's stats decline without any in-world reason.
**`creature_agent.py:575-645`** — `_check_urgent_needs()` — need messages are generic ("A soft rumble. It's hungry."). They don't tie into the creature's archetype, the terra world, or the player's journey.
**`llm_behavior.py:291-321`** — The system prompt tells the LLM "You are NOT an AI assistant" and "Never break character" — but the **mechanics below** (stat decay, evolution trigger, interaction deltas) tell a completely different story (a machine with numeric state, not a living thought-form).

### Fix
- Add narrative-flavored stat decay messages that change based on archetype, state, and journey phase.
- The `tick` system should emit world-narrative events ("The terra wind scatters your thought-energy" for an Explorer; "A shadow passes over the terra" for a Rebel).

---

## 🔷 Lens #73 — Collusion

> *"Does the game collude with the player against its own limitations?"*

### Finding: ANTAGONISTIC_DECAY (file:line)
**`creature_agent.py:406-408`** — EMA decay (`* 0.97`) runs every tick regardless of player presence. The creature's stats **always decline**. No grace period for absent players.
**`creature_agent.py:599-603`** — Dormancy (`dormant_ticks >= 24`) is framed as punishment ("Its light is fading..."). No story justification like "the creature is dreaming of you" or "the terra is conserving energy."
**`progress.py:89-139`** — No "compassion mechanics" — nothing that rewards the player for care rather than punishing neglect.

### Fix
- Add a "rested grace" mechanic: when player hasn't interacted for >4 ticks, decay rate halves (the creature sustains itself on ambient terra energy).
- Add absence-greeting: when player returns after N ticks without interaction, creature greets them with a story about what it "dreamed."
- Remove the threatening dormancy language; replace with melancholic/sympathetic framing.

---

## 🔷 Lens #75 — Avatar

> *"Is the creature the player's avatar? Does it represent them in the game world?"*

### Finding: NO_AVATAR_AGENCY (file:line)
**`creature_agent.py:208-212`** — `archetype` and `insight` are immutable after creation. The player cannot shape or influence their avatar's personality after summon.
**`creature_agent.py:361-365`** — `talk()` uses `self.insight.therefore` — a static phrase. The avatar doesn't grow in self-understanding or change how it represents the player.
**`agent_service.py:66-95`** — `to_dict()` — no `player_affinity`, no `personality_shifts`, no avatar evolution data sent to UI.

### Fix
- Add `player_affinity` field to `CreatureAgent` — tracks which archetype behaviors the player has reinforced.
- When a player talks to a Sage creature repeatedly, the creature's dialogue should gain more Sage nuance over time.
- Add `avatar_growth` representation to `to_dict()`.

---

## 🔷 Lens #84 — Friendship

> *"Does the game foster a genuine sense of friendship between player and creature?"*

### Finding: NO_MEMORY (file:line)
**`creature_agent.py:233`** — `message_history` stores ALL messages but is only used for the KV-cache window (last 6).
**`llm_behavior.py:205-265`** — `_build_attention_context()` — Channel C (History) only shows the KV-cache window. No "memory fragments" — the creature never recalls specific past moments.
**`creature_agent.py:361-368`** — `talk()` — when there's no insight, the response is always "The quiet between you says enough." No variation based on history.
**`creature_agent.py:268-296`** — `feed()` texts reference level and interaction count but never reference **specific shared experiences**.

### Fix
- Add `milestone_memory` list that stores notable shared events (first evolution, 10th interaction, etc.).
- Inject memory fragments into the LLM prompt so the creature can reference specific past moments.
- Add relationship milestones (100th interaction → special dialogue).

---

## 🔷 Lens #85 — Expression

> *"Does the game let the player express who they are?"*

### Finding: ONE_SHOT_EXPRESSION (file:line)
**`k3_insight_engine.py:445-515`** — `extract_insight()` — the player's ONLY self-expression is the initial thought seed at summon. After that: feed/play/rest/talk — generic actions.
**`creature_agent.py:208-215`** — No player journal, no custom naming (name is auto-generated), no personalization fields.
**`progress.py:89-139`** — `PlayerProgress` has no journal, no player-defined goal, no way to express personal values.

### Fix
- Add `player_journal` to `CreatureAgent` — a free-form text the player can write that influences the LLM prompt.
- Add custom naming support (rename creature).
- Add per-creature "notes" field for the player.

---

## 🔷 Lens #86 — Community

> *"Does the game support community or a shared world?"*

### Finding: NO_COMMUNITY (file:line)
**`events/agent_summoned.py:1-25`** — Event exists but has no player-sharing payload. No creature trading, battling, or visiting.
**`progress.py:58-70`** — `CREATURE_RESONANCES` are defined but only work within a **single player's collection**. No cross-player resonance.
**`agent_service.py:95`** — No `share_code`, no `public_profile`, no community hooks.
**`creature_agent.py:680`** — No community fields whatsoever. Single-player only.

### Fix
- Add `share_code` to `CreatureAgent` (a unique code players can share).
- Add visitor-ready read-only creature data for future community features.
- Seed the event payload with shareable fields.

---

## 🔷 Lens #88 — Love

> *"Does the game create conditions for the player to love it (and its characters)?"*

### Finding: ONE_SIDED_CARE (file:line)
**`creature_agent.py:268-296`** — `feed()` — the creature accepts but never gives back. Love requires reciprocity.
**`creature_agent.py:529-548`** — `evolve()` — evolution is framed as a mechanical transformation, not a **gift of trust** from the creature.
**`creature_agent.py:575-645`** — `_check_urgent_needs()` — all messages are requests for care. None express gratitude or spontaneous affection.
**`creature_agent.py:621-643`** — Ambient messages are generic ("It gazes at the horizon.") — never say "I'm glad you're here" or reference the bond.

### Fix
- Add a "gift" system: at relationship milestones, the creature offers a unique phrase or insight.
- Add reciprocal messages: spontaneous gratitude that references the bond strength.
- Add a `bond_level` field that grows from cumulative interaction and unlocks special behaviors.

---

## Summary Table

| Lens | Issue | Severity | File:Line |
|------|-------|----------|-----------|
| #65 Story Machine | Static insight never re-evaluated | 🔴 | `k3_insight_engine.py:445`, `creature_agent.py:361` |
| #68 Hero's Journey | No narrative arc or quests | 🔴 | `progress.py:89`, `creature_agent.py:250` |
| #70 Story | Mechanics contradict narrative | 🟡 | `creature_agent.py:373` |
| #73 Collusion | Adversarial decay, no grace | 🟡 | `creature_agent.py:406`, `l.599` |
| #75 Avatar | No player agency over avatar | 🔴 | `creature_agent.py:208`, `l.361` |
| #84 Friendship | No memory of shared experiences | 🟡 | `creature_agent.py:233`, `llm_behavior.py:205` |
| #85 Expression | One-shot expression, then silence | 🟡 | `creature_agent.py:208` |
| #86 Community | Fully missing | 🔴 | (entire codebase) |
| #88 Love | One-sided care, no reciprocity | 🟡 | `creature_agent.py:268`, `l.575` |

---

## File-by-file fix plan

1. **`creature_agent.py`** — 6 fixes: insight re-eval, journey phase, narrative decay, grace period, affinity, memory, gifts
2. **`k3_insight_engine.py`** — fix #65: add insight re-evaluation pathway  
3. **`llm_behavior.py`** — fix #84/#70: inject memories into prompt context
4. **`agent_service.py`** — fix #75/#86: avatar growth + community fields
5. **`progress.py`** — fix #68: journey phase tracking
6. **`events/agent_summoned.py`** — fix #86: community payload
