# 🗺 TERRAMON — Agile Roadmap до 34 лет

> **Point B: 29 июля 2027** (indradev_, 34 года 🎂)
> **Проект:** Terramon — децентрализованная AI-игра, где мысли призывают существ
> **Хакатон:** AMD ACT II (6-11 июля 2026, Track 3 Unicorn, $10K)

---

## 📐 Система координат

```
           🎂33                           🎂34
    29 июля 2026                    29 июля 2027
    │                                │
    ▼                                ▼
 ┌─────────────────────────────────────────────────────────┐
 │  Q3 2026  │  Q4 2026  │  Q1 2027  │  Q2 2027  │  Q3'27  │
 │ HACKATHON │  BETA MVP  │  GROWTH   │  SCALE    │  WIN    │
 └─────────────────────────────────────────────────────────┘
    ↑                    ↑                       ↑
  v0.1.0              v0.5.0                 v1.0.0
  MVP live            Open Beta              34 🎂
```

---

## 🎯 Стратегия (Point A → Point B)

| Элемент | Значение |
|---|---|
| **Точка А** | Один разработчик, хобби-проект, keyword классификатор, JSONL память |
| **Точка Б (34)** | Terramon — live продукт: Reflex UI, Fireworks AI на AMD, Lightning BTC, 100 Schell линз, сообщество, доход |
| **GET-WHO-TO-BY** | Make me who currently struggles alone → to thrive with a live product + income by 34 |
| **DRIVER** | Я хочу построить продукт, который приносит доход и признание |
| **BARRIER** | Ограниченные ресурсы (время, деньги, миграция), соло-разработка |
| **INSIGHT** | Мне нужна система, где каждый день — шаг к Point B, а не хаотичный рывок |

---

## 🔄 Agile Loops — Структура

1 **спринт** = 2 недели (14 дней)
1 **квартал** = 6 спринтов

| Этап | Даты | Спринтов | Фокус |
|---|---|---|---|
| **PHASE 0: PRE-HACKATHON** | 29 июн — 5 июл | 1 | Day 4-10 закрыть |
| **PHASE 1: HACKATHON** 🏆 | 6 июл — 11 июл | — | Победа в Track 3 Unicorn |
| **PHASE 2: MVP** | 12 июл — 30 сен | 6 | Reflex UI + AMD + Lightning |
| **PHASE 3: BETA** | 1 окт — 31 дек | 6 | Сообщество + тесты |
| **PHASE 4: GROWTH** | 1 янв — 31 мар | 6 | Монетизация + контент |
| **PHASE 5: SCALE** | 1 апр — 30 июн | 6 | Партнерства + мобила |
| **PHASE 6: 🎂 WIN** | 1 июл — 29 июл | 2 | V1.0.0 релиз → 34 года |

---

## PHASE 0: PRE-HACKATHON (29 июн — 5 июл)

*Что уже есть: Day 1-3 ✅, Scout на Hugging Face, hex-архитектура, 3 теста*

| Спринт | Дата | Задача | Статус |
|---|---|---|---|
| **S0.1** | 29 июн | **Day 4: Intent routing** — классификация по intent (не keyword) | 🔜 TODAY |
| | 30 июн | Day 5: Reflex frontend scaffold | |
| | 1-2 июл | Day 6-7: Summon UI + Outcome memory | |
| | 3 июл | Day 8: **Fireworks AI classifier** на AMD | ⚡ КРИТИЧЕСКИ |
| | 4 июл | Day 9: Territory system | |
| | 5 июл | Day 10: Agent-to-agent events + **AMD GPU deploy test** | |

**Gate: Все 10 дней закрыты, Dockerfile работает, Fireworks AI звонит**

---

## PHASE 1: 🏆 HACKATHON (6-11 июля)

*AMD Developer Hackathon ACT II — Track 3 Unicorn*

| День | Дата | Деливерабли |
|---|---|---|
| **D1** | 6 июл | World map UI + DID stub |
| **D2** | 7 июл | SQLite adapter swap (доказываем hexagonal) |
| **D3** | 8 июл | Multi-agent world: 3+ agents, territory memory |
| **D4** | 9 июл | **Bitcoin Lightning** micropayment for rare summons |
| **D5** | 10 июл | On-chain thought seed + wallet signing |
| **🏆 SUBMIT** | **11 июл 15:00 UTC** | **Containerised Terramon** на AMD GPU + Fireworks AI + Lightning + DID |

**Критические проверки (hard rules):**
- [ ] `docker-compose up` работает 🐳
- [ ] Fireworks AI классифицирует мысли 🔥
- [ ] Lightning платёж за редких существ ⚡
- [ ] Reflex UI показывает summon feed 📱
- [ ] AMD GPU inference на Fireworks AI 🎮

**Pitch для Track 3:**
> *"Terramon — мысль становится существом. Твой мозг — геймпад."*

---

## PHASE 2: MVP (12 июл — 30 сен) = 6 спринтов

*После хакатона: контейнеризация есть, AMD работает, Lightning есть*

| Спринт | Фокус | Ключевые сториз |
|---|---|---|
| **S1** | **Post-hackathon polish** | README demo, bugfixes, portfolio showcase on indra-ai.dev |
| **S2** | **Schell Lenses** | Unpack 100 lenses from *The Art of Game Design* into `.agents/skills/ccgs_/lenses/` |
| **S3** | **Codex Complete** | Every summoned agent has: name, summon condition, personality, tools, lore |
| **S4** | **Agent XP+Rarity** | Agents grow with summon frequency. Rare creatures cost sats |
| **S5** | **Reflex UI v2** | Mobile-first pass (375px responsive), map, agent cards |
| **S6** | **Fireworks AI Classifier** | Replace KeywordClassifier with real LLM on AMD GPU |

**Gate: v0.5.0 — Open Beta ready**

---

## PHASE 3: BETA (1 окт — 31 дек) = 6 спринтов

*Запуск в открытую бету*

| Спринт | Фокус | KPI |
|---|---|---|
| **S7** | **Community launch** | GitHub stars > 50, Discord сервер |
| **S8** | **Bug bash** | 95%+ тестов зелёные, stress test 10 thoughts |
| **S9** | **Territory wars** | Agent-to-agent conflicts over named territories |
| **S10** | **Mobile UI** | Reflex PWA, push-уведомления |
| **S11** | **Lightning economy** | Free tier = 5 summons/day, rare = 1000 sats |
| **S12** | **Winter event** | Seasonal codex creatures, holiday map |

**Gate: 100 active users, 1000 summons, $0 revenue (скорее всего)**

---

## PHASE 4: GROWTH (1 янв — 31 мар 2027) = 6 спринтов

*Монетизация и контент*

| Спринт | Фокус | KPI |
|---|---|---|
| **S13** | **Subscription model** | €9.99/mo — 50 summons/day + priority queue |
| **S14** | **Content marketing** | dev.to/Twitter threads: "I built an AI game in Python" |
| **S15** | **Partnerships** | AMD showcase, lablab.ai alumni |
| **S16** | **Schell audit** | Apply all 100 lenses, fix top 10 design gaps |
| **S17** | **Performance** | Sub-1s summon, cached territory state |
| **S18** | **Security audit** | Lightning wallet, DID, API keys |

**Gate: €2k/mo MRR (recurring)**

---

## PHASE 5: SCALE (1 апр — 30 июн 2027) = 6 спринтов

| Спринт | Фокус | KPI |
|---|---|---|
| **S19** | **Real-world sensors** | GPS territory claims, weather API triggers |
| **S20** | **User-generated agents** | Players can teach new codex creatures |
| **S21** | **AI-driven narration** | Each summon generates unique story |
| **S22** | **Mobile app** | Reflex → native wrappers (capacitor/flutter) |
| **S23** | **Load testing** | 1000 concurrent summons |
| **S24** | **Marketing push** | Product Hunt, Hacker News launch |

**Gate: 1000 MAU, €5k/mo MRR, 10+ codex creatures**

---

## PHASE 6: 🎂 WIN (1 июл — 29 июл 2027) = 2 спринта

*Точка Б — 34 года*

| Спринт | Дата | Деливерабли |
|---|---|---|
| **S25** | 1-14 июл | v1.0.0 RC — все тесты зелёные, документация, codex complete |
| **S26** | 15-28 июл | **v1.0.0 RELEASE** — git tag, GitHub Release, demo video, pitch deck |
| **🎂** | **29 июля 2027** | **34 ГОДА — ТОЧКА Б** |

### Что такое "Победа" в 34:

| Метрика | Goal | Stretch |
|---|---|---|
| GitHub Stars | 500+ | 1000+ |
| MAU | 500+ | 2000+ |
| MRR | €2k/mo | €5k/mo |
| Codex creatures | 10+ | 20+ |
| Schell lenses applied | 100/100 | 100/100 |
| AMD GPU deployed | ✅ | ✅ |
| Lightning active | ✅ | ✅ |
| Job (SII или лучше) | Python AI Engineer | Senior/Lead |

---

## 📊 Financial Flight Path

| Дата | Источник | Цель |
|---|---|---|
| Июл 2026 | Bolt deliveries + хакатон приз ($10K?) | Rent + выжить |
| Авг-сен 2026 | SII job start 💼 | Стабильный доход |
| Окт-дек 2026 | Job salary + Bolt | Накопить подушку |
| Янв-мар 2027 | Job + Terramon подписки | €2k/mo extra |
| Апр-июн 2027 | Job + Terramon growth | €5k/mo extra |
| **Июл 2027** | **Точка Б** | **Стабильность + продукт = свобода** |

---

## 🧭 Принципы Agile Loops

1. **Каждый спринт = 2 недели.** Никаких "когда будет готово"
2. **Gate после каждой фазы.** Без gate — нет перехода
3. **Point B известен.** 29 июля 2027 — дата, а не мечта
4. **Driver/Barrier/Insight** для каждого спринта
5. **Schell линзы** применяются каждый спринт к новому функционалу
6. **Зачынаем** — только после твоего зеленого света

---

## Структура каждого спринта

```
┌────────────────────────────────────────────┐
│  SPRINT N                                  │
│  Driver: что этот спринт даёт Terramon     │
│  Barrier: что может пойти не так           │
│  Tasks: [сториз с effort]                  │
│  Gate: [конкретное условие перехода]       │
│  Schell Lens: [какая линза применяется]    │
└────────────────────────────────────────────┘
```

> **Следующий шаг:** Ты говоришь **"Зачынаем"** → я создаю промпт для Sprint 0.1
> 
> ИЛИ выбираем спринт/фазу, которую обсуждаем детальнее.
