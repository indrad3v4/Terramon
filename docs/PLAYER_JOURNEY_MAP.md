# Terramon — Player Journey Map (final)

Synthesis of `/ccgs-p` orchestration (game-designer + ux-designer +
creative/narrative-director, each EXTENDED by `prism` — Schell's 100 Lenses)
and the `ai-engineering-loop` method (player journey = feedback loop; needs
eval metrics). Plus two product truths from the founder:

1. **Entrance must be effortless** — like taking a photo (the founder's own
   Kraków rainy-day shot under a bike shelter). A thought can BEGIN as a photo.
2. **Behind every thought lives an INSIGHT** — and that insight is what drives
   the agent. Model from `docs/dvizhok/phase1-strategy.md` §3 INSIGHT ENGINE:
   `DRIVER + BARRIER → THEREFORE`. The surface text is a symptom; the insight
   is the hidden behavioral mechanism that moves the creature.

---

## Verdict (ccgs-p)

**CCGS:** Technically playable, but plays like a *vending machine*, not a game.
All three roles converged: no challenge, invisible goals, flat world.
**prism (Schell):** every named lens = **FAIL**.

## Journey Map (intro → outro)

| Stage | Player sees | Gap | prism verdict |
|-------|-------------|-----|---------------|
| **S0 First open** | `TERRAMON` + `0 creatures live here` + `Empty terra. Summon your first thought.` | Dead-end onboarding; no tutorial, no "why" | #74 World FAIL (no gateway from reality); #8 Tetrad FAIL (story/mechanics weak) |
| **S1 First summon** | Creature card (sigil/rarity/agent/quote/lore/reflection/XP) | No celebration, no animation/sound | #34 Sensation FAIL; #57/#58 Feedback/Juiciness FAIL |
| **S2 Repeat** | `distinct N/5` + `Lv.` creep | Progress buried under card; SUMMON always succeeds — no agency | #25 Goals FAIL; #47 Problem Solving FAIL |
| **S3 MINT** | `⚡ MINT · 15/25 sats` (rare/legendary only) | No explanation of mint; no receipt | #98 Unification FAIL (monetization detached from play) |
| **S4 Goal (5)** | `✸ GOAL REACHED — you are a Tamer!` → nothing | One bold line; no outro loop | #65 Story Machine FAIL (vending, not story); flat interest curve |
| **S5 Return** | `load_terra` restores collection | No "welcome back / Lv.X"; no bond | #64 Projection/Imaginary Friend FAIL (transactional, not relational) |

## The 3 fixes (priority order)

### FIX 1 — Effortless, insight-bearing ENTRANCE (S0)
- Entry = **photo-first**. Camera/SIMPLIFIED: tap a photo (like the founder's
  Kraków shot) → the app extracts a *thought seed* from it (caption / what the
  player felt) → that becomes the summon input. Text stays as fallback.
- Empty state reframed from VOID to HOOK: instead of `Empty terra. Summon your
  first thought.` → `Your world is quiet. Show me what you see — and who you are
  when you see it.` (invitation, not void).
- Rationale: photo is the lowest-friction "thought" (Lens #34 Sensation, #8 Tetrad).

### FIX 2 — INSIGHT drives the agent (core loop rewire)
- Every summon runs the **INSIGHT ENGINE**: `DRIVER + BARRIER → THEREFORE`.
  - `DRIVER` = what the player wants (extracted from text/photo caption).
  - `BARRIER` = what blocks it (keyword/embedding signal: money, fear, alone…).
  - `THEREFORE` = the creature's *behavior directive* — this is what the agent
    actually does, not the rarity label.
- The creature card shows the INSIGHT, not just lore: "Scout senses you're
  afraid of tomorrow. It waits by the door." (meet, don't control).
- Reflection evolves as memory grows (json_memory): the creature *knows* the
  player's recurring insight pattern.
- This closes the roast's "vending machine" charge: the agent is now driven by
  a derived psychological mechanism, not a keyword→archetype map.

### FIX 3 — Visible progression + real outro (S2/S4)
- Always-visible `X/5 to Tamer` + XP bar (not hidden until goal).
- Named unlock at goal: "Tamer" opens **terra map mode** — creatures anchored to
  *where the thought was summoned* (geo/photo context), so `terra` = a map of
  *places-you-thought* (Lens #74 World integrity restored).
- Outro = evolving ambient story, not one bold line. Return visit shows
  `Welcome back, Lv.X — your terra grew while you were away.`

## ai-engineering-loop metrics (eval-driven)
The journey is a feedback loop; instrument it:
- `first-summon → second-summon rate` (does the hook retain?)
- `goal-reached rate` (is the goal legible / reachable?)
- `D1 retention` (does the player return?)
- `insight-extraction accuracy` (does the DRIVER/BARRIER→THEREFORE match what
  the player meant? — human-rated sample, 50 examples)

Iterate on the worst dimension. The loop surfaces the next failure mode; report
it, don't hide it.

## Status
- Diagnosis: DONE (ccgs-p + prism + ai-engineering-loop).
- Implementation: PENDING (FIX 1–3 above). Next: dispatch implementation
  subagents per ccgs-p protocol, verify with `reflex export` + pytest.
- Source reviewed: `terramon_tma/terramon_tma.py`, `terramon/application/game_loop.py`,
  `terramon/adapters/json_memory.py`, `docs/dvizhok/phase1-strategy.md`.
