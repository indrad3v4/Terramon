# 🌍 Terramon — *Freedom From Thoughts Through Play*

> **The most expensive therapist is your own brain. Terramon is the indulgence.**

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Reflex](https://img.shields.io/badge/Reflex-6E56CF?style=for-the-badge&logo=reflex&logoColor=white)
![AMD](https://img.shields.io/badge/AMD-ED1C24?style=for-the-badge&logo=amd&logoColor=white)
![Fireworks AI](https://img.shields.io/badge/Fireworks_AI-FF6B35?style=for-the-badge&logo=fireworks&logoColor=white)
![Lightning](https://img.shields.io/badge/Lightning-792EE5?style=for-the-badge&logo=bitcoin&logoColor=white)

---

## 🎯 The Idea

**The problem:** People carry their thoughts inside. Therapy costs €80-150/session. Journaling doesn't help. Friends don't get it.

**Our take:** What if your thoughts became *creatures* that live OUTSIDE your head? You type → an AI classifies your intent → the right Codex Creature is summoned. The thought lives THERE, not in your skull.

**The insight:** *Gaming is cheaper than therapy. Summoning is more effective than journaling.*

| DRIVER | BARRIER | THEREFORE | 🔑 INSIGHT |
|--------|---------|-----------|------------|
| "I want freedom from my thoughts" | "Therapy is expensive. Journaling doesn't help. Friends don't get it." | "I summon my thoughts as creatures in a game — they live THERE" | **Gaming > therapy. Summoning > journaling.** |

---

## 🏆 Hackathon Track

AMD Developer Hackathon ACT II — **Track 3: Unicorn** ("Build your startup")

| Date | Event | Details |
|------|-------|---------|
| **Jul 6–11, 2026** | AMD Developer Hackathon ACT II | lablab.ai, $20K+ prize pool |
| **Track** | Unicorn — "Build your startup" | Creativity, originality, real potential |
| **Format** | Containerised submission | Dockerfile required |
| **Resources** | $100 AMD Cloud + $50 Fireworks AI | AMD AI Developer Program |

---

## 🧠 Current Architecture

```
thought seed → IntentRouter → Codex Creature → SummonEvent → EventBus → (future UI)
                    ↓
          ClassifierPort (Protocol)
                    ↓
          KeywordClassifier ──→ (next) Fireworks AI on AMD GPU
                    ↓
          Territory system + Lightning (planned)
```

**Hexagonal ("Ports & Adapters") + Event-Driven**

| Layer | What lives here |
|-------|-----------------|
| `domain/` | Pure data classes — no dependencies |
| `ports/` | Protocol contracts (ClassifierPort, MemoryPort) |
| `adapters/` | Implementations (KeywordClassifier, JsonMemory) |
| `events/` | Typed event bus (AgentSummoned, etc.) |
| `application/` | IntentRouter, SummonService — the core loop |
| `agents/` | Codex creatures (Scout, Ranger, Archivist, Strategist) |

### The Summon Loop

```
1. You type a thought seed → "I feel lost tonight"
2. IntentRouter.classify() → matches an agent
3. Codex Creature summoned (e.g. Sage)
4. ThoughtSeed saved to memory (JSON)
5. AgentSummoned event published on EventBus
6. (Future) Reflex UI renders the summoned creature
```

### Current Agents

| Agent | Trigger Keywords | Role |
|-------|-----------------|------|
| **Scout** *(default)* | — | First responder. Processes and reports observations. |
| **Ranger** | `scan`, `image`, `photo`, `camera`, `see`, `look` | Visual analysis and territory scanning. |
| **Archivist** | `log`, `history`, `record`, `memory`, `past`, `archive` | Record keeping and historical research. |
| **Strategist** | `plan`, `attack`, `defend`, `strategy`, `move`, `territory` | Territory management and tactical planning. |

> **Current classifier:** keyword-based. **Next:** Fireworks AI LLM classifier running on AMD GPU for intent-based routing.

---

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/indrad3v4/Terramon.git
cd Terramon

# 2. Virtual environment
python -m venv .venv && source .venv/bin/activate

# 3. Install
pip install -r requirements.txt

# 4. Set your HF token (for Scout agent via HuggingFace Inference API)
echo "HF_TOKEN=your_huggingface_token" > .env

# 5. Summon!
python cli.py "Scan the ridge for movement"
# → 🔭 Ranger summoned — "Observation received. Scanning..."

python cli.py "I feel lost tonight"
# → 📜 Scout summoned — default agent handles the unknown
```

### What you'll see

```
🌱 Thought seed: Scan the ridge for movement
🧙 Summoned agent: Ranger
🕒 Timestamp: 2026-07-06T12:34:56
💾 Memory saved to: data/thought_seeds.jsonl
📡 Signal emitted: Ranger summoned at 2026-07-06T12:34:56
```

---

## 🧪 Project Status

```
┌──────────┬────────────┬──────────┬───────────┬────────────┬─────────┐
│  PRE-HACK│ 🏆 HACKATHON │   MVP    │   BETA    │   GROWTH   │  SCALE  │
│  Jun 29  │  Jul 6-11   │ Jul-Sep  │ Oct-Dec   │ Jan-Mar 27 │ Apr-Jun │
└──────────┴────────────┴──────────┴───────────┴────────────┴─────────┘
                                    │
                               🎂 Jul 29, 2027
                            v1.0.0 · 1,000 MAU · €8k/mo MRR
```

**Current Phase:** 🏃 Pre-Hackathon → 🏆 Hackathon

### Hackathon Roadmap (Jul 6–11)

| Day | Focus | Deliverable |
|:---:|-------|-------------|
| **D1** | World map UI + DID stub | Reflex map page, identity scaffold |
| **D2** | SQLite adapter swap | Hexagonal architecture proven with real DB |
| **D3** | Multi-agent world | 3+ agents, territory memory |
| **D4** | Bitcoin Lightning payments | Micropayments for rare summons |
| **D5** | On-chain thought seeds + polish | Containerised on AMD GPU |
| **🏆** | **SUBMIT — Jul 11 18:00 CEST** | **Docker + pitch + video** |

### Post-Hackathon (Jul 12 → Sep 30)

- S1: Polish, bugfixes, v0.2.0
- S2: Schell Lenses audit — Essential Experience, Fun, Curiosity, Flow
- S3: Complete Codex — every creature has name, lore, personality, tools
- S4: XP + Rarity system — creatures grow, rare ones by thought conditions
- S5: Reflex UI v2 — mobile-first, map view, creature cards
- S6: Fireworks AI classifier in prod — keyword → LLM intent routing

---

## 🏗️ How It's Built

| Stack | What For |
|-------|----------|
| **Python 3.13** | Core engine |
| **Reflex** | Web frontend (coming in hackathon phase) |
| **Fireworks AI** | LLM intent classifier on AMD GPU |
| **AMD Developer Cloud** | ROCm-powered inference |
| **HuggingFace Inference API** | Scout agent runtime (current) |
| **Bitcoin Lightning** | Micropayments (planned Day 4) |
| **SQLite** | Persistent memory (planned Day 2) |
| **Docker** | Containerised submission |

---

## 📁 Repo Structure

```
Terramon/
├── cli.py                    # CLI entry point
├── main.py                   # Scout agent demo (HuggingFace)
├── terramon/
│   ├── domain/               # Pure data — ThoughtSeed, etc.
│   ├── ports/                # Protocols — ClassifierPort, MemoryPort
│   ├── adapters/             # Implementations — KeywordClassifier, JsonMemory
│   ├── application/          # Use cases — IntentRouter, SummonService
│   └── events/               # EventBus + typed events
├── tests/                    # Pytest suite
├── tools/                    # Utilities (time_tool)
├── ROADMAP_2027.md           # 12-month plan, 26 sprints
├── STARTUP_VISION.md         # Pitch deck (10 slides)
└── STRATEGY_6_THOUGHT_EXORCIST.md  # ✅ Chosen strategy
```

---

## 📄 Key Documents

| File | What's Inside |
|------|---------------|
| `ROADMAP_2027.md` | 12-month Agile roadmap, 26 sprints, Phase 0–6 |
| `STARTUP_VISION.md` | Pitch deck — problem, solution, TAM, business model |
| `STRATEGY_6_THOUGHT_EXORCIST.md` | ✅ **Chosen strategy** — "Freedom from thoughts" |
| `LEARNING_PATH.md` | Developer learning journey through the codebase |
| `harmonogram_v2.csv` | 34-day sprint plan to Jul 29 |

---

## 🤝 How to Contribute

1. **⭐ Star the repo** — it fuels the fire
2. **🐛 Open an Issue** — bugs, ideas, features
3. **🍴 Fork it** — build your own world with your own creatures
4. **💬 Join the conversation** — [Discord](https://discord.gg/lablabai)

### PR Workflow
```bash
# Run tests first
python -m pytest tests/

# Open a PR and tag for review
# Human review required before merge
```

---

## 🎯 The Long Game

| Milestone | Target | Date |
|-----------|--------|------|
| 🏆 Hackathon submission | Working prototype on AMD GPU | Jul 11 |
| 🧠 MVP release | Full summon loop + Reflex UI | Sep 30 |
| 🌿 Open Beta | Community launch, Discord | Dec 31 |
| 💛 Revenue | €2k/mo MRR | Mar 31, 2027 |
| 🚀 Scale | 1,000 MAU | Jun 30, 2027 |
| 🎂 **v1.0.0 + €8k/mo** | **Point B — 34 years old** | **Jul 29, 2027** |

---

> *"The world is not waiting to be saved. It is waiting to be observed."*

**Built with 💜 by indradev_ — AI Systems Architect**

*Terramon — "Like a meteorite, we don't arrive quietly." 🌠*
