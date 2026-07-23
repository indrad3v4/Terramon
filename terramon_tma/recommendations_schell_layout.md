# Terramon TMA — GameBoy-Style Single-Screen Layout
## Analysis via Schell's Lenses #25 (The Player), #47 (The Screen), #49 (The Problem Solver)

---

## Current Layout (scrolls off iPhone)

```
┌────────────────────────────────┐
│        TERRAMON HEADER         │  ~50px
├────────────────────────────────┤
│      text input field          │  ~50px
├────────────────────────────────┤
│  [📷 CAPTURE]  [✨ SUMMON]     │  ~50px
├────────────────────────────────┤
│   ✦ animated demo creature     │  ~200px  (or creature card ~400px)
├────────────────────────────────┤
│  Lv.1 · 0/5 to Tamer          │  ~60px
│  ████████░░░░░ XP bar         │
├────────────────────────────────┤
│  CREATURE CARD                 │  ~350px
│  (sigil, name, thought, lore,  │
│   reflection, insight, stats,  │
│   mint button, goal celebration)│
├────────────────────────────────┤
│  CARE PANEL                    │  ~300px
│  (3 stat bars, 4 buttons,      │
│   evolve button)               │
├────────────────────────────────┤
│  🜨 YOUR TERRA                 │  ~50px
│  0 creatures live here         │
├────────────────────────────────┤
│  terra grid (2-column cards)   │  variable
└────────────────────────────────┘
```

**Before we touch layout — the lenses:**

---

## 🔍 Lens #25 — The Lens of the Player

**Core questions:** Who is the player? What does she want in this moment? What does she need? What would she love?

**Applied to Terramon TMA:**
- The player checks in 1-3×/day (Tamagotchi rhythm, not a 2-hour gaming session)
- **What she wants right now:** type a quick thought → see the creature it becomes → check if the creature is okay → leave
- **What she would love:** immediacy (the creature reacts instantly), delight (the creature feels *hers*), anticipation (what will I get this time?)
- **What she DOESN'T want:** to scroll, to read paragraphs of text, to wait through animations, to manage a complex UI on a tiny screen

**Layout insight:** The app must serve the *micro-session* (15-30 seconds). The input + summon + creature result must be visible without any action. Everything else is a deeper layer.

---

## 🔍 Lens #47 — The Lens of the Screen

**Core questions:** What does the player see right now? What does she NEED to see? What does she see that she doesn't need? What does she need that she can't see?

**Applied to Terramon TMA:**
- **Needs to see right now:** the creature (the reward), the input (the action prompt), the SUMMON button (the trigger)
- **Sees but doesn't need right now:** the full terra grid (collection browsing is a separate intent), the goal celebration banner (once seen, it's clutter), the lengthy lore/reflection text, the geo location
- **Needs but can't see at a glance:** creature's hunger/energy/happiness (core Tamagotchi loop), whether she's close to next level, quick actions to care for the creature

**Layout insight:** The screen has ONE primary state (summon + see creature) and two secondary states (care mode, collection browsing). These must be switched via tabs, not stacked vertically.

---

## 🔍 Lens #49 — The Lens of the Problem Solver

**Core questions:** What problem is the player solving right now? What decisions is she making? Is the problem at the right difficulty level?

**Applied to Terramon TMA:**
The player solves three distinct problems, each at a different moment:

| Moment | Problem | Decision |
|--------|---------|----------|
| **Entry** | "What's on my mind?" → type it → SUMMON → "Who emerged?" | What to type? |
| **Check-in** | "Is my creature okay?" → see stats → feed/play/rest | Which action? |
| **Browse** | "What have I collected?" → scroll terra → reflect on journey | Which creature? |

These are three **mutually exclusive** problem states — the player isn't solving all three simultaneously. The current layout presents them as one long list, forcing the player to scroll between problems.

**Layout insight:** Tabs map 1:1 to problem states. The home tab is the *only* state that scrolls (briefly — the summon result). Care and Terra are dedicated tab views.

---

## 🎮 GameBoy-Style Single-Screen Layout

Inspired by Pokémon Gold/Silver — three persistent zones, zero scrolling on the home screen:

```
┌────────────────────────────────┐
│  ████████████████████████████  │  ~8px  — thin status bar (always visible)
│  Lv.3  ████████░░ 240/300 XP  │         level + XP progress
├────────────────────────────────┤
│                                │
│         ★ (sigil/art)          │
│                                │
│       "Magician"               │  TOP ZONE (~40%)
│       ✦ Legendary              │  Creature Display
│                                │  Always shows current creature
│    "Transforms the ordinary"   │  (or breathing demo shadow when empty)
│                                │
│        ▼ INTELLIGENCE 78%      │  one-line insight below
│                                │
├────────────────────────────────┤
│  what's on your mind?      🔮  │  INPUT + SUMMON (always accessible)
│  ┌─────────────────────────┐  │  ~60px — compact bar
│  │ ✨ SUMMON                │  │
│  └─────────────────────────┘  │  MIDDLE ZONE (~30%)
│                                │  Context-switches by tab:
│  ┌────┬────┬────┬────┐        │  HOME: input + summon
│  │ 🍽️ │ 🎮 │ 💬 │ 💤 │        │  CARE: 4 interaction buttons + stats
│  └────┴────┴────┴────┘        │  TERRA: scrollable creature grid
│                                │
├────────────────────────────────┤
│  [CREATURE] [CARE] [TERRA]    │  BOTTOM ZONE (~20%)
│         🔵 ○ ○                │  Tab bar — always visible
│                                │  Active tab highlighted
└────────────────────────────────┘
```

**Pixel budget (iPhone SE: 375×667 — usable ~375×580 after chrome):**

| Zone | Height | Content |
|------|--------|---------|
| Status bar | ~8px | Thin line with level + XP |
| **TOP** (creature) | ~230px | Sigil, name, rarity, one-line lore, intelligence |
| **MIDDLE** (action area) | ~170px | Input bar + SUMMON button (home) — or care buttons + stats (care) — or scrollable grid (terra) |
| **BOTTOM** (tabs) | ~170px | 3 tab buttons with labels |

**Total: ~580px — fits iPhone SE/8/XR/12/14 without scrolling.**

---

## 5 Specific Recommendations

### Recommendation 1: Three-Zone Permanent Layout (No Scroll on Home)

Replace the linear `vstack` with a **grid-style layout** that enforces three zones:

- **Zone 1 (top 40%)** — `demo_creature()` (empty) or stripped-down `creature_card()` showing only: sigil, name, rarity badge, one-line lore, intelligence %. Remove: full thought quote, reflection, insight paragraph, geo location, mint button, goal celebration.
- **Zone 2 (middle 30%)** — Contextual action area. Always includes a compact input bar + SUMMON button. Below it, 4 micro-buttons (🍽️ 🎮 💬 💤) for quick care — no stat bars here (those live in the CARE tab).
- **Zone 3 (bottom 20%)** — 3-tab navigation: CREATURE (home), CARE (stats + interaction), TERRA (collection). Active tab re-renders Zone 2 content only.

**Why (Lens #25 + #47):** The player's primary intent (summon → see creature) must be *instantly satisfiable*. Zone 1 is the reward (the creature), Zone 2 is the action (summon/care), Zone 3 is the navigation. This maps to the player's mental model.

---

### Recommendation 2: Strip Creature Card to Essential Display

Current `creature_card()` shows **11 items** vertically. Strip to **5**:

| Keep | Remove |
|------|--------|
| Sigil (large, with glow) | Full thought quote |
| Creature name | Full lore paragraph |
| Rarity badge (colored dot + name) | Reflection text |
| One-line archetype lore | Insight paragraph |
| Intelligence % as compact badge | Geo location |
| | Mint button |
| | Goal celebration banner |

**Why (Lens #47):** The screen real estate is the scarcest resource. The creature *is* the reward — show it large, let the name + rarity + intelligence % convey the core info. The full thought, reflection, and insight are accessible by tapping the creature card (zoom-in modal). The goal celebration fires once, then disappears — it does not need permanent real estate.

---

### Recommendation 3: Tabs as Three Problem States (Not Three Views of the Same Thing)

Map tabs to the player's three distinct problem moments:

| Tab | Label | Zone 2 Content | When |
|-----|-------|----------------|------|
| 1 | **SUMMON** 🜨 | Input bar + SUMMON button + 4 quick-care micro-buttons | Default — the "what's on my mind?" moment |
| 2 | **CARE** ❤️ | 3 stat bars (hunger/energy/happiness) + same 4 care buttons + EVOLVE button | Check-in — "is my creature okay?" |
| 3 | **TERRA** 🌍 | Scrollable 2-column creature grid + collection count | Browse — "what have I collected?" |

**Why (Lens #49):** Each tab solves exactly one problem. The player never has to scan irrelevant content. The SUMMON tab is the default because that's the core loop entry point. The CARE tab shows full stat bars (hidden on the SUMMON tab to save space). The TERRA tab is a full collection browser.

The bottom tab bar always shows which tab is active with a dot indicator (GameBoy-style: `● ○ ○`).

---

### Recommendation 4: Make the Core Loop Visible at a Glance with a "Loop Bar"

Between Zone 1 and Zone 2, add a **single-line loop status indicator**:

```
📝 THOUGHT → 🜨 CREATURE → ❤️ CARE
     ● active         ○ ready       ○ ready
```

- The active step is highlighted
- Completed steps show a checkmark
- This makes the 3-step loop explicit to NEW users (Lens #25: they need to understand the game)
- For returning users, it subtly reinforces the loop structure

**Why (Lens #25):** First-time players don't know the game loop. Veteran players benefit from a glanceable state machine. The loop bar is ~20px — nearly free in screen space.

Implementation: 3 tiny icons in a row with a connecting line: `📝 → ✦ → ❤️`. Current step glows amber.

---

### Recommendation 5: Compact Input + SUMMON as a Single Visual Unit

Merge the current separated input and buttons into a **single cohesive bar**:

```
┌────────────────────────────────┐
│ what's on your mind?       🔮  │  ← inline input with micro-icon
├────────────────────────────────┤
│ ✨ SUMMON your thought         │  ← full-width pill button below
└────────────────────────────────┘
```

- Remove the separate `📷 CAPTURE` button (move it into a sub-action or hide until photo mode is real)
- The input field has an inline micro-button (🔮) for keyboard-submit on mobile
- The SUMMON button is a full-width pill below the input — one tap after typing
- When the input field gets focus, the SUMMON button pulses gently (subtle glow animation) — visual cue that typing → summoning is the flow

**Why (Lens #25 + #47):** The CAPTURE button is a dead feature (photo mode is `placeholder: true` with no backend). Keeping two buttons of equal weight confuses the player about the primary action. Making SUMMON the *only* primary action reduces decision friction. The combined input+button unit takes ~80px total instead of the current ~100px.

---

## Implementation Notes

### Zone heights in Reflex (responsive, max-width: 390px):

```python
# Top zone: creature display — fixed height via min/max
rx.box(
    rx.vstack(
        # sigil, name, rarity, lore, intelligence
        ...
    ),
    min_height="220px",
    max_height="240px",
    width="100%",
    max_width="390px",
)

# Middle zone: context-switches based on active tab
rx.match(
    active_tab,
    ("summon", summon_zone()),
    ("care", care_zone()),
    ("terra", terra_zone()),
)

# Bottom zone: tab bar — GameBoy-style 3 tabs
rx.hstack(
    tab_button("🜨 SUMMON", "summon"),
    tab_button("❤️ CARE", "care"),
    tab_button("🌍 TERRA", "terra"),
    width="100%",
    justify="around",
    padding="0.8em 0",
    border_top="1px solid #27272a",
)
```

### State additions needed:

```python
class TerramonState(rx.State):
    active_tab: str = "summon"  # "summon" | "care" | "terra"
    
    @rx.event
    def set_tab(self, tab: str):
        self.active_tab = tab
```

### What gets removed from existing UI:
- Full `progress_header()` — collapsed to thin status bar at very top
- `creature_care_panel()` — moved to CARE tab
- Terra grid heading + divider — moved to TERRA tab
- CAPTURE button — hidden until photo mode ships
- Goal celebration banner — fires once as toast/overlay, then gone
- Mint button — moved to creature detail modal (tap creature to see)
- Geo location line — moved to creature detail modal
- Full thought quote on card — shown in input history or tap-to-expand
- Full reflection paragraph — moved to creature detail modal

---

## Summary: Before vs After

| Metric | Current | Recommended |
|--------|---------|-------------|
| Vertical scroll on home | ~1500px (must scroll) | 0px (fits iPhone SE) |
| Core loop visible at a glance | ❌ hidden after scroll | ✅ always in Zones 1-2 |
| Primary action clarity | ❌ SUMMON + CAPTURE compete | ✅ SUMMON is the only primary |
| Secondary state access | ❌ all stacked vertically | ✅ tabs switch between modes |
| Creature as reward | ❌ buried in card details | ✅ Zone 1 is always the creature |
| Screen real estate efficiency | ~30% used for core loop | ~70% used for core loop |

---

*Analysis by Hermes Agent via Schell's Lenses #25 (The Player), #47 (The Screen), #49 (The Problem Solver)*
