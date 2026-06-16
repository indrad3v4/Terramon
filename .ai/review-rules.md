# Terramon — Serge Review Rules

Serge is Hugging Face's automated PR reviewer.
To trigger a review, comment on a PR:
```
@askserge please review
```

Serge checks every diff against the rules below.
A rule marked `[HARD]` blocks the merge. `[SOFT]` is advisory.

---

### 1. [HARD] Hexagonal boundary

**Domain and ports must never import adapters.**
- `terramon/domain/` → only Python stdlib + `dataclasses`
- `terramon/ports/` → only `typing.Protocol`, stdlib, and domain types
- `terramon/adapters/` → may import ports and domain
- No file outside `terramon/events/` may define an `Event` dataclass

*Example violation:* `from terramon.adapters.json_memory import JsonMemory` inside `domain/thought_seed.py`.

---

### 2. [HARD] ThoughtSeed contract

`thought_seed.py` exports a `ThoughtSeed` dataclass with exactly these fields:

| Field | Type | Required |
|-------|------|----------|
| `raw_input` | `str` | yes |
| `summoned_agent` | `str` | yes |
| `timestamp` | `str` | yes |
| `status` | `str` | yes |

No additional fields may be added without creating a new port interface first.

---

### 3. [HARD] Event naming

- Events use **past-tense** names: `AgentSummoned`, not `SummonAgent`.
- Every event is a `@dataclass` class.
- Events are never plain `dict`, `NamedTuple`, or `TypedDict`.
- An event's fields are all **immutable** (frozen=True is preferred).

---

### 4. [SOFT] Tests per agent

Every new agent class (Ranger, Archivist, Strategist, etc.) must have **at least one passing test** in `tests/` before merge.

Placeholder tests or `pass`-only tests will be flagged.

---

### 5. [SOFT] No overengineering

Before adding a new dependency, the diff must contain a comment or commit message explaining why.

A class with only one method should be a function unless it has a clear reason to be a class (e.g., implements a Protocol, holds state across calls).
