---
name: ccgs-p
description: Terramon Game Studio — CCGS agent roster (49 roles) adapted for Terramon (Reflex/Python TMA). Lens-based game design via the prism skill (Schell's 100 Lenses) replaces CCGS review skills. Use `/ccgs-p` to design agent architecture, world systems, mechanics, or procedural generation for Terramon.
---

# /ccgs-p — Terramon Game Studio (adapted CCGS)

49 specialised game-dev agents, adapted for **Terramon** (Python + Reflex TMA on Railway).
Source: https://github.com/Donchitos/Claude-Code-Game-Studios

## Key adaptation: prism, not CCGS reviews

Every game-design / UX / creative review goes through the **prism skill**
(Jesse Schell's 100 Lenses, RAG over *The Art of Game Design*). prism **EXTENDS**
the built-in CCGS review skills (design-review, ux-review, art-bible, balance-check)
— it adds a lens layer on top, not a replacement. Design/UX/art/narrative agents list `skills: [prism]`.

## What's installed

Cloned at `.agents/skills/ccgs-p/`:
- **49 agents** in `.claude/agents/` (game-designer, systems-designer, ux-designer, art-director, creative-director, narrative-director, economy-designer, level-designer, writer, world-builder, leads, programmers, engine specialists, qa, devops, community…)
- Hooks + rules under `.claude/`
- `CLAUDE.md` — Terramon-specific studio architecture (Reflex/Python, agentic loop, FAL art, Stars/Lightning)

## Example usage

```
/ccgs-p for Terramon

→ loads the 49-agent roster adapted to Terramon.
  Design a new creature archetype:
    invoke game-designer → it reviews via prism (Lens #23 Endogenous Value,
    #47 Problem Solving, #65 Story) instead of CCGS design-review.
  Build the TMA screen:
    invoke ui-programmer + ux-designer → lens review via prism.
  Engine specialists (godot/unity/unreal) are marked "Not For Terramon"
  (we use Reflex/Python).
```

## Agent roster (selected)

- **creative-director** — vision, tone
- **game-designer** — core loops, GDDs (uses prism)
- **systems-designer** — progression, agent systems (uses prism)
- **ux-designer** — player experience (uses prism)
- **art-director** — visual style (uses prism + FAL)
- **narrative-director** — lore, creatures' stories (uses prism)
- **economy-designer** — Stars/Lightning sink-faucet (uses prism)
- **lead-programmer** — Python/Reflex architecture
- **gameplay-programmer** — game_loop.py integration
- **devops-engineer** — Railway deploy
- **community-manager** — TMA/Nostr growth

Engine specialists (godot/unity/unreal) are present but flagged Not For Terramon.

## How to use

1. `read_file(".agents/skills/ccgs-p/.claude/agents/<name>.md")` — read an agent
2. `read_file(".agents/skills/ccgs-p/CLAUDE.md")` — studio architecture
3. When the agent needs a design review, it invokes `prism` (100 Schell lenses)
4. Adapt patterns to Python/Reflex for Terramon

## Terramon constraints (from CLAUDE.md)

- Creatures = AGENTS with memory (`json_memory.py`), not labels
- Rarity MUST be visually real via `fal_art_generator` (FAL)
- Core loop = `game_loop.py` ACT→OBSERVE→REWARD→REFLECT
- Monetization: Telegram Stars (mass) + Lightning/zaps (Nostr)
