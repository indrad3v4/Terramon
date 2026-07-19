# Terramon — Game Studio Agent Architecture (adapted from CCGS)

Indie game development for **Terramon** managed through coordinated subagents.
Each agent owns a specific domain, enforcing separation of concerns and quality.

## What Terramon Is

- **Concept**: A Telegram Mini App (TMA) + PWA where a player's *thought* becomes
  a creature (an agent) that lives in their `terra` (personal world map).
- **Real product**: deployable via Reflex (Python) on Railway. Already live at
  `https://terramon-tma-production.up.railway.app/`.
- **Agentic core**: `terramon/application/game_loop.py` (ACT→OBSERVE→REWARD→REFLECT),
  `terramon/adapters/json_memory.py` (stateful memory), `terramon/domain/progress.py`
  (terra growth). Creatures are NOT labels — they are agents with memory.
- **Art**: `terramon/adapters/fal_art_generator.py` (FAL flux/schnell, $0.003/img).

## Technology Stack

- **Engine**: Reflex 0.9.x (Python → React SPA). No Godot/Unity/Unreal.
- **Language**: Python 3.13 (backend + game logic), Reflex frontend components.
- **Deploy**: Railway (Dockerfile). TMA via BotFather `@terrramonBot` / `terramon`.
- **Art**: FAL.ai (text-to-image). Monetization: Telegram Stars + Lightning (Nostr zaps).

## LENS-BASED DESIGN (prism EXTENDS built-in reviews)

**Every game-design / UX / creative decision is reviewed through the
`prism` skill** — Jesse Schell's 100 Lenses from *The Art of Game Design*,
loaded as subagent "prisms" via RAG over the book corpus.

- prism **EXTENDS** the built-in CCGS review skills (design-review, ux-review,
  art-bible, balance-check), it does NOT replace them. Run the CCGS check, then
  the prism lens pass.
- When a role would normally "run a design review", it runs CCGS check + prism
  (e.g. "CCGS: ok. prism: Lens #23 (Endogenous Value): creature has play value
  beyond the sats gate").
- RAG corpus: Schell book on this machine (verified present). Load via prism skill.

## Coordination Rules

User-driven collaboration, not autonomous execution. Every task follows:
**Question -> Options -> Decision -> Draft -> Approval.**
Agents MUST ask "May I write this to [filepath]?" before Write/Edit.
No commits without user instruction.

## Project Structure

```
terramon/
  application/game_loop.py     # agentic loop (ACT/OBSERVE/REWARD/REFLECT)
  adapters/json_memory.py      # persistent creature memory
  adapters/fal_art_generator.py# creature art (FAL)
  adapters/embedding_classifier.py  # thought -> archetype
  adapters/nostr_publisher.py  # share creature as signed Nostr note
  domain/progress.py           # terra growth, XP
  domain/rarity.py             # rarity + sats price
  ports/                       # PaymentPort, ArtPort, PublishPort (hexagonal)
terramon_tma/                  # Reflex TMA frontend
docs/                          # dvizhok agency output, STARS_ROI.md
```

## Engine Version Reference

Reflex pinned: 0.9.7 (reflex-base 0.9.7). Do not float.

## Coding Standards

- Hexagonal architecture: domain is pure, ports define boundaries, adapters plug in.
- Creatures = agents with memory, not stateless labels.
- Every rarity tier MUST be visually real (art), else it is a "label on a canned word".
- Local-first: agentic loop + memory run with ZERO external API calls; only art + LLM-reflection use network.
