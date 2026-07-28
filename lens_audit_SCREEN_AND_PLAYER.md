# Schell's Screen & Player Lens Cluster — Terramon TMA Audit

**12 Lenses Applied**: #25 Goals, #47 Balance, #49 Visible Progress, #53 Control, #54 Physical Interface, #55 Virtual Interface, #56 Transparency, #57 Feedback, #58 Juiciness, #59 Channels/Dimensions, #60 Modes, #61 Interest Curve

**Target**: `/root/Terramon/terramon_tma/terramon_tma.py` (1897 lines) + `/root/Terramon/terramon/domain/creature_agent.py` (579 lines)

---

## Lens #25: Goals
> *What are the player's goals? Are they clear, compelling, and achievable?*

### #25-A — Hidden long-term goal (terra:line 1518-1552)
**Finding**: The only progress indicator in the header bar is "Lv.X · Y/5 to Tamer" with no explanation of what "to Tamer" means or what happens at 5/5. The goal of collecting 5 distinct archetypes is buried in the progress_header() and only visible as a fraction.
**Fix**: Add a one-line tooltip or subtitle: "Collect 5 unique archetypes to awaken the terra." Show progress as a visual ring or step indicator (★ empty → ★ filled) near the header.

### #25-B — Evolution goal has no visible target (terra:line 241-250)
**Finding**: `evolution_hint` shows "Need X more ❤️ Happiness" or "X more levels to evolve" but the player never sees what the evolution requirement thresholds actually are (min_level=10, min_happiness=70, min_xp_total=500, insight_diversity=3 from creature_agent.py:156-162).
**Fix**: Show the evolution requirements as a checklist: "☐ Level 10+ · ☐ ❤️ 70+ · ☐ XP 500+ · ☐ 3 Archetypes met". This turns a vague hint into a clear goal.

### #25-C — MINT goal is confusing (terra:line 555-559, 926-945)
**Finding**: The MINT button shows "locked · train more" when can_mint=False, but "train more" is vague — the player doesn't know what unlocks minting (Bayesian confidence > 50%).
**Fix**: Show exact unlock condition: "Mint at 50%+ Intelligence (currently X%)" with a progress ring.

---

## Lens #47: Balance
> *Are game elements balanced? Are there hardcoded values that create unfair or broken scenarios?*

### #47-A — Hardcoded `goal_distinct=5` (terra:line 86, 456)
**Finding**: `PlayerProgress(goal_distinct=5)` hardcoded in two places (line 86 module init, line 456 load_terra). This is the fundamental progression gate — 5 distinct archetypes to "awaken the terra" — but is a magic number.
**Fix**: Lift to a config constant at module top: `GOAL_DISTINCT = 5`. This at least makes it visible and changeable without hunting.

### #47-B — Hardcoded stat initial values (terra:line 336-338, creature_agent.py:192-194)
**Finding**: After summon: `agent_hunger=80, agent_energy=80, agent_happiness=60`. In CreatureAgent defaults: `hunger=80, energy=80, happiness=60`. These are repeated in at least 3 places. If one changes, the others drift.
**Fix**: Define a single constant dict `STARTING_STATS = {"hunger": 80, "energy": 80, "happiness": 60}` in creature_agent.py and reference it everywhere.

### #47-C — Stat decay capped at 48 ticks (terra:line 602)
**Finding**: `ticks = min(int(hours), 48)` — if a player doesn't return for 48+ hours, decay is capped at 48 ticks (about 2 days of simulation). A creature left for a week hits the same state as one left for 2 days. This is an artificial balance limit that creates a perverse incentive to ignore the creature.
**Fix**: Either raise cap to 168 (1 week) or implement logarithmic decay where the first 24 ticks matter most and later ticks matter less, making long absence still meaningful but not punishing.

### #47-D — Hardcoded color_schema typo (terra:line 1713)
**Finding**: `color_schema="gray"` — this is a typo (should be `color_scheme`). Reflex silently ignores unknown props, so the text input field has no color scheme applied and falls to default styling that may not match the dark theme.
**Fix**: Change to `color_scheme="gray"` or `color_scheme="slate"`.

### #47-E — Hardcoded price model (terra:line 680-686)
**Finding**: `_price_for()` returns hardcoded sats: common=0, uncommon=0, rare=15, legendary=25. Two rarities are free, two cost. This creates a weird "why bother pricing common/uncommon at 0?" dead zone.
**Fix**: Either price all rarities (1/3/15/25) so every mint has meaning, or make common/uncommon genuinely free and rare/legendary the only mint targets. The current 0/0/15/25 feels like placeholder values.

---

## Lens #49: Visible Progress
> *Can the player see how they're progressing at all times?*

### #49-A — XP bar visible but level-up is invisible (terra:line 747-789)
**Finding**: The XP bar animates smoothly (line 768: `transition: width 0.4s ease`), but when a level-up happens, there's no visual event — no flash, no text, no particle effect. The player only knows they leveled because the number changes.
**Fix**: On level-up, trigger a brief overlay or flash animation: "★ Level X!" with a 2-second auto-dismiss. Store `previous_level` and compare in summon().

### #49-B — Evolution progress bar has no milestone markers (terra:line 1082-1100)
**Finding**: The evolution probability is shown as a percentage bar (0-100%), but the player doesn't know what probability corresponds to "ready." The `can_evolve` threshold is 50% (creature_agent.py:229), but the bar has no visible tick mark or color change at 50%.
**Fix**: Add a dashed vertical indicator line at 50% on the evolution bar, and change the bar color from amber to gold when probability > 50%.

### #49-C — Terra grid shows count but no progress toward next milestone (terra:line 1826-1834)
**Finding**: The Terra tab shows "X unique · Y total" but provides no context about what comes after reaching 5/5. Post-goal (Tamer status), there's no next milestone displayed.
**Fix**: Add a "Next: Collect 10 archetypes for ★★" or show a second ring of progression. Currently the progression system dead-ends.

---

## Lens #53: Control
> *Does the player feel in control? Are there confusing or non-responsive controls?*

### #53-A — SUMMON button doesn't disable while summoning (terra:line 1719-1725)
**Finding**: While `summoning=True`, the button text changes to "🔮" via `rx.cond`, but the button is NOT disabled — a player can click it multiple times during the ~0.5-3s LLM call. The `summon()` method guards with `if not text: return` but doesn't check `self.summoning`.
**Fix**: Add `is_disabled=TerramonState.summoning` to the SUMMON button. Also add an early return guard at the top of `summon()`: `if self.summoning: return`.

### #53-B — Care panel buttons triggered on dead agent (terra:line 1006-1007)
**Finding**: The care panel is gated by `TerramonState.has_summoned`, but within the panel the feed/play/rest/talk buttons modify `agent_hunger/energy/happiness` that are initialized ONLY during `summon()` (line 336-338). If `load_terra()` runs but no summon happened yet, these stay at 0 and stat bars show 0%.
**Fix**: The `_init_agent_stats()` method (line 490-498) tries to fix this but is called per-action. Instead, initialize stats to default in `load_terra()`.

### #53-C — "locked · train more" is dead text (terra:line 942)
**Finding**: When `can_mint=False` and `price_sats>0`, the player sees `rx.text("locked · train more", ...)` — but this is just text with no action, no tooltip, no path forward.
**Fix**: Make it a clickable hint: `rx.button("🔒 Train to unlock Mint", on_click=...scroll_to_care_tab...)` that switches the active tab to "care" so the player can interact more.

### #53-D — Scout button runs but result appears silently (terra:line 645-666, 1738-1755)
**Finding**: The Scout button shows ⏳ while running, but when the result arrives (set via threading), there's no notification — the output box just appears silently. The player may not notice.
**Fix**: Add a brief flash highlight on the scout result box when new content arrives, or a small "✓ Scout complete" badge.

---

## Lens #54: Physical Interface
> *Is the interface comfortable to use? Touch targets, readability, spacing.*

### #54-A — Bottom nav buttons have very small touch targets (terra:line 1764-1798)
**Finding**: The three nav buttons at the bottom are `width="30%"` with `font_size="0.7em"` text and emoji icons at `font_size="1em"`. On mobile, these are ~30-40px tall buttons — below the recommended 44px minimum touch target for iOS/Android.
**Fix**: Increase button size to `size="3"` or add `min_height="44px"` and `padding="0.6em"` to meet accessibility standards.

### #54-B — Text input placeholder doesn't fit TMA context (terra:line 1702-1714)
**Finding**: The placeholder alternates between "caption this moment..." (photo_mode) and "i'm afraid of the interview..." (default). The example text is emotionally loaded (fear/anxiety) which may be off-putting. It also doesn't demonstrate the creature-summoning mechanic.
**Fix**: Use neutral evocative examples: "thoughts become creatures..." or "describe a memory..." Keeping "i'm afraid of the interview" narrows the emotional range the player feels invited to share.

### #54-C — Font sizes cascade too small (terra:line 719-720, 880-881, 958-960)
**Finding**: Some text elements go as low as `font_size="0.6em"` and `font_size="0.55em"` (line 1598-1599, 1609). On a mobile screen with base 16px, 0.55em = ~8.8px — unreadable for many users.
**Fix**: Floor font sizes at 0.7em (~11px). For secondary information, use color (#6b7280) to de-emphasize rather than micro-fonts.

### #54-D — No safe-area insets for modern phones (terra:line 1861-1865)
**Finding**: The outer container uses `height="100vh"` with no `padding` for notch/dynamic island/bottom bar on modern iPhones and Android phones. The bottom nav buttons may be hidden behind the system navigation bar.
**Fix**: Add `padding_bottom="env(safe-area-inset-bottom)"` and `padding_top="env(safe-area-inset-top)"`. Reflex supports these through style props or CSS-injection.

---

## Lens #55: Virtual Interface
> *Does the interface clearly communicate data and state? Information hierarchy.*

### #55-A — Intelligence score shown as raw percentage with no context (terra:line 868-873)
**Finding**: "Intelligence: 87%" appears below the creature card. The player has no idea what this measures — Bayesian confidence? Archetype classifier score? Token confidence? Three different confidence values exist (token_confidence line 402, intelligence line 350, archetype_probs line 353) and only "Intelligence" is shown.
**Fix**: Rename to "Archetype Match: 87%" or show a small info icon with tooltip explaining "How confident we are in your creature's archetype."

### #55-B — Token count display is over-technical (terra:line 875-884)
**Finding**: "tokens: 12 | archetype: Hero | confidence: 87.5%" uses NLP jargon that means nothing to a game player. This is a developer debug leak into the game UI.
**Fix**: Gate behind a debug mode or dev flag. Replace with a simpler, diegetic stat like "Thought Depth: 12" or remove entirely.

### #55-C — Stat bars have no labels on the bar itself (terra:line 1045-1081)
**Finding**: The care panel shows "🍽️ Hunger" label above an amber bar, "⚡ Energy" above a green bar, "❤️ Happiness" above a red bar. But the bar itself has no numeric overlay — the player must guess the numeric value from the bar width.
**Fix**: Show the number on the bar: `rx.text(state_var.to_string() + "%", font_size="0.6em", color="#f5f5f5")` overlaid or right-aligned after the bar.

### #55-D — Day/night phase shown but doesn't do anything visible (terra:line 1022-1044)
**Finding**: The UI shows "☀️ Day ·" or "🌙 Night ·" with the creature state, but the day phase affects decay rates (creature_agent.py:126-131) without any visible feedback. The player sees a label but can't perceive its gameplay impact.
**Fix**: Show a subtle modifier badge: "🌙 Night (resting — energy decays slower)" or apply a visual filter/dim to the card at night.

---

## Lens #56: Transparency
> *Does the player understand what's happening behind the scenes?*

### #56-A — LLM greeting silently fails (terra:line 298-314)
**Finding**: The LLM-generated creature greeting is fetched inside a `try/except` that logs a warning and sets `self.creature_greeting = ""`. If the LLM is down or slow, the greeting just doesn't appear with no indication why.
**Fix**: Add a fallback greeting stored locally per-archetype so there's never silence. If LLM returns, swap. The player should never see an empty bubble — either the real greeting or a canned one.

### #56-B — Portrait generation is fire-and-forget (terra:line 437-448)
**Finding**: The FAL.ai portrait generation runs in a daemon thread with `log.debug` on failure. The player never knows if a portrait was generated, failed, or is still loading. The sigil fallback shows without explanation.
**Fix**: Add a loading indicator while portrait is generating, and a retry button if it fails. Currently the portrait silently doesn't appear.

### #56-C — "free summon" text is misleading (terra:line 944)
**Finding**: When `price_sats == 0`, the card shows `rx.text("free summon", ...)`. This implies the current creature is free to mint, but actually common/uncommon creatures are free — but minting still requires Telegram Stars infrastructure. The text conflates "this summon was free" with "this creature is free to mint."
**Fix**: Change to "Free creature — upgrade with MINT" or remove the price_sats=0 case entirely.

### #56-D — Safety flag shown without explanation (terra:line 955-963)
**Finding**: "content advisory: [reason]" appears on the creature card when safety_flagged. The player doesn't know what "safety" means in this context or what consequence it has.
**Fix**: Either remove (it has no gameplay effect currently) or add context: "Content note: [reason]. This affects nothing — all thoughts welcome."

---

## Lens #57: Feedback
> *Does every action produce appropriate, timely feedback?*

### #57-A — Mint action produces no result (terra:line 555-559)
**Finding**: `mint_creature()` sets `self.agent_message` to "⚡ Minting..." but never completes the mint — it's a stub. The player sees "Minting..." and nothing happens.
**Fix**: Either implement the full mint flow or remove the button. A stub button that hangs is worse than no button.

### #57-B — Capture mode has no visual mode indicator (terra:line 469-471, 1702-1706)
**Finding**: Clicking 📷 sets `photo_mode=True`, which changes the input placeholder to "caption this moment..." but there's no visual change to indicate the app entered photo mode (no camera UI, no frame, no shutter button).
**Fix**: Since photo mode is simulated (MVP dead mode), either fully remove the 📷 button or add a visual overlay: a thin white viewfinder frame around the creature area + "Tap to capture" hint.

### #57-C — No haptic feedback on any action
**Finding**: None of the 15+ clickable buttons trigger any Telegram haptic feedback (`Telegram.WebApp.HapticFeedback.impactOccurred()`). On mobile, this makes interactions feel flat.
**Fix**: Use `rx.call_script("Telegram.WebApp.HapticFeedback.impactOccurred('medium')")` on all primary actions (SUMMON, FEED, PLAY, EVOLVE).

### #57-D — Share action silences on repeat clicks (terra:line 574-586)
**Finding**: `share_creature()` sets `self.agent_message` to "📤 Creature card copied!" but this overwrites the previous `agent_message` (which might be the creature's speech), causing state to flicker.
**Fix**: Use a separate `share_notification` state var, or use a temporary toast that auto-dismisses. Currently shout from the creature gets eaten by the share confirmation.

---

## Lens #58: Juiciness
> *Are animations and effects satisfying? Does the interface feel alive?*

### #58-A — Summon has a loading icon but no animation chain (terra:line 265, 435, 1719-1725)
**Finding**: The summon button shows 🔮 during loading, then the creature card appears instantly via `self.summoning = False` (line 435) with only a CSS `transition: opacity 0.35s ease` on the card container (line 1000). There's no animation sequence: no "writing in progress" → "portal opening" → "creature emerges" chain.
**Fix**: Implement a 3-phase summon animation:
1. Input text dissolves upward (0.3s fade+translate)
2. Portal effect: expanding circle with glow (0.4s scale)
3. Creature card slides in from bottom (0.3s translateY+opacity)
Use state vars `summon_phase: int = 0` and CSS `animation` props.

### #58-B — Evolution button has no visual payoff (terra:line 1138-1140)
**Finding**: The EVOLVE button triggers `evolve_agent()` which increments evolution and sets a message, but the UI doesn't animate — no shimmer, no flash, no scale burst. The creature_agent.py evolve() (line 446-465) says "✦ Evolved! It shimmers and transforms." but the TMA doesn't show this visually.
**Fix**: On evolve trigger: 1-second gold shimmer overlay on the creature card, scale-up to 1.1× then back down, particle-like emoji burst (★★★★), then show the new evolution stage.

### #58-C — Care buttons have no activation animation (terra:line 1120-1136)
**Finding**: Clicking Feed/Play/Rest/Talk updates stat bars with a CSS `width` transition (0.3s ease), but the button itself has no press animation — no ripple, no scale-press, no glow.
**Fix**: Add `_active={"transform": "scale(0.95)"}` to all care buttons to give physical press feedback.

### #58-D — XP bar is the only animated element — more elements need life (terra:line 763-769)
**Finding**: Only the XP bar has a width transition. Stat bars in the care panel (line 1049-1077) also animate, but the creature card, sigil, and header all appear statically.
**Fix**: Add a subtle ambient animation to the sigil: slow color pulse matching the rarity glow, or a gentle rotation (10deg oscillation over 4s) to make the creature feel alive even when idle.

### #58-E — `fadeIn` keyframe referenced but never defined (terra:line 1501)
**Finding**: The celebration overlay uses `style={"animation": "fadeIn 0.5s ease"}` (line 1501), but `@keyframes fadeIn` is never defined in any injected `<style>` block. `_CELEBRATION_STYLE` (line 1451-1457) only defines `celebrationSparkle`. This means the fade-in animation silently fails — the overlay snaps into existence rather than fading in.
**Fix**: Add `@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }` to `_CELEBRATION_STYLE` or inject it via a separate `<style>` block in the `index()` component.

---

## Lens #59: Channels/Dimensions
> *Are different information channels (text, color, sound, space, motion) used effectively?*

### #59-A — Rarity only uses visual channel (color + sigil) (terra:line 91-108)
**Finding**: Rarity differentiation uses color (gray/green/blue/gold) and sigil (·/✦/✧/★). These are both visual-only. Color-blind players cannot distinguish common (gray) from rare (blue) reliably. No sound, no animation speed, no size difference.
**Fix**: Add a second dimension: higher rarity creatures pulse faster (shorter animation duration), have a larger sigil, or include a text badge. Use shape differentiation (common=circle, uncommon=diamond, rare=star, legendary=crown) for color-blind accessibility.

### #59-B — Creature state uses text only — no visual state change (terra:line 1040-1041)
**Finding**: `TerramonState.creature_state.upper()` is shown as raw text ("HAPPY", "HUNGRY", "TIRED", "SICK", "EVOLVING"). This is the least effective way to communicate state. The player has to read and parse a word while simultaneously looking at stat bars.
**Fix**: Map states to distinct visual treatments:
- HAPPY → sigil glows steadily
- HUNGRY → sigil pulses amber (urgent)
- TIRED → sigil dims to 50% opacity
- SICK → sigil wobbles/desaturates
- EVOLVING → sigil sparkles gold

### #59-C — Memory greeting channel confusion (terra:line 316-332, 852-858)
**Finding**: The memory greeting ("You were just here..." / "Almost a day...") appears as small italic text in the creature card, same channel as the creature's own speech. This makes it unclear whether the creature is speaking or the system is.
**Fix**: Use a distinct visual style: put memory greetings in a monospace/tag-like badge (`rx.badge(...)`) with a clock icon, clearly separated from the creature's voice bubble.

### #59-D — All buttons share the same interaction channel (terra:line 1120-1140)
**Finding**: The 4 care buttons (Feed/Play/Rest/Talk) use different color_schemes (amber/green/blue/purple) but have identical shape, size, and interaction pattern. Evolution buttons and MINT also look similar.
**Fix**: Differentiate by dimension: destructive/urgent buttons get a different border style (dashed), primary actions get solid fill, secondary actions get outline/tinted. Currently everything is "soft" variant, creating visual flatness.

---

## Lens #60: Modes
> *Are interface modes clear? Are there dead or confusing modes?*

### #60-A — photo_mode is a dead mode (terra:line 169-170, 469-471, 1702-1706)
**Finding**: `photo_mode` is set to True by `capture()`, but there is NO photo capture UI, no camera integration, and no way to exit photo mode except clicking 📷 again (which toggles nothing — `set_thought` doesn't reset photo_mode). The mode changes only the placeholder text. This is a dead interface mode.
**Fix**: Either implement the camera overlay (show viewfinder frame, capture button, confirmation flow) or remove the 📷 button and photo_mode state entirely. A mode that does nothing is worse than no mode.

### #60-B — active_tab toggle behavior is non-standard (terra:line 474-476)
**Finding**: `set_tab` toggles: clicking an already-active tab closes it (sets to ""). This is unusual — standard bottom navs keep the current tab active. The empty tab state shows a blank area (rx.fragment()) between the action buttons and bottom nav, which is dead space.
**Fix**: Either keep the last tab active after first click (no toggle-off), or fill the empty state with something useful (the demo creature, or "Tap a tab to explore" hint).

### #60-C — Celebration overlay blocks ALL interaction (terra:line 1464-1502, 1801-1809)
**Finding**: The `celebration_component()` overlay has `z_index=900` and a semi-transparent backdrop, but it does NOT prevent interaction with the buttons underneath. The player can click SUMMON or FEED while the celebration is showing, causing state desync.
**Fix**: When celebration is showing, render a transparent overlay that catches clicks, or disable all interactive elements underneath. Also add a "tap anywhere to dismiss" behavior (rx.box with on_click, full-screen).

### #60-D — Scout mode shows no status while running (terra:line 218-219, 645-666)
**Finding**: `scout_running=True` shows ⏳ on the button, but the button remains clickable and the scout can be re-triggered (the guard `if self.scout_running: return` only blocks in Python, but the browser can queue requests).
**Fix**: Add `is_disabled=TerramonState.scout_running` to the Scout button, and show a "Thinking..." spinner text rather than a static ⏳.

---

## Lens #61: Interest Curve
> *Does the experience build, sustain, and release tension appropriately?*

### #61-A — No introductory ramp — player sees everything at once (terra:line 1505-1509)
**Finding**: The entire UI (header, creature zone, XP bar, input, bottom nav) loads simultaneously. There's no gradual reveal, no progressive disclosure. The tutorial overlay (line 1264-1343) helps, but the underlying UI is fully visible through the semi-transparent backdrop.
**Fix**: Stage the UI reveal: first show the input prompt + demo creature (the "shadow creature" from demo_creature()), then after first summon, reveal the header + XP bar + bottom nav with staggered fade-ins (200ms delay between elements).

### #61-B — Post-goal plateau — no next milestone (terra:line 968-987, 1801-1809)
**Finding**: After reaching Tamer status (5/5), the celebration fires, the star badge appears, but then... nothing changes. There's no new goal, no prestige mechanic, no next tier. The interest curve flatlines after the celebration.
**Fix**: Introduce a post-Tamer loop: "★ Tamer unlocked — Now collect 12 unique creatures for the ★★ Legendary tier." Or trigger a new game element (Scout unlocks permanently, Multi-creature team management, World map exploration). The player needs a reason to keep playing after the victory lap.

### #61-C — Stat decay creates negative tension without relief (terra:line 588-623, creature_agent.py:310-399)
**Finding**: The tick decay system (48 ticks, 3% EMA per tick + state-dependent decay) means creatures steadily decline when the app is closed. There's no mechanic to mitigate this — no "auto-care while away," no items, no shelter system. The player returns to a sad creature with no way to prevent it.
**Fix**: Implement a basic "terra caretaker" passive feature: if the creature was happy when the player left, it auto-grazes (slower decay). Or add a "❄️ Stasis" button that pauses decay for 24h (cooldown).

### #61-D — No reward escalation loop (terra:line 430-434, 689-704)
**Finding**: Every summon is equally weighted — there's no increasing reward for playing longer. The first summon and the 50th summon produce the same card with the same visual treatment (sigil + lore + XP gain). No streaks, no bonuses, no special rewards for consecutive play days.
**Fix**: Add a summon streak counter. Every 3rd consecutive day summoning gives a bonus XP multiplier (1.5×) or increases rare/legendary probability slightly. Display a streak flame 🔥 in the header.

---

## Summary by Lens

| Lens | Priority | Findings |
|------|----------|----------|
| #25 Goals | MEDIUM | 3 findings — unclear long-term goal, hidden evolution reqs, confusing MINT gate |
| #47 Balance | HIGH | 5 findings — hardcoded values, stat initialization drift, decay cap, typo in prop name, broken price model |
| #49 Visible Progress | MEDIUM | 3 findings — invisible level-up, missing milestone markers, post-goal dead end |
| #53 Control | HIGH | 4 findings — summon double-click bug, dead stat initialization, locked-but-no-path, silent scout result |
| #54 Physical Interface | HIGH | 4 findings — small touch targets, loaded placeholder, unreadable micro-fonts, no safe-area |
| #55 Virtual Interface | MEDIUM | 4 findings — opaque intelligence score, debug leak, no bar overlays, invisible night effect |
| #56 Transparency | MEDIUM | 4 findings — silent LLM failure, invisible portrait gen, misleading price labels, unexplained safety flag |
| #57 Feedback | HIGH | 4 findings — dead mint stub, dead photo mode, no haptic feedback, share notification eats creature speech |
| #58 Juiciness | HIGH | 4 findings — no summon animation chain, no evolution payoff, no press feedback, static sigil |
| #59 Channels/Dimensions | MEDIUM | 4 findings — color-only rarity, text-only state, channel confusion for memory, flat button variety |
| #60 Modes | HIGH | 4 findings — dead photo_mode, non-standard tab toggle, celebration doesn't trap clicks, scout double-fire |
| #61 Interest Curve | HIGH | 4 findings — no introductory ramp, post-goal plateau, negative-only decay, no escalation loop |

**Total: 48 specific findings across 12 lenses, each with file:line citation and concrete fix recommendation.**
