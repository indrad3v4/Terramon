# Terramon — North Star Gap Report (v2) · 2026-08-10 (iter-14)

Fingerprint: `0c52511` (post-iter-14 push) · Playwright/Chromium headless + TMA-mock · Target: https://terramon-tma-production.up.railway.app

---

## 0. ВЕРДИКТ ДНЯ (TL;DR)

- **North Star Score: 75/100** (→ плато 3-я итерация; Geo/Lore/Win-path железно 12/12; M7 код-сайд ЗАКРЫТ и доказан — инвойс создаётся на проде)
- Топ-3 блокера: **1) M7 settle-нога: нужен РЕАЛЬНЫЙ ПЛАТЁЖ владельца (~3000 sats) 2) Railway volume не примонтирован — данные стёрты деплоем 3) нет реальных игроков (M6/M8)**
- Kill-condition монитор: share 1 · mint 0 · дней с mint=0: ~15/30 → **НЕ в зоне риска (readiness-фаза)**
- 🎯 **ГЛАВНОЕ СОБЫТИЕ**: впервые в истории loop'а проба M7 создала LN-инвойс на проде — `invoice_ok: true`, `invoice_msg: "⚡ Invoice ready"` (клик по Care-кнопке, а не по перекрытой home-кнопке). Цепочка «инвойс → settle → счётчик» код-сайд доказана на 2/3 звена.

## 1. NORTH STAR SCORE (композит)

| Компонент | Вес | Сегодня | Нормализация |
|---|---|---|---|
| Geo-привязка | 25 | **100%** (12/12) | static-map URL с реальными координатами (50.0619, 19.9368) |
| Vision-lore («Open your eyes») | 25 | **1** | кнопка в DOM на главной карточке + лор рендерится |
| Win-path (достижимость) | 25 | **12/12** | min(архетипов/12, 1) — полная вселенная |
| Mint-loop | 25 | **0** | инвойс создан (invoice_ok=True), но settle не было → mint_count=0 |
| **ИТОГО** | 100 | **75/100** | |

Боевая формула (с реальными игроками): NSS = 40·MintRate + 30·D7 + 15·Geo + 15·Lore.

## 2. ГЭП-ТАБЛИЦА (мост «инженерия → северная звезда»)

| # | Метрика | Что меряет | Сегодня | Цель | Гэп | Блокирует | Измерение |
|---|---|---|---|---|---|---|---|
| M1 | Geo% | доля существ с реальными координатами | 12/12 (100%) | 100% | 🟢 код-ок; ждёт device-проверки | share-петлю | AUTO + **device** |
| M2 | Vision-lore | «Open your eyes» + рендер лора | 1 | 1 | 🟢 ок | эмоцию/арт | AUTO |
| M3 | Win-path | уникальные архетипы за прогон | 12/12 | 12/12 | 🟢 ок | контентную глубину → D7 | AUTO |
| M4 | Дубликаты | unique/total | 12/16 (0.75) | 1.0 | 🟡 инфо (часть дублей — probe-сиды) | экономику минта | AUTO |
| M5 | Фрикция | гейт/модалки | 0 блоков | 0 | 🟢 ок | онбординг → D7 | AUTO |
| M6 | Share-funnel | доля сессий с share-тапом | счётчик работает (+1/прогон) | ≥2% (kill <2%) | 🔴 нет игроков | охват (kill-condition) | AUTO + **люди** |
| M7 | Mint rate | % саммонеров с mint | 0 (mint_count=0) | ≥2% | 🔴 **инвойс-нога ДОКАЗАНА; settle ждёт платёж** | саму северную звезду | AUTO + **платёж владельца** |
| M8 | D7 retention | возврат на 7-й день | нет данных | кохортный бенчмарк | 🔴 нет игроков | 2-ю половину NSS | **люди** |

Регрессионные guard: **418 тестов зелёные** (414 + 4 новых) · reflex export собирается · +4 source-scan гварда на mint-reachability.

## 3. ТОП-3 БЛОКЕРА (ранжировано)

1. **M7 mint-loop: код-сайд цепочка доказана полностью, остался 1 реальный платёж.** В этом прогоне проба (после фикса iter-14) кликнула «⚡ Mint via Lightning» по Care-кнопке → **`invoice_ok: true`, «⚡ Invoice ready: 3000 sats»** — Alby Hub создаёт инвойс на проде. MintLoop=0 только потому, что инвойс никто не оплатил (settle → `verify_lightning` → `_record_mint` → mint_count=1). **Действие владельца: оплатить инвойс из любого LN-кошелька (~3000 sats) и нажать «✅ I've paid — verify» в игре → M7=1 → NSS=100.** Это ЕДИНСТВЕННЫЙ оставшийся шаг до 100/100 (readiness).
2. **Railway volume НЕ примонтирован — деплой iter-14 снова стёр data/.** share_count 1→0 и seed_count 16→0 на старте KPI (прогон заново насеял 15 сидов: 12 раундов + 3 пробы). ⚠️ При этом `/health` показал `data_persisted: true` — сигнал, похоже, ЛОЖНОПОЛОЖИТЕЛЬНЫЙ (маркер `data/boot_epoch.json` переживает boot даже когда сами данные стёрты? нет — маркер пишется при boot'е заново; вероятен edge-case порядка boot'ов при деплое). **След. итерация: age-based проверка** (существует ли сид СТАРШЕ boot-маркера — тогда data_persisted честен). **Действие владельца: создать volume `terramon-data` в дашборде Railway** (Settings → Volumes → mount `/app/data`).
3. **M6/M8 и полировка: нет реальных игроков + home-карточка.** share-счётчик работает (+1 честный тап/прогон). Нужен охват: разослать бота, проверить кнопку Mini App. Плюс: после фикса перекрытия mint-кнопки home-карточки ушли ПОД сгиб (карточка 160px, контент 257px, скролл внутри) — не перекрыты, но менее заметны; полировка (кнопки выше сгиба) — след. итерация.

## 4. ЧТО СДЕЛАНО В ITER-14 (все изменения проверены на диске: grep + pytest + export)

1. **Root-cause найден и доказан (диагностика, scripts/kpi/diag_iter14.py)**: в DOM ДВЕ кнопки «⚡ Mint via Lightning» — home-карточка (ZONE 1) и Care-панель. `elementFromPoint` в центре home-кнопки возвращал **INPUT** (поле ввода мысли перекрывало mint-зону — карточка переросла фиксированный экран) → `locator(...).first` ждал actionability 4s → таймаут → invoice_ok=null в каждой итерации. Клик по Care-кнопке создавал инвойс мгновенно.
2. **Probe fix (scripts/kpi/play_to_win.py)**: хелпер `_button_is_covered()` (elementFromPoint vs bounding-box, ошибки → False) + цикл по `.count()/.nth(i)` — клик по ПЕРВОЙ видимой НЕперекрытой кнопке (= Care-панель). `.first` убран полностью. Policy NEVER-click для «⚡ MINT ·»/«Mint (1 Star)»/«✅ I've paid» не тронута.
3. **UI fix (terramon_tma.py, ZONE 1)**: компактная карточка получила `max_height="100%"` + `overflow_y="auto"` (контент скроллится ВНУТРИ карточки, ничего не вылезает под input); line-clamp: lore 2 строки, creature_greeting 2 строки, memory_greeting 1 строка. Доказано на проде: input (y 269) больше НЕ перекрывает mint-кнопки; элемент из elementFromPoint — текст карточки, не INPUT.
4. **4 новых source-scan гварда (tests/test_m7_mint_reachability.py)**: (1) карточка ZONE 1 несёт max_height/overflow_y; (2) ≥2 line-clamp в ZONE 1; (3) KPI-проба НЕ кликает `.first` по Lightning-кнопке + есть elementFromPoint-проверка; (4) воронка home-карточки (метки + маркер M7-funnel) цела.
5. Верификация: **418 passed, 0 failed** · `reflex export --frontend-only --no-zip` exit 0 · все правки подтверждены grep'ом на диске. Push: `4934ead..0c52511`.

## 5. RESEARCH-РЕФЕРЕНСЫ (обоснование решений)

- **getAlby/hub** (github.com/getalby/hub, активный, self-custodial LN-нода, NIP-47): паттерн «инвойс → lookup → settled» — ровно то, что делает `verify_lightning` → **REPLICATE** (уже реализовано; settle ждёт платёж).
- **Simo-B/FlashInvoice** (TMA + LN-инвойсы): паттерн «показать BOLT11 внутри Mini App» — у нас: «Pay ⚡ 3000 sats», инвойс в agent_message → **REPLICATE** (есть).
- **Telegram-Mini-Apps/tma.js** (официальная org): эталон интеграции TMA; наш injected-mock для headless — обоснованная альтернатива → **AVOID** переписывания на TS-стек.
- **Reflex Docs Scroll Area + MDN -webkit-line-clamp**: стандартный CSS-паттерн max-height + overflow-y:auto для фикс-высотных зон → **REPLICATE** (сделано; без rx.scroll_area — меньше риска).

---

**NSS: 75/100** · Сделано: M7-инвойс доказан на проде (invoice_ok=True), устранено перекрытие mint-кнопок input'ом, +4 гварда, 418 тестов. · **След. итерация**: (1) починить data_persisted (age-based: сид старше boot-маркера), (2) полировка home-card mint-зоны (кнопки выше сгиба), (3) синхронизировать `tests: 414 → 418` в /health, (4) перепроверить KPI после деплоя. · **Действие владельца (критично для NSS=100)**: оплатить LN-инвойс ~3000 sats → «✅ I've paid — verify»; создать volume `terramon-data` → `/app/data`; разослать бота (M6/M8).
