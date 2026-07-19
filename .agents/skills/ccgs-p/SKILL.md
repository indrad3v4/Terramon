---
name: ccgs-p
description: Terramon Game Studio orchestrator — coordinates 49 CCGS agent roles (designer, programmer, artist, qa...) for building games, with every design/UX decision EXTENDED by the prism skill (Schell's 100 Lenses) as a lens layer on top of built-in CCGS reviews. Use `/ccgs-p` to orchestrate a game-dev task for Terramon via subagents. Example `/ccgs-p design a new creature archetype for Terramon`.
---

# /ccgs-p — Terramon Game Studio (orchestrator)

`ccgs-p` is an **orchestrator of subagents**: it coordinates the 49 CCGS agent
roles (`.agents/skills/ccgs-p/.claude/agents/`) to build games, and extends every
design/UX review with the **prism skill** (Schell's 100 Lenses) on top of CCGS's
built-in checks. **Terramon is the first game built with this studio.**

## How the orchestrator works (protocol)

When the user invokes `/ccgs-p <task>` for Terramon:

1. **Decompose** the task into agent roles that own each piece
   (game-designer for loops, ux-designer for screens, art-director for visuals,
   lead-programmer for Reflex/Python, economy-designer for Stars/Lightning…).
2. **Dispatch** each role as a **subagent** (`delegate_task`):
   - Pass the role's prompt from `.agents/skills/ccgs-p/.claude/agents/<role>.md`
     as context, plus the Terramon task.
   - Roles that own design/UX/art/narrative carry `skills: [prism]` (or
     `[... , prism]`) — they MUST run a prism lens pass.
3. **Review layer (prism EXTENDS CCGS)**:
   - For any design/UX/creative output, the orchestrator (or the role subagent)
     spawns **prism subagents** — one per relevant Schell Lens — each grounded
     in the book via RAG. Report: "CCGS: <verdict>. prism: Lens #N (<name>): <verdict>."
   - prism ADDS a lens layer; it does NOT replace CCGS built-in review skills.
4. **Synthesize**: merge role outputs into one Terramon-facing result, keeping
   the agentic-loop + memory constraints from `ccgs-p/CLAUDE.md`.

## Example invocation

```
/ccgs-p design a new creature archetype for Terramon

→ orchestrator decomposes:
   - game-designer: core loop fit, rarity, summon mechanic
   - narrative-director: creature lore, "meet don't control"
   - art-director: FAL prompt from archetype + rarity
   - economy-designer: Stars price, sink/faucet
→ each role runs as subagent; design roles run prism (Lens #23 Endogenous Value,
  #47 Problem Solving, #65 Story, #74 World, #98 Unification)
→ result: a creature spec ready for terramon/application/game_loop.py
```

## What's installed

At `.agents/skills/ccgs-p/`:
- **49 agents** in `.claude/agents/` (game-designer, systems-designer, ux-designer,
  art-director, creative-director, narrative-director, economy-designer,
  level-designer, writer, world-builder, leads, programmers, qa, devops, community…)
- 73 skills in `.claude/skills/` (design-review, code-review, art-bible, ux-review…)
- 12 hooks, 11 rules in `.claude/`
- `CLAUDE.md` — Terramon studio architecture (Reflex/Python, agentic loop, FAL, Stars/Lightning)

## Role roster (selected)

- **creative-director** — vision, tone
- **game-designer** — core loops, GDDs (`[design-review, balance-check, brainstorm, prism]`)
- **systems-designer** — progression, agent systems (`[prism]`)
- **ux-designer** — player experience (`[prism]`)
- **art-director** — visual style (`[prism]` + FAL)
- **narrative-director** — lore, creature stories (`[prism]`)
- **economy-designer** — Stars/Lightning sink-faucet (`[prism]`)
- **lead-programmer** — Python/Reflex architecture
- **gameplay-programmer** — `game_loop.py` integration
- **devops-engineer** — Railway deploy
- **community-manager** — TMA/Nostr growth

Engine specialists (godot/unity/unreal) are present but flagged **Not For Terramon**
(Terramon uses Reflex/Python).

## Terramon constraints (from CLAUDE.md)

- Creatures = AGENTS with memory (`terramon/adapters/json_memory.py`), not labels
- Rarity MUST be visually real via `terramon/adapters/fal_art_generator.py` (FAL)
- Core loop = `terramon/application/game_loop.py` ACT→OBSERVE→REWARD→REFLECT
- Monetization: Telegram Stars (mass TMA) + Lightning/zaps (Nostr native)

## How to use

1. Invoke `/ccgs-p <task>` — the orchestrator decomposes and dispatches subagents.
2. Read a role: `read_file(".agents/skills/ccgs-p/.claude/agents/<name>.md")`
3. Read studio arch: `read_file(".agents/skills/ccgs-p/CLAUDE.md")`
4. For design review, the role (or orchestrator) invokes `prism` (Schell 100 Lenses).
5. Adapt outputs to Python/Reflex for Terramon.
