# TERRAMON — DVIZHOK PHASE 1 / СТРАТЕГІЯ

_Статус: roast + стратегія. RU/UK mix. Terse._

---

## 1. CONTACT REPORT — що Terramon є СЬОГОДНІ

**Контакт:** Illia / `indradev_` (Краків, AI Systems Architect). Власник, єдиний білдер.
Хоче: пасивний дохід ("зробив — забув — капає"), App Store + RuStore, "монетизувати думки" через Lightning.

**Продукт (факт, не мрія):**
- Python CLI, гекс-архітектура (domain/ports/adapters/events/application/agents). 34 pytest зелені. Чистий код — ок.
- Ввід "thought seed" → **KeywordClassifier** (НЕ embedding!) → 1 з 5 агентів (Scout/Ranger/Archivist/Strategist/Sage) → запис у JSON-пам'ять → (плановано) Reflex UI.
- Агенти = терапевтичні істоти (Comfort/Courage/Healer/Sage/Strategist). Обрана стратегія: **"Freedom from thoughts through play"** — терапія-через-гру.
- Монетизація в репо: FREE 5 summon/день, SUMMONER $9.99/mo, RARE = 1000 sats (Lightning, плановано), BUILDER $4,999.
- **НЕМАЄ:** арту, історії, світу, мультиплеєра, мобілки, App Store-білда. Це CLI + roadmap на 26 спринтів.

**Розрив (the gap that kills the brief):** Твій бріф каже "EmbeddingClassifier 512-dim, агенти Mystic/Wanderer, LNBits 5000 sats legendary, Stripe EUR, monetize thoughts". Репо каже **keyword-router + Sage + 1000 sats + терапія**. Ти продаєш інвестору продукт, якого ще не існує, і називаєш його тим, що вже є. Це не стратегія — це самообман із roadmaps.

---

## 2. BRAND ARCHITECTURE — піраміда (6 рівнів)

```
ESSENCE        "Freedom from thoughts through play"  ← БРЕШЕ з монетизацією
               (розірвано: терапія vs "monetize thoughts")
VALUES         свобода від оверсинку · гра-як-зцілення · без стигми ·
               open-source + Lightning прозорість
CHARACTER      тихий екзорцист · іронічний ("найдорожчий терапевт — твій мозок")
               · не повчає, співчуває
EMOTIONAL      полегшення · "думки живуть ТАМ, не в голові" · мене почули
FUNCTIONAL     думка → істота · пам'ять-неперервність · дешевше за терапію ·
               гра замість щоденника
ATTRIBUTES     thought-seed ввід · keyword→LLM router · 5 агентів · JSON/SQLite
               пам'ять · free 5/день · 1000 sats за рідкісного · Reflex UI (план)
```

**Roast по Aaker:**
- **Essence не проходить "and only your brand" тест** — "freedom through play" є в кожного journaling-апу. А "monetize thoughts on Lightning" взагалі не essence, а фантазія білдера.
- **Self-expressive шар відсутній.** Користувач не може сказати "я — людина, що сумонує свої думки". Це не статус, це coping.
- **Price-quality не б'ється:** обіцяєш "свободу/зцілення" (преміум-емоція), а даєш text-label за 1000 sats. БЕЗ АРТУ рідкісна істота = звичайна. Ціна сигналізує сміття.

---

## 3. INSIGHT ENGINE — Driver + Barrier → Therefore

**Цільовий юзер:** indie-dev / AI-цікавий, хто шукає "монетизувати думки".

> **DRIVER:** "Хочу, щоб сайд-проєкт капав пасивний дохід, щоб не возити Bolt їжу."
>
> **BARRIER:** "Щоб хтось платив, треба retention + WTP. У мене CLI без арту, без світу, без жодного доведеного платника. 34 тесту ≠ 34 юзері."
>
> **THEREFORE (брудний):** "Я перейменовую терапію-гру в 'monetize your thoughts on Lightning' стартап, надуваю TAM до $10B, і називаю keyword-рутер 'production agentic system' — щоб вірити, що гроші йдуть, не довівши, що бодай хтось заплатить."

**Інсайт:** *Інді-білдер не продає продукт — він продає собі ілюзію пасивного доходу, бо довести WTP страшніше, ніж написати 26-й спринт.*

> ⚠️ Це НЕ "they'd pay sats". Це coping-поведінка зараз. Саме тому бріф про "monetize thoughts" — брехня: ти платиш собі в думках, а не хтось тобі.

---

## 4. CREATIVE BRIEF (8 полів)

```
BACKGROUND      Terramon — чистий Python-CLI терапія-гра ("виклич думку як істоту").
                 Власник хоче App Store + Lightning-пасивний дохід, але продукт ще
                 не мобільний і не має WTP. Бренд розірваний: терапія vs монетизація.

OBJECTIVE       Перестати продавати фантазію. Обрати ОДИН essence і побудувати
                 навколо нього мобільний loop з доведеним поверненням.

AUDIENCE        BRAND CHAMPION: Макс, 29, інді-дев у Кракові. Тривожний, пише
                 щоденник і кидає. Хоче "щось із ІІ, щоб не йти до терапевта за €120".
                 DRIVER: "хочу видихнути голову". BARRIER: "терапія дорого,
                 щоденник нудно, стигма". TA: AI-цікава молодь 25-35, EU/UA, burnout.

INSIGHT         Див. п.3 — білдер монетизує власну делюзію, а не думки юзерів.

MESSAGE         "Твої думки — не в тебе. Виклич їх назовні і живи тут."
                 (бренд = асистент, НЕ заміна; юзер — протагоніст)

RTB             гекс-архітектура робить пам'ять неперервною · free 5/день без
                 стигми · агенти мають ролі (Sage/Healer) · Lightning = чесна
                 мікроплата, а не підписка-пастка

MANDATORIES     НЕ казати "monetize thoughts" до доказу WTP. НЕ робити 2 продукти
                 в 1 назві. Спочатку арт + світ (без них "rare" = ніщо).
                 App Store тільки після mobile-loop. Tone: теплий, іронічний, не medical.

OUTPUT          Mobile-first summon-loop (Reflex/Capacitor) + 1 brand film
                 (30s, "most expensive therapist is your brain") + App Store page.
```

---

## THE STRATEGIC LIE (roast)

**"Monetize thoughts on Lightning" — це фантазія, не ринок.**
- Ти НЕ монетизуєш думки. Ти береш sats за рідкісного text-монстра. Це lootbox без луту.
- **Хто платить sats за text-істоту?** Ніхто, що раз. А "чому двічі?" — бо рідкісна істота без арту = звичайна істота з іншим лейблом. Юзер платить 1000 sats, бачить текст, і йому треба заплатити ЩЕ раз за "справжню рідкість", якої не існує. Він платить за ніщо, двічі, раз за разом. Це не retention — це каса самообману.
- Ринок "AI gaming $10B" і "companions +300% YoY" — інфляція TAM. Твій реальний ринок = дешева self-care альтернатива терапії. Там WTP є ($9.99/mo), але Lightning-sats-монетизація йому суперечить (бідний студент не відкриватиме LNBits-гаманець за рідкісного Сейджа).

**Дві правди, що не живуть в одній назві:**
1. Терапія-гра (free/cheap, retention через емоцію) — РЕАЛЬНА.
2. "Monetize thoughts on Lightning" (пасивний дохід білдера) — ФАНТАЗІЯ.

Ти будуєш №1, а пітчуєш №2. Інвестор купить №2, юзер потрібен для №1. Конфлікт.

---

## POSITIONING STATEMENT (одна)

> **Terramon — гра-екзорцист, де ти викликаєш свої тривожні думки як істот, що живуть поза головою: дешевше за терапію, без стигми, без щоденника. Не "монетизуй думки" — звільнись від них.**

---

## ЩО УНАСЛІДУЮТЬ НАСТУПНІ ФАЗИ

- **CREATIVE** успадковує: essence "freedom through play" (НЕ monetize), tone — теплий/іронічний, brand film "most expensive therapist is your brain", заборону на "monetize thoughts" у копірайті. Big Idea = "думки живуть ТАМ".
- **PRODUCING** успадковує: пріоритет #1 = АРТ + СВІТ (без них rare-механіка мертва), mobile-loop через Reflex→Capacitor, Lightning тільки як чесна мікроплата ПІСЛЯ доказу retention, відкласти App Store до готового loop. WBS: спочатку арт/світ, потім monetization.
- **MEDIA** успадковує: ціль — self-care/burnout аудиторія (не crypto/bitcoin crowd), канали = dev.to/X/Discord, НЕ біткоїн-форуми. KPI = retention/days-active, НЕ sats-volume. App Store + RuStore — тільки на фіналі Phase 5.
