# TERRAMON — PHASE 3: PRODUCING (ROAST + PLAN)
*CLI Python (hexagonal) → опублікований апп → Lightning, що реально сетлиться.*

---

## 0. ЧЕСНА ВІДПОВІДЬ (The Roast up front)
**"App Store + Lightning" щоб продавати цифровий контент — НЕЗАКОННО. HARD REJECT.**
- Apple Guidelines **3.1.1** — digital goods MUST go through Apple IAP (30% cut). Любий LN-платіж всередині апки = відмова.
- **3.1.5 (crypto)** — навіть якщо "just Lightning tips", апка не може обходити IAP для розблокування фіч.
- Обгортка (web-view shell) що лінкує на LN-чекаут → 3.1.1 + 4.7/4.8 → reject.
- **Висновок:** App Store придатний ТІЛЬКИ якщо Apple IAP для анлоку, а LN — ЗОВНІ (сайт-донат, не для in-app). Це вбиває твою LN-модель у сторі.

**Реальний шлях:**
| Шлях | LN всередині | Чи пройде | Охват | Вердикт |
|---|---|---|---|---|
| **Telegram Mini App** | ✅ TON/LN native | ✅ так | RU/CIS + crypto-юзери | 🔥 КРАЩИЙ — стратегія "passive income" + вже є трафік |
| **Web PWA (iOS Safari)** | ✅ WebLN/LNBits | ✅ (нема бінаря в сторі) | глобал | 🔥 ДРУГИЙ — повний LN, без правил Apple |
| **RuStore** | ⚠️ дозволено, але санкції/гео | 🟡 умо | RU тільки | обхідний, не для EU |
| **App Store** | ❌ заборонено для in-app | ❌ reject | глобал | НІ, хіба IAP+LN-зовні |

---

## 1. WBS — CLI Python → published app
**WBS by Results (що складається):**
- A. UI-обгортка (web/PWA або TMA)
- B. LN-платіж, що реально сетлиться (LNBits adapter)
- C. Backend/хостинг + domain
- D. Store/TMA listing assets (іконка, скріншоти, опис)
- E. QA + soft launch

**WBS by Process (робота):**
```
1. UI WRAP
   1.1 Обрати форму: PWA (React/Vite) АБО TMA (HTML+TG WebApp SDK)
   1.2 Спроектувати 3 екрани (onboard → core → paywall)
   1.3 Адаптувати hexagonal CLI → API/порт (виокремити use-case)
2. LN SETTLEMENT (критично)
   2.1 Підняти LNBits (self-host або lnbits.cloud)
   2.2 Adapter: create invoice → webhook → unlock (poll 5s, timeout 15m)
   2.3 Реальний тест: заплатити 1 sats → отримати анлок (НЕ мок)
   2.4 Error states: expired, underpaid, double-spend
3. PACKAGING/DEPLOY
   3.1 PWA: build → хостинг (Netlify/Vercel free) → domain
   3.2 TMA: задеплоїти URL → BotFather → Menu Button
   3.3 RuStore: AAB + опис (тільки якщо RU-таргет)
4. LISTING ASSETS
   4.1 Іконка 512px (AI + доопрацювання, НЕ placeholder)
   4.2 3–5 скріншотів реального UI
   4.3 Опис UA/EN + ключові слова
5. QA + LAUNCH
   5.1 Тест на iOS Safari + Android + Desktop
   5.2 Smoke LN на живому
   5.3 Soft launch → моніторинг інвойсів
```

---

## 2. РЕАЛЬНИЙ ШЛЯХ (коротко)
- **Рекомендація #1: Telegram Mini App.** Стратегія казала "low-effort passive income, Kraków, solo" — TMA дає готовий трафік + native LN/TON. Найшвидший сетл.
- **Рекомендація #2: Web PWA + LN (WebLN).** Для EU/Western пасивного доходу без Apple-ріжок. iOS Safari дозволяє LN у браузері.
- **RuStore** — тільки якщо цілишся в RU-аудиторію; санкції/карти обмежують виторг.
- **App Store** — ВИКЛЮЧИТИ з LN-плану. Туди йди тільки з Apple IAP, LN залиш зовні (tips через сайт).

---

## 3. BUDGET (€ + час, solo)
| Стаття | € | Час | Нотатка |
|---|---|---|---|
| Хостинг/домен | ~20/рік | 2г | Vercel free + €10 домен |
| LNBits (self-host VPS) | ~5–10/міс | 4г | або lnbits.cloud free-tier |
| Іконка/скріншоти (якщо НЕМА арту) | 50–300 | — | Fiverr АБО AI+шаблон (ризик reject) |
| Store-фі | 0 (TG/RuStore) / 92 (Apple/рік) | — | Apple тільки для IAP-шляху |
| Dev-час (solo, без зп) | 0 | 8–14 тиж | твій час |
| **КЕШ ВСЬОГО** | **~€150–450** | **8–14 тиж** | + твій час |

> Соло, низький кеш → кеш не проблема, час і арт — проблема.

---

## 4. GANTT (реалістичні тижні, solo)
```
TASK              │ W1 │ W2 │ W3 │ W4 │ W5 │ W6 │ W7 │ W8 │
──────────────────┼────┼────┼────┼────┼────┼────┼────┼────┤
1 UI wrap (PWA/TMA)│███│███│    │    │    │    │    │    │
2 LN adapter      │    │███│███│    │    │    │    │    │  ← критичний шлях
3 Real LN test     │    │    │███│    │    │    │    │    │  ← MILESTONE: 1st sats
4 Packaging/deploy │    │    │    │███│███│    │    │    │
5 Listing assets  │    │    │    │███│███│    │    │    │  ← ризик "no-art"
6 QA + soft launch│    │    │    │    │    │███│███│    │
buffer (+25%)     │    │    │    │    │    │    │    │███│
```
**Milestone W3:** перший реальний LN-сетл (не мок). Якщо не пройшов — pivот на TMA.

---

## 5. RISK ASSESSMENT — TOP 5
| # | Ризик | Ймовірн. | Шкода | Сев. | Відповідь |
|---|---|---|---|---|---|
| 1 | **Apple відкидає LN** (3.1.1/3.1.5) | 95% | revenue lost | 5 | AVOID: не пхай LN у App Store; TMA/PWA натомість |
| 2 | **LNBits падає / не сетлиться** | 40% | розблок не йде | 4 | MIN: self-host + health-check + invoice retry + алерт |
| 3 | **Reject за "no-art"** (пусті скріншоти/placeholder) | 50% | лістинг відхилено | 3 | MIN: реальний UI-арт, не stock-пустота; AI+доопрацювання |
| 4 | **LN-фрікшн / волатільність** (юзер не розуміє sats) | 45% | low conv | 3 | MIN: туторіал + fiat-еквівалент + "pay with card?" fallback |
| 5 | **Solo burnout / кидаєш** | 35% | проєкт мертвий | 4 | ACCEPT+MIN: MVP за 8 тиж, не ідеаль; TMA = найменше коду |

---

## 6. CROSS-REF: Strategy + Creative scope
- **Strategy** (passive income, Kraków solo, low cash) → **TMA/PWA**, НЕ App Store. Стратегія вимагала дешевий шлях з трафіком — TMA дає обидва. App Store + IAP суперечить "Lightning-модель" із стратегії.
- **Creative** (Big Idea Form/Drama/Benefit) → якщо Creative видав плейсхолдер-арт без реального UI — **Risk #3 спрацьовує**. Listing вимагає справжнього скріншоту, не концепт. Перед лістингом Creative мусить віддати рендер реального екрану.
- **Producing вердикт:** кеш є, час — ні. Ріж критичний шлях (LN adapter) на W2, а не на W6. Якщо LN не сетлиться до W3 — pivот на TMA (там LN нативний, менше коду).

---
*Roast summary: App Store + Lightning = міф. Реально шипиться через Telegram Mini App або Web PWA з LN поза стором. Apple — тільки з IAP, LN залиш зовні.*
