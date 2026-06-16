# Terramon Day 3 Plan — Scout Remembers

**TL;DR:** We will build Terramon as a **hexagonal + event-driven** hybrid. The backend keeps game rules clean and separate from storage, while agents talk to each other through signals. Day 3 proves the loop: a player's thought seed is routed to an agent, saved as JSON memory, and announced as an event.

---

## 1. Architecture Comparison

Think of architecture as the "floor plan" of your code house. Each style arranges rooms differently.

| Architecture | Simple Analogy | Best For | Terramon Fit |
|--------------|----------------|----------|--------------|
| **Hexagonal** | A kitchen with plug-in appliances: the stove, fridge, and blender all fit the same wall sockets. | Swapping tools without rewriting rules. | **High.** We can start with JSON memory and later swap in SQLite or a blockchain ledger. |
| **Event-Driven** | A school intercom: one announcement reaches every classroom that cares. | Agents reacting to each other without tight coupling. | **High.** When a Ranger spots something, the Strategist and Archivist can listen in. |
| **Clean Architecture** | A castle with a throne room at the center and outer walls for guards. | Large teams needing strict dependency rules. | Medium. Powerful, but adds folders early; we can grow into it. |
| **MVC** | A restaurant: Model = kitchen, View = dining room, Controller = waiter. | Simple CRUD apps and web pages. | Low. Game agents do not map cleanly to Model/View/Controller. |
| **Actor Model** | A post office where every worker has their own mailbox and never shares a desk. | Thousands of independent agents running in parallel. | Medium-High long term; overkill for Day 3. |

**Verdict for Day 3:** **Hexagonal + Event-Driven hybrid.**
- Hexagonal keeps our game rules safe from tool changes.
- Event-driven lets agents "hear" each other without direct imports.
- We call this hybrid **"Summon & Signal."**

---

## 2. Recommended Hybrid Explained for a Python Learner

Imagine you are playing with LEGO.

- **Domain bricks** are the shapes of your game world: a `ThoughtSeed`, an `Agent`, a `Territory`.
- **Port bricks** are the studs on top: they say, "any piece that fits here can be used."
- **Adapter bricks** are the actual pieces you snap on: JSON file, SQLite, LLM classifier, keyword classifier.
- **Events** are little paper notes you pass between LEGO sets: "Ranger saw an enemy."

In Python:

```python
# domain brick
@dataclass
class ThoughtSeed:
    raw_input: str
    summoned_agent: str
    timestamp: str
```

```python
# port studs
class MemoryPort(Protocol):
    def save_seed(self, seed: ThoughtSeed) -> None: ...
    def load_all_seeds(self) -> list[ThoughtSeed]: ...
```

```python
# adapter brick
class JsonMemoryAdapter(MemoryPort):
    def save_seed(self, seed: ThoughtSeed) -> None: ...
```

```python
# paper note
@dataclass
class AgentSummoned:
    thought_seed: str
    agent_name: str
    timestamp: str
```

This way, if you later replace JSON with a real database, you only change the adapter. The rest of the castle stays standing.

---

## 3. Filesystem Plan

| Path | What Lives There |
|------|------------------|
| `terramon-backend/terramon/domain/` | Plain data shapes: `ThoughtSeed`, `Agent`, `Territory`. |
| `terramon-backend/terramon/application/` | Use cases: `SummonService`, `IntentRouter`. |
| `terramon-backend/terramon/ports/` | Protocol interfaces: `MemoryPort`, `ClassifierPort`. |
| `terramon-backend/terramon/adapters/` | Concrete implementations: `JsonMemoryAdapter`, `KeywordClassifier`. |
| `terramon-backend/terramon/events/` | Messages and bus: `AgentSummoned`, `EventBus`. |
| `terramon-backend/terramon/agents/` | Agent behavior logic: `Ranger`, `Archivist`, `Strategist`. |
| `terramon-backend/terramon/tools/` | Shared helpers: `time_tool.py`, geo helpers. |
| `terramon-backend/tests/` | pytest tests. |
| `terramon-frontend/terramon_frontend/pages/` | Reflex pages/routes. |
| `terramon-frontend/terramon_frontend/components/` | Reusable UI pieces. |
| `terramon-frontend/terramon_frontend/state/` | Reflex state classes. |
| `terramon-frontend/terramon_frontend/services/` | API clients to talk to the backend. |
| `terramon-frontend/terramon_frontend/assets/` | Images, icons, map tiles. |

---

## 4. What Each Top-Level Folder Does

| Folder | One Sentence | Python Analogy | Example File |
|--------|-------------|----------------|--------------|
| `domain/` | The pure shapes of your game world — plain data, no logic. | A `@dataclass` is like a cookie cutter: it defines the shape, not the taste. | `thought_seed.py` → `@dataclass class ThoughtSeed` |
| `application/` | The "what happens when" — use cases that orchestrate domain objects. | Like a recipe that says "mix flour and eggs" without caring which bowl you use. | `summon_service.py` → `class SummonService` |
| `ports/` | The contracts that say "any adapter shaped like this will work." | Like a USB-C port: you don't care what's on the other end, only that it fits. | `memory_port.py` → `class MemoryPort(Protocol)` |
| `adapters/` | The real things that plug into ports — files, APIs, databases. | Like the actual USB-C cable you buy: it implements the shape. | `json_memory.py` → `class JsonMemoryAdapter(MemoryPort)` |
| `events/` | Messages agents broadcast so others can react. | Like a group chat: one message, many readers. | `agent_summoned.py` → `@dataclass class AgentSummoned` |
| `agents/` | The brains — what each agent actually does when summoned. | Like hiring a specialist: the Ranger knows terrain, the Archivist knows history. | `ranger.py` → `class RangerAgent` |
| `tools/` | Shared utility functions any agent can use. | Like a Swiss Army knife you keep in your pocket. | `time_tool.py` → `get_time_phase()` |
| `tests/` | Code that proves your code works. | Like a fire drill: you run it regularly to make sure nothing is broken. | `test_summon_service.py` |

---

## 5. How JSON Memory Fits In (Day 3)

Today we build the first link in the chain: **thought → agent → memory**.

The player types something like `"scan the northern ridge"`. That string is a **thought seed** — a raw idea that hasn't been assigned to any agent yet.

```
player input → IntentRouter → agent name → SummonService → ThoughtSeed → JsonMemoryAdapter → .jsonl file
                                                                                         ↓
                                                                                    AgentSummoned event
```

The JSONL file (`data/thought_seeds.jsonl`) stores one JSON object per line:

```json
{"raw_input": "scan the northern ridge", "summoned_agent": "Ranger", "timestamp": "2026-06-16T22:34:09.110259", "status": "summoned"}
```

Every time you summon an agent, a new line is appended. No database, no server — just a file. This is the **MemoryPort** adapter in action. Later, when we swap to SQLite or a blockchain, we write a new adapter class. The `SummonService` never changes.

---

## 6. First Files to Create

### Backend — 7 files to create next (in order)

| # | File | What It Contains | Why First |
|---|------|-----------------|-----------|
| 1 | `terramon/domain/thought_seed.py` | `@dataclass class ThoughtSeed` | Foundation shape for everything |
| 2 | `terramon/ports/memory_port.py` | `class MemoryPort(Protocol)` | Contract before implementation |
| 3 | `terramon/ports/classifier_port.py` | `class ClassifierPort(Protocol)` | Contract for routing |
| 4 | `terramon/adapters/json_memory.py` | `class JsonMemoryAdapter(MemoryPort)` | Day 3 memory storage |
| 5 | `terramon/adapters/keyword_classifier.py` | `class KeywordClassifier(ClassifierPort)` | Day 3 routing |
| 6 | `terramon/events/agent_summoned.py` + `bus.py` | `AgentSummoned` event + `EventBus` | Signal layer |
| 7 | `terramon/application/intent_router.py` + `summon_service.py` + `cli.py` | Orchestration + CLI | Proves the full loop |

### Frontend — 5 files to create later (when Reflex is wired)

| # | File | What It Contains | Why Later |
|---|------|-----------------|-----------|
| 1 | `pages/summon.py` | Reflex page with thought-seed input | First user-facing UI |
| 2 | `components/summon_form.py` | Reusable form component | Building block |
| 3 | `state/summon_state.py` | Reflex State class for summon flow | Connects UI to backend |
| 4 | `services/summon_client.py` | HTTP client to call backend API | Separates concerns |
| 5 | `assets/map_tile_placeholder.svg` | Empty world map | Visual anchor |

---

## 7. Improving CCGS — Lens Toolkit

Jesse Schell's *The Art of Game Design* teaches that you should look at your game through different "lenses" — each lens reveals something you'd miss otherwise. The **Lens Toolkit** gives each CCGS role a set of lenses to apply when designing, reviewing, or debugging Terramon.

### 5 Terramon-Relevant Lenses

| Lens | Question It Asks | What It Reveals |
|------|-----------------|-----------------|
| **Lens of the Living World** | "Does the world feel alive even when the player isn't watching?" | Passive agent activity, time-based state changes, ambient events |
| **Lens of Territory** | "Does this place have meaning beyond its coordinates?" | Named regions, owner feelings, boundary tension |
| **Lens of Emergence** | "Can two simple rules create something surprising?" | Agent-agent interactions, resource conflicts, spontaneous events |
| **Lens of the Unseen** | "What hints can I give without showing the full truth?" | Fog of war, agent rumors, partial map reveals |
| **Lens of Memory** | "How does past action shape future possibility?" | Agent history, territory memory, persistent consequences |

### Lenses Mapped to Roles

| Role | Primary Lens | Why This Lens | Secondary Lens |
|------|-------------|---------------|----------------|
| **Strategist** | Lens of Emergence | Asks: which two agents, combined, create unexpected gameplay? | Lens of Territory |
| **Game Designer** | Lens of Territory | Asks: what makes a place feel like *mine* in code? | Lens of Memory |
| **Systems Designer** | Lens of Memory | Asks: how does state persist across summon cycles? | Lens of the Living World |
| **UI Programmer** | Lens of the Unseen | Asks: how do I show just enough to provoke curiosity? | Lens of Territory |
| **QA Lead** | Lens of the Living World | Asks: what happens when I walk away for an hour? | Lens of Emergence |

When any role starts a task, they should:
1. Put on their **primary lens** and describe what they see.
2. Switch to their **secondary lens** and describe what changed.
3. Write down one falsifiable claim per lens (e.g., *"If I leave two agents in the same territory for 10 minutes, at least one event will fire"*).

---

## 8. README Lines — Light Architecture Showcase

Add these three lines to the Terramon README (between the Day 2 entry and the Vision section):

```
- **Hexagonal backend.** Ports and adapters keep game rules clean — swap JSON for SQLite without changing the summon loop.
- **Event-driven agents.** When a Ranger spots something, every listening agent hears it. No direct imports, no tight coupling.
- **Reflex fullstack frontend.** Real-time reactive UI, Python end-to-end, no JavaScript required. The world lives in your browser.
```

---

## 9. Next GitHub Polish Tasks

### indrad3v4 Profile README

| Task | Why | Effort |
|------|-----|--------|
| Enable GitHub stats card (`?username=indrad3v4`) | Shows commit activity, repos, stars | ⭐ (5 min) |
| Add streak widget (`https://github-readme-streak-stats.herokuapp.com/?user=indrad3v4`) | Shows daily coding consistency | ⭐ (5 min) |
| Add Terramon to pinned repos | Drive visibility for the project | ⭐ (2 min) |
| Add "Currently building:" section with Terramon one-liner | Tells visitors what you're working on | ⭐ (10 min) |

### Terramon README

| Task | Why | Effort |
|------|-----|--------|
| Replace placeholder `main.py` run instructions with `cli.py` summon demo | Day 3 changed the entry point | ⭐⭐ (15 min) |
| Add "Day 3 — Scout Remembers" section | Documents the memory milestone | ⭐ (10 min) |
| Add hexagonal architecture badge (custom shield.io) | Visual architecture anchor | ⭐⭐ (20 min) |
| Add `.env.example` with `HF_TOKEN` placeholder | New contributors can set up in 30 seconds | ⭐ (5 min) |
| Add `data/` to `.gitignore` | Prevents committing generated memory files | ⭐ (2 min) |

---

**End of Day 3 Plan. The loop is proven. Tomorrow, agents wake up.**
