# 🌍 Terramon — Your thoughts become creatures that live on Earth

> **Type a thought. Meet the creature it becomes. Feed, play, and evolve it — like Tamagotchi × Pokémon, but born from your mind.**

[![Live Demo](https://img.shields.io/badge/Demo-Telegram_%40terrramonBot-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/terrramonBot/terramon)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Reflex](https://img.shields.io/badge/Reflex-0.9.x-6E56CF?style=for-the-badge&logo=reflex&logoColor=white)](https://reflex.dev)
[![DeepSeek V4](https://img.shields.io/badge/LLM-DeepSeek_V4_Flash-4A90D9?style=for-the-badge&logo=deepseek&logoColor=white)](https://openrouter.ai)
[![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E?style=for-the-badge&logo=railway&logoColor=white)](https://railway.app)
[![Tests](https://img.shields.io/badge/Tests-68_passing-22c55e?style=for-the-badge)](/root/Terramon/tests)

---

## 🎯 What It Is

Terramon is a **Telegram Mini App** where every thought you type becomes an AI creature with:

- **Personality** — one of **12 Jungian archetypes** (Hero, Sage, Jester, Caregiver…) determines how it speaks and behaves
- **Needs** — hunger, energy, happiness decay over time; you feed, play, rest, and talk to keep it alive
- **Growth** — gain XP through interaction, level up, evolve when conditions are met (logistic probability)
- **Memory** — the creature remembers your past interactions and reflects on them via DeepSeek V4 Flash
- **Geography** — creatures are anchored to real places on Earth (your photo becomes their birthplace)

Behind every creature is an **Insight Engine** — a neural network that extracts the hidden DRIVER + BARRIER → THEREFORE from your thought. The creature doesn't just exist; it *acts* on the psychological mechanism that birthed it.

### Live Demo

Open [t.me/terrramonBot/terramon](https://t.me/terrramonBot/terramon) on your phone — no install, no login. Type a thought and summon your first creature in 3 seconds.

---

## 🧠 Architecture

```
player thought
     ↓
encode() → 512-dim hashing vector (L2-normalized)
     ↓
K3 MoE Insight Engine → 12 Jungian archetype experts + router → softmax probability distribution
     ↓
CreatureAgent born → stats (hunger/energy/happiness) + archetype + geo-anchor + THEREFORE
     ↓
DeepSeek V4 Flash (OpenRouter) generates unique in-character responses for every interaction
     ↓
Reflex TMA renders creature card + care panel + terra grid
     ↓
JsonMemory persists everything — survives redeploys
```

| Layer | Tech | What it does |
|-------|------|-------------|
| **Insight** | K3 MoE (12 Jungian experts) | Classifies thought into archetype + DRIVER/BARRIER/THEREFORE |
| **Agent** | CreatureAgent + LLM behavior | Creature with stats, needs, evolution, LLM‑generated dialogue |
| **Rarity** | Dirichlet‑multinomial distribution | Probabilistic rarity sampling (not binary keyword match) |
| **Frontend** | Reflex 0.9.x + Telegram Mini App | Creature card, stat bars, interaction buttons, terra grid |
| **AI** | DeepSeek V4 Flash via OpenRouter | Generates unique creature dialogue in character |
| **Deploy** | Railway (auto‑deploy from GitHub) | Live at `t.me/terrramonBot/terramon` |

---

## 🎮 Try It

### Fastest way: Telegram Mini App

1. Open [t.me/terrramonBot/terramon](https://t.me/terrramonBot/terramon)
2. Type `"I'm afraid of the interview tomorrow"`
3. Tap **SUMMON** → your creature appears
4. Feed it 🍽️, Play with it 🎮, Talk to it 💬
5. Watch it grow. Eventually it **evolves**.

### From source

```bash
git clone https://github.com/indrad3v4/Terramon.git
cd Terramon
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m terramon.application.k3_insight_engine
```

---

## 🧬 Key Techniques Applied

Every module is a direct artifact from the [AI Engineering from Scratch](https://aiengineeringfromscratch.com/) curriculum (503 lessons, 20 phases):

| Lesson | Artifact | What it taught |
|--------|----------|----------------|
| 01–02 | `insight_engine.py` encode + W@x+b | Matrices as space‑warps |
| 03 | `transforms.py` | Rotation, scale, shear = layer operations |
| 04 | `trainer.py` → `k3_insight_engine.train_k3()` | Gradient descent, loss landscapes |
| 05 | `autograd.py` | From‑scratch autograd (Value class) |
| 06 | `rarity.py`, temperature‑scaled softmax | Probability distributions, Dirichlet, logistic |
| 07 | `k3_insight_engine.py` MoE | 10 transferable techniques from Kimi K3 (AdamW, dropout, label smoothing…) |
| 14 | `creature_agent.py` + `llm_behavior.py` | Agent loops, LLM function calling |

---

## 📊 Project Status

```
▸ Phase: Live TMA · 68 tests · Railway auto-deploy
▸ Current build: 24 Jungian archetypes → K3 MoE → LLM creature behavior
▸ Next: Bayes' theorem for belief updating (creature learns from player feedback)
```

---

## 🏛️ Repo Structure

```
terramon/
├── domain/                # Pure data — Insight, CreatureAgent, ThoughtSeed, rarity, progress
│   ├── insight.py         # DRIVER/BARRIER/THEREFORE + GeoContext
│   ├── creature_agent.py  # Stats, evolution, Jungian verbs/sounds/feelings
│   └── rarity.py          # Dirichlet distribution rarity
├── application/           # Core engine
│   ├── insight_engine.py  # Public API (delegates to K3)
│   ├── k3_insight_engine.py # K3 MoE with 12 Jungian archetypes
│   ├── autograd.py        # From‑scratch autograd (Value class)
│   ├── llm_behavior.py    # DeepSeek V4 Flash creature dialogue
│   ├── agent_service.py   # Creature interaction service
│   └── summon_service.py  # Summon loop
├── adapters/
│   ├── embedding_classifier.py  # 12 Jungian archetypes in 512‑dim space
│   ├── keyword_classifier.py    # 7 Jungian keyword map
│   └── json_memory.py           # Persistence (v3: Insight + geo fields)
├── ports/                 # Service protocols
└── terramon_tma/          # Reflex frontend
    └── terramon_tma.py    # GameBoy‑style single‑screen TMA
```

---

## 🤝 Contribute

- **⭐ Star the repo** — signals matter
- **🐛 Open an Issue** — bugs, ideas, features
- **💬 Join** — Telegram [@terrramonBot](https://t.me/terrramonBot/terramon) (play first, then contribute)

```bash
# Run tests before any PR
python -m pytest tests/
```

---

> *"7 billion people. Billions of thoughts a day. Each one becomes a creature somewhere on this planet."*

**Built with DeepSeek V4 Flash, Reflex, and Jungian psychology by indradev_ — AI Systems Architect**
