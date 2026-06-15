---
name: CCGS
description: Claude Code Game Studios — 49 specialised game dev agents, 72 skills, 12 hooks, 11 rules adapted for Terramon. Use when designing agent architecture, world systems, game mechanics, or procedural generation in Python + Reflex.
---

# CCGS — Claude Code Game Studios for Terramon

Full game dev studio framework adapted for Terramon (Python/Reflex/HF). Source: https://github.com/Donchitos/Claude-Code-Game-Studios

## What's Installed

Cloned at `.agents/skills/ccgs/`:
- **49 agents** in `.claude/agents/`
- **73 skills** in `.claude/skills/`
- **12 hooks** in `.claude/hooks/`
- **11 rules** in `.claude/rules/`

## Agent Roster (49)

### Tier 1 — Directors
- creative-director — vision, tone, design philosophy
- technical-director — architecture, technology choices
- producer — process, milestones, coordination

### Tier 2 — Department Leads
- game-designer — core mechanics, GDDs
- lead-programmer — code standards, code reviews
- art-director — visual style, art bible
- audio-director — sound design, music
- narrative-director — story, characters, lore
- qa-lead — testing strategy, quality gates
- release-manager — build, deploy, release
- localization-lead — translation, cultural adaptation

### Tier 3 — Specialists
- gameplay-programmer — player mechanics, combat, physics
- engine-programmer — engine integration, optimization
- ai-programmer — NPC behaviour, enemy AI
- network-programmer — multiplayer, replication
- tools-programmer — editor tools, pipeline
- ui-programmer — UI/UX frameworks
- systems-designer — game systems, progression
- level-designer — level layout, encounter design
- economy-designer — currencies, balance, rewards
- technical-artist — shaders, materials, pipeline
- sound-designer — SFX, ambient, foley
- writer — dialogue, quest text, lore
- world-builder — open world, environment design
- ux-designer — player experience, accessibility
- prototyper — rapid prototyping, vertical slices
- performance-analyst — profiling, optimisation
- devops-engineer — CI/CD, infrastructure
- analytics-engineer — telemetry, player data
- security-engineer — anti-cheat, data protection
- qa-tester — manual/automated testing
- accessibility-specialist — inclusive design
- live-ops-designer — events, seasons, retention
- community-manager — social, feedback, moderation

### Engine Specialists (Godot/Unity/Unreal)
- godot-specialist, godot-gdscript-specialist, godot-gdextension-specialist, godot-csharp-specialist, godot-shader-specialist
- unity-specialist, unity-dots-specialist, unity-shader-specialist, unity-addressables-specialist, unity-ui-specialist
- unreal-specialist, ue-gas-specialist, ue-blueprint-specialist, ue-replication-specialist, ue-umg-specialist

## Skills (73)

### Onboarding & Navigation
/start, /help, /project-stage-detect, /setup-engine, /adopt

### Game Design
/brainstorm, /map-systems, /design-system, /quick-design, /review-all-gdds, /propagate-design-change

### Art & Assets
/art-bible, /asset-spec, /asset-audit

### UX & Interface
/ux-design, /ux-review

### Architecture
/create-architecture, /architecture-decision, /architecture-review, /create-control-manifest

### Stories & Sprints
/create-epics, /create-stories, /dev-story, /sprint-plan, /sprint-status, /story-readiness, /story-done, /estimate

### Reviews & Analysis
/design-review, /code-review, /balance-check, /content-audit, /scope-check, /perf-profile, /tech-debt, /gate-check, /consistency-check, /security-audit

### QA & Testing
/qa-plan, /smoke-check, /soak-test, /regression-suite, /test-setup, /test-helpers, /test-evidence-review, /test-flakiness, /skill-test, /skill-improve

### Production
/milestone-review, /retrospective, /bug-report, /bug-triage, /reverse-document, /playtest-report

### Release
/release-checklist, /launch-checklist, /changelog, /patch-notes, /hotfix, /day-one-patch

### Creative & Content
/prototype, /vertical-slice, /onboard, /localize

### Team Orchestration
/team-combat, /team-narrative, /team-ui, /team-release, /team-polish, /team-audio, /team-level, /team-live-ops, /team-qa

## Terramon Adaptation

| CCGS Agent | Terramon Role |
|------------|---------------|
| game-designer | World Architect — territories, rules |
| systems-designer | Agent Engineer — Scout, Ranger, tools |
| lead-programmer | Backend Engineer — Python, HF, SQLite |
| ui-programmer | Frontend Engineer — Reflex PWA |
| qa-lead | QA Engineer — pytest, Scout validation |

## How to Use

1. `read_file(".agents/skills/ccgs/.claude/agents/<name>.md")` — read agent prompts
2. `read_file(".agents/skills/ccgs/.claude/skills/<name>/SKILL.md")` — read skill workflows
3. Adapt patterns to Python/Reflex for Terramon

## Hooks (12)

validate-commit.sh, validate-push.sh, validate-assets.sh, session-start.sh, detect-gaps.sh, pre-compact.sh, post-compact.sh, notify.sh, session-stop.sh, log-agent.sh, log-agent-stop.sh, validate-skill-change.sh

## Rules (11)

src/gameplay/**, src/core/**, src/ai/**, src/networking/**, src/ui/**, design/gdd/**, tests/**, prototypes/**