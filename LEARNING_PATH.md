# 📚 TERRAMON LEARNING PATH — Agentic AI in Python

> **Кожны дзень = адзін Python/AI concept + адзін крок да 34 гадоў**
> Гэта не проста TODO. Гэта твой асабісты AI Engineering curriculum.

---

## 🎯 Як карыстацца

1. Адкрываеш дзень → чытаеш **што ты вывучыш**
2. Робіш задачу → атрымліваеш **interview snippet** (што сказаць на субясе)
3. Зачыняеш дзень → пераходзіш да наступнага

---

## PHASE 0: PRE-HACKATHON (Jun 29 — Jul 5)
*Канцэпцыя: ад keyword да intent, ад JSON да GPU*

### Day 4 — Jun 29 (🔜 TODAY)

| Модуль | Што вывучыш |
|--------|------------|
| **Python concept** | `enum`, `Protocol` duck typing, стратегія Strategy |
| **AI concept** | Intent vs Keyword classification |
| **Архітэктура** | Hexagonal ports — замена adapter без змены domain |

**Код:**
```python
class IntentKind(enum.Enum):
    WISDOM = "wisdom"      # "I feel lost"
    COMFORT = "comfort"    # "I'm sad"
    ACTION = "action"      # "movement on the ridge"
    CURIOSITY = "curiosity" # "what is that light?"
```

**Interview snippet:**
> *"I built an intent classifier that routes user input to specialized agents using a hexagonal ports/adapter pattern. The ClassifierPort is a Protocol — I can swap keyword matching for Fireworks AI without changing the summon loop."*

---

### Day 5 — Jun 30

| Модуль | Што вывучыш |
|--------|------------|
| **Python concept** | `@rx.event(background=True)`, `async with self:`, Reflex state |
| **AI concept** | User-facing AI interface design |
| **Архітэктура** | Backend-for-Frontend (BFF) pattern |

**Что построишь:** Reflex app, где input → summon → результат

**Interview snippet:**
> *"I built a Reflex frontend with background event handlers — the user types a thought and sees the summoned creature appear without blocking UI."*

---

### Day 6 — Jul 1

| Модуль | Што вывучыш |
|--------|------------|
| **Python concept** | `rx.foreach`, `rx.cond`, reactive UI |
| **AI concept** | Agent response streaming |
| **Архітэктура** | Event-driven UI updates |

---

### Day 7 — Jul 2

| Модуль | Што вывучыш |
|--------|------------|
| **Python concept** | JSONL persistence, adapter pattern |
| **AI concept** | Memory systems (episodic vs semantic) |
| **Архітэктура** | CQRS — Command Query Responsibility Segregation |

---

### Day 8 — Jul 3 ⚡

| Модуль | Што вывучыш |
|--------|------------|
| **Python concept** | `httpx.AsyncClient`, `asyncio` timeouts |
| **AI concept** | LLM inference on AMD GPU через Fireworks AI |
| **Архітэктура** | Provider pattern — замена OpenAI → Fireworks без змены кода |

**Interview snippet:**
> *"I replaced a keyword classifier with LLM inference on AMD GPUs via Fireworks AI — the switch was a single adapter file thanks to hexagonal architecture."*

---

### Day 9 — Jul 4

| Модуль | Што вывучыш |
|--------|------------|
| **Python concept** | `@dataclass` с валідацыяй, `__post_init__` |
| **AI concept** | Spatial AI — agents in named territories |
| **Архітэктура** | Domain-Driven Design aggregates |

---

### Day 10 — Jul 5

| Модуль | Што вывучыш |
|--------|------------|
| **Python concept** | Pub/sub in pure Python, `Callable[[T], None]` |
| **AI concept** | Multi-agent communication patterns |
| **Архітэктура** | Event-driven architecture |

---

## 🏆 PHASE 1: HACKATHON (Jul 6-11)
*Канцэпцыя: deploy на AMD GPU, Lightning BTC, containerization*

### Day 11 — Jul 6 🏆

| Модуль | Што вывучыш |
|--------|------------|
| **Python concept** | Reflex map components, SVG rendering |
| **AI concept** | Decentralized identity (DID) |
| **Архітэктура** | Client-side routing |

---

### Day 12 — Jul 7 🏆

| Модуль | Што вывучыш |
|--------|------------|
| **Python concept** | SQLite3, migration scripts |
| **AI concept** | Persistent memory for agents |
| **Архітэктура** | Доказываем hexagonal — JSON → SQLite без змены domain |

**Interview snippet:**
> *"I proved hexagonal architecture works by swapping JSON file storage for SQLite — zero changes to domain or application layers. Just one new adapter."*

---

### Day 13 — Jul 8 🏆

| Модуль | Што вывучыш |
|--------|------------|
| **Python concept** | Multi-agent orchestration |
| **AI concept** | World state, shared context |
| **Архітэктура** | State machine (agent lifecycle) |

---

### Day 14 — Jul 9 🏆⚡

| Модуль | Што вывучыш |
|--------|------------|
| **Python concept** | `asyncio` для фінансавых транзакцый |
| **AI concept** | Pay-per-use AI (micropayments) |
| **Архітэктура** | Payment Port — абстракцыя плацежнай сістэмы |

**Interview snippet:**
> *"I integrated Bitcoin Lightning Network for micropayments — summoning rare creatures costs sats. The PaymentPort means I can swap Lightning for Stripe without changing game logic."*

---

### Day 15 — Jul 10 🏆

| Модуль | Што вывучыш |
|--------|------------|
| **Python concept** | Web3.py, wallet signing |
| **AI concept** | On-chain AI actions |
| **Архітэктура** | Signed events for audit trail |

---

### Day 16 — Jul 11 🏆 SUBMIT

| Модуль | Што вывучыш |
|--------|------------|
| **Python concept** | Docker multi-stage builds, docker-compose |
| **AI concept** | Full-stack AI deployment |
| **Архітэктура** | Containerized microservices |

**Interview snippet:**
> *"I containerized a multi-agent AI game on AMD GPUs with Fireworks AI inference and Bitcoin Lightning payments — all in one docker-compose."*

---

## PHASE 2: MVP (Jul 12 — Sep 30)
*Канцэпцыя: Schell lenses → game design → prod*

### Sprint 1: Polish (Jul 12-25)

| Дзень | Што вывучыш | Код |
|-------|------------|-----|
| Jul 12 | **Post-hackathon** README, demo GIF, portfolio | `docs/` |
| Jul 13 | **Mobile-first CSS** — 375px responsive | Reflex breakpoints |
| Jul 14 | **Codex design** — agent identity layer | `docs/codex/*.md` |
| Jul 15 | **Schell Lens #1:** Essential Experience | `lenses/01.md` |
| Jul 16 | **Schell Lens #2:** Fun | `lenses/02.md` |
| Jul 17 | **Schell Lens #3:** Curiosity | `lenses/03.md` |
| Jul 18 | **Schell Lens #4:** Flow | `lenses/04.md` |

### Sprint 2-3: Codex + Lenses (Jul 26 — Aug 8)

| Дзень | Што вывучыш | Код |
|-------|------------|-----|
| Jul 26-28 | **Чистая архитектура** — domain entities, rich models | `domain/agent.py` |
| Jul 29 | **🎂 33 ГОДА** — v0.3.0 release | `git tag v0.3.0` |
| Jul 30-Aug 2 | **Strategy pattern** — agent personalities | `agents/*.py` |
| Aug 3-8 | **XP system** — numeric progression | `domain/xp.py` |

### Sprint 4-5: Reflex UI v2 (Aug 9-22)

| Модуль | Што вывучыш |
|--------|------------|
| **8 days** | Reflex components, state, routing |
| **Interview snippet:** | *"I built a mobile-first reactive game UI in pure Python — no JavaScript."* |

### Sprint 6: Fireworks AI Prod (Aug 23 — Sep 5)

| Модуль | Што вывучыш |
|--------|------------|
| **Python concept** | Retry, backoff, circuit breaker |
| **AI concept** | Production LLM serving |
| **Архітэктура** | Fireworks adapter for ClassifierPort |

**v0.5.0 BETA** — Open Beta gate 🎉

---

## PHASE 3-6: BETA → GROWTH → SCALE → WIN (Oct 2026 — Jul 2027)

*Поўны распіс у `ROADMAP_2027.md` і `STARTUP_VISION.md`*

---

## 🎓 САМОЕ ГАЛОЎНАЕ: Што ты ўмееш да 34

| Skill | Дзе вывучыў | Што сказаць на субясе |
|-------|------------|----------------------|
| **Python async** | Day 4-10 | "Built async agent pipeline with asyncio + httpx" |
| **Hexagonal architecture** | Day 3-4 | "Ports and adapters — swap storage without changing domain" |
| **Event-driven systems** | Day 10 | "Typed EventBus with pub/sub for agent communication" |
| **LLM deployment on AMD** | Day 8 | "Fireworks AI on AMD GPU for intent classification" |
| **Bitcoin Lightning** | Day 14 | "Micropayments for AI actions via Lightning Network" |
| **Containerization** | Day 16 | "Docker + docker-compose for multi-service AI deployment" |
| **Reflex / full-stack Python** | Day 5-6 | "Mobile-first reactive UI in pure Python" |
| **Game design (Schell)** | Phase 2 | "100 game design lenses applied to AI product" |
| **Product management** | Phase 3-6 | "12-month roadmap, Agile sprints, REVENUE" |

---

**Гэты файл — твой асабісты даведнік.** Кожны дзень адкрываеш → чытаеш → робіш → атрымліваеш interview snippet.

> **Learning = doing. Doing = Terramon. Terramon = портфолио. Портфолио = job. Job = свобода.** 🚀
