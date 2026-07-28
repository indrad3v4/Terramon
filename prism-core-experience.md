# PRISM Analysis: Core Experience Lens Cluster

**Subject:** Terramon TMA (Telegram Mini App) — thought-to-creature summoning game
**Date:** 2026-07-28
**Lenses:** #1 Essential Experience, #3 Fun, #4 Curiosity, #7 Elemental Tetrad, #9 Unification, #17 Pleasure, #18 Flow, #19 Needs, #21 Functional Space, #22 Dynamic State

---

## 🔷 Lens #1: Essential Experience
**Core question:** Is the essential experience clear? What one sentence describes what the player should feel?

**Finding:** **No single crafted essential experience exists.** The file header (line 1-28) lists 12 UI/UX "sins fixed" but no paragraph describing the *feeling* the player should have. The tutorial overlay (lines 1264-1343) lists 4 steps (type → summon → care → evolve), but these are *features* not *experience*. The demo creature text (line 1232) says "Something stirs in the void..." — evocative but not an essential experience statement.

**Evidence:**
- `terramon_tma.py:1505-1508` — index docstring: "GameBoy-style single-screen TMA... Three zones" — describes layout, not experience
- `terramon_tma.py:1240` — "Type a thought. Meet what emerges." — close, but not carried through the loop
- `tutorial_overlay():1273` — "Your thoughts become creatures on real planet Earth." — says what happens, not how it feels

**The result:** The game tries to be a journal, a pet sim, a personality test, and a collect-a-thon simultaneously. Each turn does too much (summon + rarity + XP + insight + geo + portrait + LLM + Bayesian + safety + BPE stats + scout), diluting the core.

**Fix:** Define the essential experience: **"Your thoughts become creatures. They live on Earth. They remember you."** Strip everything that doesn't serve this.

---

## 🔷 Lens #3: Fun (4 kinds)
**Core question:** What kind of fun does this game offer? (challenge, fantasy, discovery, fellowship, expression)

**Finding:** **Care interactions are isomorphic.** Feed/Play/Rest/Talk all do the same thing: click button → stat changes + one of 5 canned response texts. `creature_agent.py:240-246` (feed), `248-265` (play), `268-279` (rest), `282-296` (talk) — each has ~4 choice() texts, no strategic depth, no consequence for order, no resource management.

**Evidence:**
- `creature_agent.py:240-245` — feed: 4 responses, all interchangeable
- `creature_agent.py:260-265` — play: 4 responses, all interchangeable
- `creature_agent.py:275-279` — rest: 4 responses, all interchangeable
- `agent_service.py` — each wraps CreatureAgent methods directly, no strategy layer

**Key insight from Schell:** "The fun of mastery comes from the *discovery of strategy*, not from the action itself." The game has no strategy to discover — Feed always gives +25 hunger +5 energy +3 XP, regardless of state.

**Fix:** Add interaction consequence chains: feeding when happy gives bonus XP, playing when tired is less effective, rest stacking reduces hunger faster. Introduce a *choice that matters*.

---

## 🔷 Lens #4: Curiosity
**Core question:** Does the game make the player want to know what happens next?

**Finding:** **Curiosity collapses after 5-12 summons.** The only unknown is "what archetype will I get?" — after seeing all 12, there's nothing hidden. No secret creatures triggered by specific thought patterns. No cross-creature interactions. No creatures that only appear at night/dawn/after evolution.

**Evidence:**
- `progress.py:55` — `goal_distinct = 3`, hardcoded to 5 in TMA (line 161). After 5 distinct creatures, game "ends" (goal_reached = True) with no post-game
- `creature_agent.py:546-571` — archetype verb/feeling/sound maps are static, same for every creature of that archetype forever
- No search results for "rare", "secret", "hidden", "special", "event" in summon logic

**Fix:** Add meta-progression: once all 12 archetypes collected, unlock "echo" mode where thought patterns can summon hybrid creatures.

---

## 🔷 Lens #7: Elemental Tetrad
**Core question:** Do Mechanics, Story, Aesthetics, and Technology harmonize?

**Mechanics ⭐⭐⭐½** — Summon/care/collect/evolve are solid. Tick decay, rarity tiers, XP curve all functional.

**Story ⭐½** — The lore is a single static sentence per archetype (lines 109-122). The "story" is "you typed a thing, a creature appeared." No narrative arc. No change over time. No relationship development.

**Aesthetics ⭐⭐⭐⭐** — Strong. Breathing shadow (line 1157-1261), rarity glow (103-108), gradient backgrounds (995), XP bar animation (764), celebration overlay (1451-1501). Visual language is cohesive and evocative.

**Technology ⭐⭐⭐** — Event-driven architecture, clean ports/adapters, Reflex 0.9.x for TMA. However, the TMA does ALL computation in one monolithic `summon()` event (lines 257-448) — BPE tokenizer, Bayesian classifier, LLM greeting, safety check, portrait gen, state recomputation — every summon pays the full tax.

**Harmony failure:** **The Story element is dramatically weaker than the other three.** A beautiful creature appears, makes one greeting, then its lore never changes — the "same" creature at level 1 vs level 50 has the same lore text.

**Fix:** Dynamic lore that evolves: `{archetype} at level {level} who has evolved {evolution_stage} times and been fed {feed_count} times.` Generate lore from state.

---

## 🔷 Lens #9: Unification
**Core question:** Does every element serve the essential experience, or are there elements that pull against it?

**Finding:** **Multiple features serve the developer, not the player.** The TMA exposes raw system diagnostics as gameplay:

| Feature | Line | What it tells the player | Essential? |
|---------|------|------------------------|------------|
| Scout button | 1726-1734 | Runs a background agent process | NO — dev tool |
| Token count display | 876-884 | Shows BPE tokenization stats | NO — debugging UI |
| Archetype probability bars | 886-912 | Shows Bayesian posterior distribution | NO — ML model internals |
| Intelligence % | 868-873 | Shows Bayesian confidence score | NO — not a game stat |
| Safety advisory | 954-963 | Flags content policy violations | NO — backend detail |
| Rarity odds | L36 stats | Shows P(common), P(rare), P(legendary) | NO — removes mystery |

Each of these pushes the player into "developer mode" — thinking about how the system works instead of the fantasy.

**Fix:** Hide all diagnostic information. Show only the creature, its stats, and its lore. Put dev features behind a debug flag.

---

## 🔷 Lens #17: Pleasure
**Core question:** What simple pleasures does the game offer?

**Finding:** **No escalating pleasures.** The pleasure arc is: summon 1 (ooh!) → summon 5 (nice variety) → summon 10 (seen it all) → goal reached (celebration) → ... nothing. After reaching Tamer status (5/5), the game has no new tier of pleasure to offer:

- `progress.py:55` — `goal_distinct=3` (default), TMA overrides to 5 (line 161)
- `terramon_tma.py:966-987` — goal celebration fires once, then `celebration_dismissed` = True (486), no permanent UI change except a ★ badge (1523)
- No post-goal content: no "collect 10/20/30", no legendary completionist goal, no new game+

**Fix:** Progressive goal tiers: Bronze (3), Silver (5), Gold (10), Platinum (all 12). Each tier changes the header badge and unlocks a visual flair.

---

## 🔷 Lens #18: Flow
**Core question:** Does the player experience the right balance of challenge and skill?

**Finding:** **Zero challenge = no flow possible.** There is no failure state in the game:

- `creature_agent.py:504-518` — even at <20 stats, creature just sends a "need" message — no consequences
- `creature_agent.py:406-416` — SICK state is cosmetic (accelerated decay) but creature can never die
- `creature_agent.py:248-253` — play with <20 energy returns a "too tired" message, but doesn't penalize you
- No skill check anywhere — care buttons always succeed, summon always produces a creature

Without a failure state, there's no tension, no relief, and no learning. The game is a toy, not a game.

**Fix:** Add a "wilted" state where a creature that stays at 0 stats for >24 ticks becomes dormant and must be reawakened with a special summon. Add a small time-attack bonus for responding quickly to need messages.

---

## 🔷 Lens #19: Needs
**Core question:** What psychological needs does this game satisfy?

**Finding:** **Relatedness is thin.** The creature talks back, but its responses never deepen. A level-50 creature that has been fed 200 times and evolved twice says the exact same things as one just summoned:

- `creature_agent.py:240-296` — feed/play/rest/talk use `random.choice()` over 4-5 static strings
- No response text ever references `self.level`, `self.interaction_count`, or past insights
- `llm_behavior.py` (line 301 reference) — LLM greeting is one-shot on summon, never called again for ongoing conversation

**Competence** is partially satisfied (progress bars, collection). **Autonomy** is strong (you choose what to type).

**Fix:** Make creature responses parametric: include `self.level`, `self.hunger` status, and `self.interaction_count` in response text generation.

---

## 🔷 Lens #21: Functional Space
**Core question:** Does the screen layout make sense? Is it easy to find what you need?

**Finding:** **Cognitive overload on a 400px screen.** The index page (lines 1505-1868) has 5+ information zones crammed into one viewport:

1. Header (Lv + Tamer badge)
2. Creature display (sigil, name, thought, lore, creature_greeting, place, memory_greeting)
3. XP bar
4. Input + 3 buttons (capture, summon, scout)
5. Scout result
6. Bottom nav (terra, care, map)
7. Tab content (terra grid / care panel / map)
8. Goal celebration overlay
9. Tutorial overlay (on first visit)

Plus conditional info: insight text (845-850), token stats (875-884), archetype bars (886-912), safety advisory (954-963), evolution hint (1102-1103).

**Evidence:** `terramon_tma.py:1505-1868` — the entire index() function is a single massive component with no meaningful grouping.

**Fix:** Collapse diagnostics into a single "stats" expandable. Remove token stats, archetype bars, intelligence %, and safety flag from the main view.

---

## 🔷 Lens #22: Dynamic State
**Core question:** Does the game state change in meaningful ways over time?

**Finding:** **The creature is effectively stateless across sessions.** Although stats decay via tick (creature_agent.py:301-399), the creature:
- Does not remember what you said to it last time
- Does not show its interaction history
- Does not change its personality based on how you treated it
- `_seed_to_card()` (line 689-704) — terra cards show only the original thought + archetype + rarity, not how the creature *was*
- `_MEMORY` stores ThoughtSeeds (raw_input + archetype + rarity), not CreatureAgent instances — the creature's evolving state is never persisted to terra

**Evidence:**
- `progress.py:50-54` — PlayerProgress has collection (set of archetype names) and xp — that's it. No creature-specific history.
- `summon_service.py:58-70` — ThoughtSeed stores raw_input, archetype, rarity, paid — no stat snapshot
- `terramon_tma.py:689-704` — terra card shows archetype + rarity + thought, no level, no stats, no evolution stage

**Fix:** Persist a lightweight CreatureSnapshot (archetype, level, evolution_stage, max stats achieved) with each seed so the terra shows how that creature progressed.
