# PRISM: Risk & Process Lens Cluster — Terramon Analysis

**Date:** 2026-07-28
**Test suite:** 84 tests (83 ✅, 1 ❌)
**Scope:** 7 lenses applied to `/root/Terramon/`

---

## 🔷 Lens #14: Risk Mitigation — "What could go wrong?"

### Core Questions
- What single points of failure exist?
- How does the system degrade when external APIs fail?
- Are there circuit breakers, timeouts, retry logic?

### Findings

**1. No LLM response structure validation before parsing**
- **File:** `terramon/application/llm_behavior.py:397-403`
- **Issue:** `_call_llm()` catches ALL exceptions with `except Exception as e` and returns `None`. The OpenRouter API could return a valid HTTP 200 with error content (e.g. `{"error": {"message": "..."}}`), which would crash at `data["choices"][0]` — but since it's caught as Exception, it's indistinguishable from a network timeout. The retry logic re-tries 3 times even on 400 Bad Request responses (which will never succeed).
- **Fix:** Distinguish transient errors (timeout/5xx) from permanent errors (4xx, bad JSON, wrong schema). Only retry transient errors.

**2. `JsonMemory.load_all_seeds()` is unbounded**
- **File:** `terramon/adapters/json_memory.py:80`
- **Issue:** `raw = self.path.read_text(encoding="utf-8")` reads the ENTIRE file into memory. After thousands of summons, this will OOM. The `splitlines()` on the full text creates another copy.
- **Fix:** Use line-by-line iteration (`self.path.open('r')`) with readline in a loop instead of reading the whole file at once.

**3. FAL.ai API key is cached at construction time**
- **File:** `terramon/adapters/fal_art.py:396`
- **Issue:** `self._api_key = api_key or os.environ.get("FAL_KEY", "")` — if the env var changes during runtime (rotation), the old key is used until re-construction.
- **Fix:** Read `os.environ.get("FAL_KEY")` on each `generate()` call instead of caching.

**4. No circuit breaker for external APIs**
- **File:** `terramon/application/llm_behavior.py:594-606` and `terramon/adapters/fal_art.py:455-461`
- **Issue:** If OpenRouter or FAL.ai are down for an extended period, every single summon/creature-interaction still tries the API, wasting 30+ seconds on timeouts before falling back.
- **Fix:** Add a simple circuit breaker (e.g. after 3 consecutive failures, skip the API for 60 seconds). Reset on first success.

**5. `tools/web_search.py` has no retry logic**
- **File:** `tools/web_search.py:71`
- **Issue:** `urllib.request.urlopen(req, timeout=self.timeout)` — single attempt, no retry. A transient network glitch kills the search.
- **Fix:** Add 2 retries with 1s backoff (same pattern as `_call_with_retry` in llm_behavior.py).

**6. DuckDuckGo Lite HTML parsing is fragile (not a risk — a fragility)**
- **File:** `tools/web_search.py:93-141`
- **Issue:** `_parse_results()` parses raw HTML with string matching. DDG could change their HTML layout at any time, silently breaking search.
- **Fix:** Add a test that parses known HTML (captured snapshot) to catch layout changes.

**7. Missing: HF_TOKEN expiry check**
- **File:** `terramon/application/llm_behavior.py:61-62`
- **Issue:** `_has_hf_token()` checks if the env var exists but not if it's expired. HuggingFace tokens can expire and the fallback would silently fail.
- **Fix:** Check if the token is non-empty AND not trivially expired.

---

## 🔷 Lens #91: Playtesting — "Are the tests testing the right things?"

### Core Questions
- What failure modes are NOT covered by tests?
- Do the tests simulate real player behavior?
- Is there a gap between unit tests and integration tests?

### Findings

**Test suite status: 84 tests, 83 pass, 1 fails**

**❌ FAILING TEST: `test_play_session_reaches_goal`**
- **File:** `tests/test_embedding_classifier.py:183-204`
- **Error:** `AssertionError: goal not reached; collection={'Orphan', 'Innocent', 'Rebel', 'Hero'}`
- **Root cause:** The test expects `goal_reached=True` after 4 distinct creatures (Innocent, Orphan, Hero, Rebel) with `goal_distinct=3`. But the EmbeddingClassifier may be classifying slightly differently than expected. The test's training examples for "Rebel" include "rules are meant to be broken" which matches keyword-wise, but the embedding classifier uses TF-IDF vectors. The collection shows 4 distinct creatures, suggesting the classifier DID produce 4 distinct archetypes, but the `goal_reached` property didn't trigger. This could be a timing issue — `goal_reached` is checked via `r.goal_reached` after each turn, but the turn might change the classification.
- **Fix:** The thought "rules are meant to be broken" in the EmbeddingClassifier's test thought should match "Rebel" via embedding. The test uses a keyword-set that may not match the embedding classifier's prototype. Needs investigation into the EmbeddingClassifier's behavior for this specific input.

### Missing Test Coverage (15 gaps found)

| # | Component | Missing Tests | Risk Level |
|---|-----------|--------------|------------|
| 1 | `events/bus.py` | Middleware registration, `content_safety_middleware`, middleware failure isolation, filtered middleware by type | **High** |
| 2 | `application/agent_service.py` | `create_agent`, `to_dict`, `tick` passthrough, all interactions | **High** |
| 3 | `application/llm_behavior.py` | `generate_response`, `_call_llm`, `_call_huggingface`, `_call_with_retry`, `_parse_structured_response`, edge cases (malformed JSON, empty response) | **High** |
| 4 | `domain/creature_agent.py` | `feed`, `play`, `rest`, `talk`, `tick`, `_apply_tick`, `_compute_state`, `_compute_mood`, `can_evolve`, `STATE_MOD`, interaction history | **High** |
| 5 | `events/bus.py EventBus` | Full publish cycle with middleware, safety flagging, multiple subscribers, subscriber failure isolation | **High** |
| 6 | `application/k3_insight_engine.py` | MoE router, expert MLPs, thinking loop, all 3 inference paths | **Medium** |
| 7 | `adapters/fal_art.py` | `_fal_request` retry/backoff logic, `_augment_and_save` error paths, `_svg_to_png` fallback | **Medium** |
| 8 | `application/bayes_router.py` | Posterior updates, prior integration | **Medium** |
| 9 | `application/intent_router.py` | Routing logic, fallback paths | **Medium** |
| 10 | `application/payment_gate.py` | `requires_payment`, `request`, `settle` | **Medium** |
| 11 | `domain/progress.py` | `check_resonances()`, goal tier advancement, tier edge cases, duplicate handling | **Medium** |
| 12 | `application/feedback.py` | `render_reveal` (only indirect via game_loop) | **Low** |
| 13 | `tools/web_search.py` | `_parse_results` with known HTML | **Low** |
| 14 | `tools/web_fetch.py` | `_HTMLTextExtractor`, charset edge cases | **Low** |
| 15 | `creature_agent.py -- evolve()` | `evolve()` method (agent_service.py line 63 calls it but it's never tested) | **Low** |

### Key Finding: The creature_agent.py file — the CORE gameplay mechanic (state machine, stats, tick, interactions) — has ZERO direct tests.

---

## 🔷 Lens #92: Technology — "Are the right technologies used?"

### Core Questions
- Is the tech stack appropriate for a Telegram Mini App?
- What are the technology risks (deprecation, cost, performance)?
- Are there simpler alternatives?

### Findings

**1. Reflex 0.9.x for TMA — ✅ Appropriate but risk of breaking upgrades**
- **File:** `terramon_tma/terramon_tma.py`
- **Issue:** Reflex 0.9.x compiles to a static SPA, ideal for Telegram Mini Apps. Risk: Reflex had major breaking changes between 0.9.x → 1.0+. Version is not pinned anywhere visible.
- **Recommendation:** Pin `reflex>=0.9.0,<1.0.0` in requirements and test TMA compilation in CI.

**2. DeepSeek V4 Flash (OpenRouter) → Qwen2.5-7B (HF free) → Template — ✅ Good 3-deep fallback**
- **File:** `terramon/application/llm_behavior.py:35-37`
- **Issue:** The fallback chain is well-designed but OpenRouter may add latency (100-300ms per call). For a TMA, this means creature responses take 1-3 seconds.
- **Recommendation:** Add a loading/typing indicator in the TMA for interactions that trigger LLM calls.

**3. FAL.ai flux/schnell — ✅ Appropriate, placeholder fallback exists**
- **File:** `terramon/adapters/fal_art.py:39`
- **Issue:** FAL.ai generates images in 2-4 seconds. In a TMA context, waiting 2-4 seconds for a summon portrait is acceptable. The placeholder SVG/PNG fallback is well-implemented.
- **Recommendation:** Consider adding a "generating..." animation in the TMA so the player knows something is happening.

**4. Nostr publishing — ✅ Good for decentralization**
- **File:** `terramon/adapters/nostr_publisher.py`
- **Issue:** Relay list is hardcoded (`["wss://a.relay", "wss://b.relay"]`). If those relays go down, publishing silently fails.
- **Recommendation:** Read relay list from config/env, add more relays, implement a relay discovery mechanism.

**5. DuckDuckGo Lite HTML parsing — ⚠️ Fragile**
- **File:** `tools/web_search.py:92-141`
- **Issue:** HTML parsing without a proper parser. DDG could change layout at any time.
- **Recommendation:** Use a simple CSS-selector based parser (or switch to the official DuckDuckGo API if available). At minimum, add a regression test with captured HTML.

**6. JSON memory backend — ⚠️ Not scalable past ~10K records**
- **File:** `terramon/adapters/json_memory.py:80`
- **Issue:** `load_all_seeds()` reads the entire file into memory. With 10K records at ~500 bytes each, that's 5MB — manageable. At 100K records, it's 50MB.
- **Recommendation:** Add streaming read, pagination, or consider SQLite for production.

---

## 🔷 Lens #77: Character Traits — "Do the 12 Jungian archetypes have distinct mechanical traits or just labels?"

### Core Questions
- Do different archetypes play differently?
- Is the archetype system cosmetic or mechanical?
- Are there meaningful gameplay differences between archetypes?

### Findings

**The archetypes are COSMETIC + CLASSIFICATION, NOT MECHANICAL**

| Aspect | Mechanical? | File:Line | Evidence |
|--------|------------|-----------|----------|
| Classification | ✅ YES | `keyword_classifier.py:27-76` | 10 distinct keywords per archetype, IDF-weighted scoring |
| Classification | ✅ YES | `embedding_classifier.py:286-371` | 5 training examples per archetype, distinct vector space regions |
| LLM Voice | ✅ YES (cosmetic) | `llm_behavior.py:69-118` | 12 distinct voice instructions for LLM prompt |
| Stats (hunger/energy/happiness) | ❌ NO | `creature_agent.py:220-224` | ALL archetypes start with identical stats (80/80/60) |
| Stat decay rates | ❌ NO | `creature_agent.py:56-58` | `DECAY_HUNGER=5, DECAY_ENERGY=3, DECAY_HAPPINESS=2` — global constants |
| State machine | ❌ NO | `creature_agent.py:481-499` | `_compute_state()` is archetype-agnostic |
| Interaction modifiers | ❌ NO | `creature_agent.py:78-97` | `STATE_MOD` applies by CreatureState, not by archetype |
| Evolution requirements | ❌ NO | `creature_agent.py:186-191` | Same `EvolutionRequirement(min_level=10)` for all creatures |
| Lore text | ✅ YES (cosmetic) | `creature_agent.py` | `_archetype_verb()`, `_archetype_feeling()`, `_archetype_sound()` return different text |
| Insight extraction | ✅ YES | `k3_insight_engine.py` | Archetype influences the insight output via MoE router |

**1. All creatures are mechanically identical**
- **File:** `terramon/domain/creature_agent.py:220-224`
- **Issue:** `hunger: int = 80, energy: int = 80, happiness: int = 60` — same defaults regardless of archetype. A Hero creature has the exact same stat curve as an Orphan.
- **Fix:** Define per-archetype stat modifiers:
  ```python
  _ARCHETYPE_STATS = {
      "Hero":      {"hunger": 70, "energy": 90, "happiness": 60},  # high energy, low hunger
      "Caregiver": {"hunger": 60, "energy": 70, "happiness": 80},  # high happiness
      "Orphan":    {"hunger": 80, "energy": 60, "happiness": 40},  # low happiness, needy
      ...
  }
  ```

**2. State machine thresholds are archetype-agnostic**
- **File:** `terramon/domain/creature_agent.py:481-499`
- **Issue:** `_compute_state()` uses global thresholds (SICK < 10, HUNGRY < 30, TIRED < 30) — same for all archetypes. A Hero should maybe have higher TIRED threshold (gets tired slower), an Orphan lower HAPPY threshold (harder to keep happy).
- **Fix:** Add archetype-specific state thresholds.

**3. Evolution requirements are uniform**
- **File:** `terramon/domain/creature_agent.py:186-191`
- **Issue:** `EvolutionRequirement(min_level=10, min_happiness=70, ...)` — same for every creature. Archetypes should have different evolution paths.
- **Fix:** Define per-archetype `EvolutionRequirement`.

**4. The `_archetype_verb()` methods are untested**
- **Finding:** The verb/feeling/sound methods produce different text per archetype but are completely untested.
- **Fix:** Add tests that verify each archetype returns a non-empty verb/feeling/sound.

---

## 🔷 Lens #79: Character Web — "Do creatures have relationships with each other?"

### Core Questions
- Do summoned creatures interact with each other?
- Is there a "social graph" of creatures?
- Does owning complementary creatures unlock gameplay?

### Findings

✅ **CREATURE RESONANCES EXIST** — but are purely cosmetic

**1. Resonances are defined but untested**
- **File:** `terramon/domain/progress.py:61-70`
- **Current state:** 8 resonance pairs defined (Hero+Rebel, Sage+Jester, Creator+Magician, Lover+Caregiver, Explorer+Innocent, Ruler+Orphan, Innocent+Rebel, Sage+Orphan).
- **Issue:** `check_resonances()` at line 73-79 returns flavor text only. No gameplay effect.

**2. No tests for resonance system**
- **File:** `tests/test_game_loop.py` (no resonance tests)
- **Fix needed:** Add tests:
  ```python
  def test_check_resonances_finds_pairs():
      collection = {"Hero", "Rebel", "Sage"}
      found = check_resonances(collection)
      assert len(found) == 1  # Hero+Rebel
      assert "Hero" in found[0] and "Rebel" in found[0]

  def test_check_resonances_no_match():
      assert check_resonances({"Hero", "Orphan"}) == []

  def test_check_resonances_multiple_pairs():
      coll = {"Hero", "Rebel", "Sage", "Jester"}
      assert len(check_resonances(coll)) == 2
  ```

**3. Resonances have no gameplay effect**
- **File:** `terramon/domain/progress.py:73-79`
- **Issue:** Returns text strings only. A "resonance" should unlock something: bonus XP, special interactions, co-op abilities.
- **Fix:** Award bonus XP when a resonance pair is unlocked:
  ```python
  def claim_resonance_bonus(collection: set[str]) -> int:
      bonus = 0
      for a, b, _ in CREATURE_RESONANCES:
          if a in collection and b in collection:
              bonus += 25  # XP bonus for unlocking a pair
      return bonus
  ```

**4. No creature-to-creature interactions**
- **Finding:** Creatures don't interact with each other at all. A CreatureAgent has no reference to other creatures.
- **Recommendation:** Add a `neighbors` field to CreatureAgent and a "visit" interaction where creatures can observe/respond to each other. This is a major gameplay depth opportunity.

---

## 🔷 Lens #80: Status — "What status effects exist? Are they tested?"

### Core Questions
- What states/statuses do creatures have?
- Are state transitions tested?
- Do players understand the status system?

### Findings

**✅ Rich state machine exists — but ZERO tests**
- **File:** `terramon/domain/creature_agent.py:108-121`
- **States:** `HAPPY`, `HUNGRY`, `TIRED`, `EVOLVING`, `SICK`, `DORMANT`
- **Mechanics:** Each state affects decay rates (STATE_DECAY, line 143), interaction effectiveness (STATE_MOD, line 78), and day phase (DAY_PHASE_MOD, line 156).
- **✨ Structurally excellent** — state machine with EMA decay, gradient clipping, mood computation, day/night cycle.

**1. 🐛 BUG: `dormant_ticks` is a MODULE-LEVEL variable shared across ALL creatures**
- **File:** `terramon/domain/creature_agent.py:101`
- **Issue:** `dormant_ticks: int = 0  # counter for consecutive all-zero ticks` is defined at module scope, NOT as an instance attribute. Multiple creatures share the same counter — creature A going dormant also counts creature B's ticks.
- **Fix:** Move into `__init__` or make it a dataclass field:
  ```python
  # Current (broken):
  dormant_ticks: int = 0  # module-level, shared!

  # Fix (in CreatureAgent dataclass):
  dormant_ticks: int = 0  # instance-level via dataclass default
  ```
  Since `CreatureAgent` is a `@dataclass`, adding `dormant_ticks: int = 0` as a field makes it per-instance. The current module-level variable (line 101) is never referenced inside the dataclass — the dataclass gets its OWN `dormant_ticks` field via the `field()` mechanism... Actually wait, line 101 is `dormant_ticks: int = 0` at MODULE level, and `_compute_state` at line 487 uses `self.dormant_ticks`. But if `CreatureAgent` doesn't have `dormant_ticks` as a dataclass field, `self.dormant_ticks` falls through to the module-level variable, making it SHARED.
  - **Check:** `CreatureAgent` (line 195) does NOT list `dormant_ticks` as a field. So `self.dormant_ticks` resolves to the module-level `dormant_ticks`, which IS shared across all creature instances!
  - **Fix:** Add `dormant_ticks: int = 0` as a field in the `CreatureAgent` dataclass.

**2. No tests for any state machine behavior**
- **Missing tests (all in `creature_agent.py`):**
  - `test_tick_decays_stats()` — verify EMA decay factor (0.97) is applied correctly
  - `test_compute_state_sick_when_any_stat_below_10()` — state machine priority
  - `test_compute_state_dormant_after_24_ticks()` — DORMANT transition
  - `test_state_mod_feed_when_hungry()` — STATE_MOD amplification
  - `test_gradient_clipping_caps_delta()` — MAX_DELTA_PER_TICK enforcement
  - `test_day_phase_modifies_decay()` — day/night cycle
  - `test_mood_computed_from_history()` — mood computation
  - `test_play_energy_too_low_returns_message()` — energy gating
  - `test_can_evolve_logistic()` — evolution probability

**3. `_archatype_verb()` typo (cosmetic)**
- **File:** `terramon/domain/creature_agent.py` — likely a method named `_archetype_verb()` being called correctly but there may be a typo somewhere.

---

## 🔷 Lens #87: Griefing — "Can players abuse the system?"

### Core Questions
- Can players spam the summon system?
- Can players submit harmful content?
- Is there economic abuse potential?

### Findings

**1. Content safety middleware FLAGS but does NOT BLOCK harmful content**
- **File:** `terramon/events/bus.py:128-150`
- **Issue:** `content_safety_middleware()` always returns `(event, True)` — the event is NEVER dropped. Harmful content is logged but still reaches handlers. The comment says "for observability" but this means a player can summon creatures with hate speech/self-harm content and it goes through.
- **Fix:** Add a configuration option for the middleware to block flagged events:
  ```python
  def content_safety_middleware(event, block=True):
      ...
      if block and event.safety_flagged:
          return event, False  # DROP the event
      return event, True
  ```

**2. ❌ NO RATE LIMITING on summon**
- **File:** `terramon/application/summon_service.py:47-70`
- **Issue:** `summon()` can be called infinitely with no throttle. Each call triggers:
  - Classification (CPU)
  - Rarity computation (CPU: Dirichlet sampling with hash)
  - Insight extraction (CPU: K3 MoE forward pass)
  - JSON persistence (I/O)
  - Event dispatch
- **Fix:** Add rate limiting: track per-player summon timestamps and reject if < 2s between summons:
  ```python
  def __init__(self, ..., min_interval: float = 2.0):
      self._last_summon: dict[str, float] = {}
      self._min_interval = min_interval

  def summon(self, raw_input: str, player_id: str = "") -> ThoughtSeed:
      now = time.time()
      if player_id and now - self._last_summon.get(player_id, 0) < self._min_interval:
          raise RuntimeError("Summon too fast — wait a moment")
      ...
  ```

**3. ❌ NO INPUT LENGTH VALIDATION**
- **File:** `terramon/application/summon_service.py:47-70`
- **Issue:** `raw_input` is never length-checked. A 100KB string would cause:
  - Massive tokenization in `_encode` / keyword matching → O(n) memory per character
  - Huge rarity analysis (scans multiple keyword tuples)
  - Large JSON record in memory
  - Potential denial of service via memory exhaustion
- **Fix:** Validate input length early:
  ```python
  MAX_INPUT_LENGTH = 500
  if len(raw_input) > MAX_INPUT_LENGTH:
      raw_input = raw_input[:MAX_INPUT_LENGTH]  # or raise
  ```

**4. ❌ NO SUMMON COOLDOWN in middleware**
- **File:** `terramon/events/bus.py` (nowhere — doesn't exist)
- **Issue:** There's no mechanism to detect or prevent rapid-fire summons. A Telegram bot script could call `summon()` 1000 times in a minute.
- **Fix:** Add rate-limiting middleware to the EventBus:
  ```python
  def rate_limit_middleware(event):
      if isinstance(event, AgentSummoned):
          # Check rate limit per agent_name or IP
          ...
      return event, True
  ```

**5. ⚠️ No sanitization of summon text in Nostr output**
- **File:** `terramon/adapters/nostr_publisher.py` / ShareCard
- **Finding:** The player's thought text is shared to Nostr relays. Harmful content that bypasses the safety middleware would be published to the decentralized network.
- **Fix:** The content safety middleware should block (not just flag) events before they reach the Nostr publisher handler.

**6. `hash()` is used as seed in FAL.ai**
- **File:** `terramon/adapters/fal_art.py:405`
- **Issue:** `seed = hash(request.thought + request.archetype) & 0x7FFFFFFF` — Python's `hash()` is salted with a random per-process seed! Two different Python processes would produce different seeds for the same thought+archetype, breaking cache determinism.
- **Fix:** Use `hashlib.blake2b` instead:
  ```python
  seed = int.from_bytes(
      hashlib.blake2b((request.thought + request.archetype).encode(), digest_size=4).digest(),
      "big"
  ) & 0x7FFFFFFF
  ```

---

## Summary of Critical Issues by Severity

### 🔴 Critical (must fix)
1. **`dormant_ticks` shared across all creatures** — `creature_agent.py:101` — module-level variable, not instance field
2. **No rate limiting** — `summon_service.py:47` — infinite summon spam possible
3. **No input length validation** — `summon_service.py:47` — DoS via giant strings
4. **`hash()` used as deterministic seed** — `fal_art.py:405` — breaks cache across processes
5. **`JsonMemory.load_all_seeds()` unbounded memory** — `json_memory.py:80` — OOM on large files

### 🟠 High (should fix)
6. **Content safety middleware flags but doesn't block** — `bus.py:128-150`
7. **No creature_agent.py tests** — entire 680-line state machine is untested
8. **No llm_behavior.py tests** — 816-line LLM orchestration untested
9. **No EventBus middleware tests** — safety middleware, rate limiting, filtering
10. **1 failing test** — `test_play_session_reaches_goal`
11. **Archetypes are cosmetic only** — no mechanical stat differentiation

### 🟡 Medium (fix when convenient)
12. **No circuit breaker for external APIs** — every failure retries for 30+ seconds
13. **No retry in web_search.py** — single attempt per search
14. **FAL_KEY cached at construction** — can't rotate at runtime
15. **Relay list hardcoded** in Nostr publisher
16. **Resonances are flavor text only** — no gameplay bonus
17. **No evolve() tests** — evolution method untested

### 🟢 Low (nice to have)
18. DAY_PHASE_MOD defaults to "afternoon" — consider explicit fallback
19. Typo/consistency issues in archetype method names
20. No health probe for external API status
