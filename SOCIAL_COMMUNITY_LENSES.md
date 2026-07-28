# Terramon — Social & Community Lens Cluster Analysis

## Scope
5 lenses applied: #36 Competition, #37 Cooperation, #84 Friendship, #86 Community, #88 Love.
Files examined: `terramon_tma.py` (2024 lines), `creature_agent.py` (1087 lines), `agent_service.py`, `game_loop.py`, `summon_service.py`, `progress.py`, `nostr_publisher.py`, `publish_port.py`, `events/bus.py`, `events/agent_summoned.py`.

---

## 🔷 Lens #36 — Competition
**Schell's question:** "What creates competition in my game? Is the competition balanced? Is it satisfying?"

### Finding: Zero competition exists. The entire game is single-player solitaire.

| Location | Finding | Severity |
|---|---|---|
| `terramon_tma.py:1854-1901` | Bottom nav has Terra/Care/Map tabs — zero social or competitive tabs | HIGH |
| `terramon_tma.py:1902-1906` | Empty bottom-nav slot between Map and nothing — a 4th competitive tab should go here | MEDIUM |
| `progress.py:50-54` | Goal tiers (Explorer → Tamer → Terra Lord → Arcanist) are solo progression only — no competitive ladder | MEDIUM |
| `terramon/` (entire tree) | No `leaderboard`, `pvp`, `battle`, `rank`, `score`, or `race` anywhere in the codebase | HIGH |

### What's missing:
- **No creature battle system** — the `creature_agent.py` has stats (hunger, energy, happiness, level, evolution) that are PERFECT building blocks for PvP battles, but no battle logic exists
- **No leaderboard** — no global ranking by distinct count, XP, or collection quality
- **No weekly challenges** — no "collect 3 Fire-type creatures this week" competitive events
- **No rarity races** — no global feed showing "Bobby just summoned a LEGENDARY!"
- **No collection score** — no aggregate score players could compare (e.g., weighted by rarity)

### Recommendation:
1. Add a `LeaderboardTab` component to `terramon_tma.py` (~line 1870, 4th nav button) that shows:
   - Your rank among all players
   - Top 10 by distinct count / XP
   - Weekly movement ("You gained 3 ranks this week")
2. Add a `creature_battle()` function to `creature_agent.py` that uses existing stats (level, evolution, affinity) in a simple rock-paper-scissors or auto-battle engine.
3. Wire the Nostr event feed as a **global scroll** of recent summon events — "Player X summoned a RARE Sage" creates FOMO and implicit competition.

---

## 🔷 Lens #37 — Cooperation
**Schell's question:** "Does my game give players reasons to work together? Is there shared benefit?"

### Finding: Zero cooperation mechanics. No multiplayer of any kind.

| Location | Finding | Severity |
|---|---|---|
| `terramon_tma.py:233-236` | `terra` list is player-only — no shared terra concept | HIGH |
| `game_loop.py:36-73` | GameLoop operates on a single player, single service — no group play | HIGH |
| `progress.py:94-97` | `collection` is a `set[str]` — player-private, no shared collection | HIGH |
| `summon_service.py:36-137` | SummonService has no concept of group/batch summons | MEDIUM |

### What's missing:
- **No shared terra/garden** — two players cannot see each other's creatures in one view
- **No co-op summoning** — both players contribute a thought seed, a hybrid creature emerges
- **No creature trading** — no way to give a creature to another player
- **No cooperative goals** — no "both players collect 3 Explorer creatures to unlock a portal"
- **No visiting** — no "visit friend's terra" feature, despite the earth_map infrastructure

### Recommendation:
1. Add a **shared terra** concept: a `shared_terra` endpoint that merges two players' creature lists into one view. The earth_map component (`terramon_tma.py:1426-1476`) already supports multiple creature markers — add a "friend's creatures" toggle.
2. Add a **co-op summon** event: `coop_summon(thought_a, thought_b)` → creates a blended archetype with stats derived from both inputs. The archetype affinity system (`creature_agent.py:762-790`) already models multi-archetype influences — wire it to two inputs.
3. Add **creature visiting**: `visit_terra(other_player_id)` loads their creatures into a read-only view. The existing `_MEMORY.load_all_seeds()` infrastructure supports this with a player ID filter.

---

## 🔷 Lens #84 — Friendship
**Schell's question:** "Does the creature feel like a friend or a tool? What makes the player care about it as an individual?"

### Finding: Strong foundation in domain model, but TMA integration is incomplete.

| Location | Finding | Severity |
|---|---|---|
| `creature_agent.py:249-251` | `bond_level` and `milestone_memory` fields exist ✅ | INFO |
| `creature_agent.py:292-293` | `bond_level += 1` on every interaction ✅ | INFO |
| `creature_agent.py:854-902` | Bond milestone gifts at 10/25/50/100/200/500 interactions ✅ | INFO |
| `creature_agent.py:908-929` | Absence greeting when player returns after >4 ticks ✅ | INFO |
| `creature_agent.py:843-848` | Memory fragment recall during talk interaction ✅ | INFO |
| **`terramon_tma.py:986-999`** | **"Bond" bar shows `agent_happiness`, NOT `bond_level`** — the actual friendship stat is invisible | **HIGH** |
| **`terramon_tma.py:169-170`** | `reflection` is schema-derived, not bond-aware — never mentions the relationship depth | **MEDIUM** |
| **`agent_service.py:96-97`** | `bond_level` serialized in `to_dict()` but **never consumed by TMA state** | **HIGH** |
| **`game_loop.py:26-73`** | `TurnResult` doesn't include bond_level or milestone data — the TMA never receives it | **HIGH** |
| `terramon_tma.py:734-745` | `_dynamic_lore()` mentions interaction_count but NOT bond_level — stale data | LOW |
| `terramon_tma.py:344-358` | `summon()` creates a fresh `CreatureAgent` each time — bond resets every summon | HIGH |

### Critical findings:

1. **Bond resets on every summon** (`terramon_tma.py:346-352`). When `summon()` runs, it creates a new `CreatureAgent` for the greeting LLM call with `agent_id="summon-greet"`, which has `bond_level=0`. The actual summoned creature's bond is never loaded from memory. The `feed_agent`, `play_with_agent`, etc. handlers also create temporary `CreatureAgent("_tmp", ...)` instances — bond modifications happen on a throwaway object and are lost.

2. **Bond never decays** (`creature_agent.py:292-293`). `bond_level` only goes up (incremented by 1 per interaction), never down when the creature is neglected. This makes it a participation trophy rather than a genuine relationship metric.

3. **No naming** — creatures are `"Hero #a1b2"` (`agent_service.py:39`). The player never names their creature, preventing individual attachment.

### Recommendation:
1. **Persist bond_level** — Add `bond_level` to `ThoughtSeed` / `JsonMemory` so it survives across sessions. Load it when showing the creature card.
2. **Make bond visible in TMA** — Replace the happiness-based "Bond" bar (`terramon_tma.py:986-999`) with a real `bond_level` display. Add bond milestone celebrations.
3. **Add bond decay** — When a creature goes `DORMANT` (`creature_agent.py:567-568`), decay bond by 1 per tick to create "relationship maintenance" stakes.
4. **Add creature naming** — Add a `name_creature(agent_id, custom_name)` event and show the custom name in the creature card (`terramon_tma.py:1662-1756`).
5. **Load real bond on TMA mount** — In `load_terra()` (`terramon_tma.py:493-512`), load the current creature's bond from memory instead of creating fresh agents each time.
6. **Fix agent creation for care actions** — The feed/play/rest/talk handlers should operate on a persisted CreatureAgent, not a throwaway `_tmp`.

---

## 🔷 Lens #86 — Community
**Schell's question:** "What gives players a sense of community? How do they share their experiences?"

### Finding: Share button exists but the Nostr protocol adapter is completely disconnected from the game.

| Location | Finding | Severity |
|---|---|---|
| `terramon_tma.py:628-640` | `share_creature()` copies a text card to clipboard — works but limited ✅ | INFO |
| `terramon_tma.py:1035-1042` | Share button in creature_card UI ✅ | INFO |
| `nostr_publisher.py:1-214` | Full BIP-340 Nostr publisher with WebSocket broadcast exists ✅ | INFO |
| `publish_port.py:1-72` | `ShareCard` dataclass + `PublishPort` protocol ✅ | INFO |
| **Entire codebase except `test_nostr_publisher.py`** | **NostrPublisher is NEVER instantiated or called** — zero integration points | **CRITICAL** |
| **`summon_service.py:80-137`** | `summon()` publishes an `AgentSummoned` event but does NOT create a ShareCard or call PublishPort | **HIGH** |
| **`game_loop.py:47-73`** | `take_turn()` doesn't call PublishPort after summon | **HIGH** |
| `terramon_tma.py:80-85` | `_SERVICE` created with a bare `EventBus()` — no publisher connected | HIGH |
| `creature_agent.py:260` | `share_code` field exists but is `""` by default and never populated | MEDIUM |

### What's missing:
- **No community feed** — players cannot see what others summoned
- **NostrPublish is a dead adapter** — full implementation, zero callers
- **No follow/friend system** — no way to connect with other tamers
- **No "hot creatures" feed** — no trending/notable summons displayed
- **No comments or reactions** on other players' creatures
- `share_code` on CreatureAgent is a stub

### Recommendation:
1. **Wire NostrPublish into summon flow** — In `game_loop.py:take_turn()` or `summon_service.py:summon()`, create a `ShareCard` from the summon result and call `PublishPort.publish()`. Add a `publisher` parameter to `SummonService.__init__()`.
2. **Generate `share_code`** — In `creature_agent.py` or `agent_service.py`, generate a unique share code for each creature via `blake2b(agent_id + archetype)[:8]`.
3. **Add a community feed tab** to the bottom nav (4th button, replacing empty slot): show Nostr notes from other players' summons.
4. **Add creature "boost"** — Let players zap (tip) another player's creature via Lightning. The `lightning_adapter.py` and `stripe_adapter.py` already exist.
5. **Show "Other Tamers" near you** — The earth_map (`terramon_tma.py:1426-1476`) shows only your creatures. Add an overlay showing recently summoned creatures near the player's geo-location.

---

## 🔷 Lens #88 — Love
**Schell's question:** "What makes the player feel affection for their creature? What creates reciprocal love?"

### Finding: The "Lover" archetype exists but love mechanics are shallow and one-sided.

| Location | Finding | Severity |
|---|---|---|
| `terramon_tma.py:116` | `"Lover": "Connection is the only truth."` — archetype lore exists ✅ | INFO |
| `creature_agent.py:854-902` | 6 bond-level gift messages exist (10/25/50/100/200/500) ✅ | INFO |
| `creature_agent.py:876-902` | Gift messages are genuinely touching ("You kept coming back...") ✅ | INFO |
| **`terramon_tma.py:195-196`** | `agent_name: str = ""` — never personalized, auto-generated "Hero #a1b2" | **HIGH** |
| **`creature_agent.py:877-901`** | **Bond gifts are archetype-agnostic** — Lover archetype creature gets same text as Hero archetype creature | MEDIUM |
| **`terramon_tma.py:628-640`** | `share_creature()` is clipboard-only — no love language of "show your beloved creature to the world" | MEDIUM |
| **`agent_service.py:37-39`** | Name generation is deterministic and impersonal — `"Hero #a1b2"` format | MEDIUM |
| **`terramon_tma.py:1997-2001`** | No `app.mount` handler that could trigger a welcome-back animation for returning players | LOW |

### What's missing:
1. **No naming ceremony** — the most basic love mechanic in creature games (naming your pet) doesn't exist
2. **No bonding animations** — hearts, sparkles, or visual "purr" effects when the creature sees you
3. **No love decay** — bond only goes up, never down, making gifts feel unearned
4. **No archetype-specific love language** — Lover creature should say different things at bond milestones than Sage
5. **No creature diary/journal** — `player_journal` field exists but is never shown or written to

### Recommendation:
1. **Add naming** — In `terramon_tma.py`, add a `set_creature_name(name: str)` event similar to `set_thought`. Show the custom name prominently on the creature card. Default is auto-generated, but once named, use the custom name everywhere.
2. **Archetype-bond gifts** — Replace flat `gifts` dict in `_bond_gift()` (`creature_agent.py:876-902`) with an archetype-dimensioned dict: `gifts[level][archetype]` so Lover creatures give love-text and Hero creatures give respect-text at the same bond milestone.
3. **Add visual love signals** — In `creature_card()` and `creature_care_panel()`, add:
   - Heart floaters when bond_level hits milestones
   - A "purr" / glow pulse when the creature is fed or played with at high bond
   - A special "greeting" animation when returning after absence (memory greeting is text-only now)
4. **Wire `player_journal`** — Add a "Journal" button in `creature_care_panel()` that shows the creature's memories, bond milestones, and the player's shared history. This is the love LENS made visible.

---

## Summary: Quick-Fix Priority Matrix

| Priority | Lens | Fix | File:Line | Effort |
|---|---|---|---|---|
| 🔴 P0 | #84 | Persist bond_level across sessions (fixes bond-reset-per-summon bug) | `agent_service.py:37-45`, `thought_seed.py` | 1h |
| 🔴 P0 | #86 | Wire NostrPublish into summon flow (stop being a dead adapter) | `game_loop.py:47-73`, `terramon_tma.py:80-85` | 1h |
| 🟠 P1 | #84 | Show real bond_level in TMA UI (not happiness-as-bond) | `terramon_tma.py:986-999` | 30m |
| 🟠 P1 | #88 | Add creature naming (basic love mechanic) | `terramon_tma.py:1756` area | 30m |
| 🟠 P1 | #88 | Archetype-specific bond gifts | `creature_agent.py:876-902` | 1h |
| 🟡 P2 | #36 | Add leaderboard tab (4th nav button) | `terramon_tma.py:1870-1906` | 2h |
| 🟡 P2 | #37 | Co-op summon concept | `summon_service.py:80-137` | 3h |
| 🟡 P2 | #84 | Bond decay when creature neglected | `creature_agent.py:292-293` | 30m |
| 🟢 P3 | #88 | Wire player_journal into TMA | `terramon_tma.py` new component | 2h |
| 🟢 P3 | #86 | Community feed from Nostr events | New TMA component | 4h |
| 🟢 P3 | #36 | Creature battle system (uses existing stats) | New domain module | 8h |
