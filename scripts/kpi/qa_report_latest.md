# Terramon — North Star Gap Report (v2) · 2026-08-10 (iter-17)

Fingerprint: `0a88807e` (текущий прод-деплой: `tests:421`, `data_persisted:false` — честный сигнал: Railway volume НЕ примонтирован, данные стёрты редеплоем) · Playwright/Chromium headless + TMA-mock · Target: https://terramon-tma-production.up.railway.app

---

## 0. ВЕРДИКТ ДНЯ (TL;DR)

- **North Star Score: 75/100** (плато 6-я итерация; Geo/Lore/Win-path железно; M7 инвойс-нога ДОКАЗАНА на проде 4-й раз; settle ждёт реального платежа)
- Топ-3 блокера: **1) M7 settle-нога: нужен РЕАЛЬНЫЙ ПЛАТЁЖ владельца (~3000 sats) 2) нет реальных игроков (M6/M8) 3) Railway volume НЕ примонтирован — данные стираются при каждом редеплое (`data_persisted:false`)**
- Kill-condition монитор: share 1 · mint 0 · дней с mint=0: ~18/30 → **НЕ в зоне риска (readiness-фаза)**
- 🎯 **ГЛАВНОЕ СОБЫТИЕ iter-17**: **автопроверка оплаты Lightning (auto-verify)** — после создания BOLT11-инвойса приложение само опрашивает Alby Hub каждые 6 с (до 30 попыток / ~3 мин) через скрытый `rx.moment`-таймер; при settle минт записывается АВТОМАТИЧЕСКИ, без клика «✅ I've paid — verify» (кнопка остаётся fallback'ом). Это убирает главный UX-риск MintLoop: раньше оплативший игрок, не нажавший verify (или закрывший приложение), терял минт. Теперь «оплатил → минт записан» гарантирован, пока страница открыта. Прямой удар по M7 → северной звезде.

## 1. NORTH STAR SCORE (композит)

| Компонент | Вес | Сегодня | Нормализация |
|---|---|---|---|
| Geo-привязка | 25 | **100%** (12/12) | static-map URL с реальными координатами (50.0619, 19.9368); headless-симуляция, ждёт device-проверки |
| Vision-lore («Open your eyes») | 25 | **1** | кнопка в DOM на главной карточке + после Care-таба |
| Win-path (достижимость) | 25 | **12/12** | min(архетипов/12, 1) — полная вселенная |
| Mint-loop | 25 | **0** | инвойс создан (invoice_ok=True, 4-й прогон), settle не было → mint_count=0 |
| **ИТОГО** | 100 | **75/100** | |

Боевая формула (включается, когда есть реальные игроки): NSS = 40·MintRate + 30·D7 + 15·Geo + 15·Lore.

## 2. ГЭП-ТАБЛИЦА (мост «инженерия → северная звезда»)

| # | Метрика | Что меряет | Сегодня | Цель | Гэп | Блокирует | Измерение |
|---|---|---|---|---|---|---|---|
| M1 | Geo% | доля существ с реальными координатами | 12/12 (100%) | 100% | 🟢 код-ок; ждёт device-проверки | share-петлю | AUTO + **device** |
| M2 | Vision-lore | «Open your eyes» + рендер лора | 1 | 1 | 🟢 ок | эмоцию/арт | AUTO |
| M3 | Win-path | уникальные архетипы за прогон | 12/12 | 12/12 | 🟢 ок | контентную глубину → D7 | AUTO |
| M4 | Дубликаты | unique/total | 12/12 в прогоне (probe-сиды 14+ на проде) | 1.0 | 🟢 ок (dedup работает) | экономику минта | AUTO |
| M5 | Фрикция | гейт/модалки | 0 блоков (failed_rounds: []) | 0 | 🟢 ок | онбординг → D7 | AUTO |
| M6 | Share-funnel | доля сессий с share-тапом | счётчик работает (share=1 на проде) | ≥2% (kill <2%) | 🔴 нет игроков | охват (kill-condition) | AUTO + **люди** |
| M7 | Mint rate | % саммонеров с mint | 0 (mint_count=0) | ≥2% | 🔴 **инвойс-нога ДОКАЗАНА (4-й раз); settle ждёт платёж; auto-verify устранил UX-риск потери минта** | саму северную звезду | AUTO + **платёж владельца** |
| M8 | D7 retention | возврат на 7-й день | нет данных | кохортный бенчмарк | 🔴 нет игроков | 2-ю половину NSS | **люди** |

Регрессионные guard: **437 тестов зелёные** (429 + 8 новых: 3 source-guard auto-verify + 5 поведенческих) · reflex export собирается (exit 0, в JSX виден `jsx(Moment,{interval:6000,...})`) · /health tests count синхронизирован 421→429→**437** (в т.ч. починен guard, сломанный с iter-16: рабочее дерево уже имело `"tests":429`, guard ждал 421 → 1 fail; теперь сходится).

## 3. ТОП-3 БЛОКЕРА (ранжировано)

1. **M7 settle-нога — нужен реальный платёж владельца.** Инвойс-создание доказано на проде 4 раза подряд (`invoice_ok:true`, «⚡ Invoice ready» — Magician post-loop проба). mint_count=0, потому что никто не платил. Теперь код-сайд готов и к settle: auto-verify сам опросит Alby Hub и запишет минт. → **Owner action**: открыть приложение в Telegram, призвать существо (англ. мысль, 1-5 призывов), дождаться mint-кнопки, нажать «⚡ Mint via Lightning» (~3000 sats), оплатить из LN-кошелька — минт запишется АВТОМАТИЧЕСКИ (или нажать «✅ I've paid — verify») → mint_count станет 1 → NSS = 100 (MintLoop 25/25).
2. **Нет реальных игроков (M6/M8).** Все seed_count на проде — probe-сиды KPI-прогонов. → **Owner action**: запустить тестовую аудиторию/друзей, замерить share% и D7.
3. **Railway volume НЕ примонтирован** (подтверждено iter-16 фиксом, подтверждается снова): `data_persisted:false` на текущем деплое, данные стираются при каждом редеплое. Бизнес-эффект: mint-рекорды/игроки не переживут редеплой. → **Owner action**: в Railway dashboard создать volume `terramon-data` и примонтировать к сервису (railway.json уже декларирует mount /app/data).

## 4. EVIDENCE

- NSS-прогон: geo_ok 1/1 раундов (map-url) · distinct 12/12 · OYE в DOM · mint_ui_state: «mint visible» в post-loop пробе · `invoice_ok:true`, «⚡ Invoice ready» (Magician) · mint_count_health: 0 · m6 share_count: 1 (без дельты — раунд без успешного summon) · failed_rounds: []
- Auto-verify (iter-17): `LIGHTNING_VERIFY_INTERVAL_MS=6000` / `LIGHTNING_VERIFY_MAX_ATTEMPTS=30` (terramon_tma.py:238-246) · state: `lightning_auto_verify`/`lightning_verify_attempts` (:364-365) · arm в `mint_lightning` (:1738-1741) и `pay_lightning` (:1857-1860) · `verify_lightning(self, _tick=None)` (:1866-1941): stale-timer silent stop, settle→disarm+`_record_mint`, poll-тик НЕ трогает `agent_message` (KPI-маркер «⚡ Invoice ready» защищён), give-up после 30 попыток с маркером «⏳ Payment not detected yet…», ручной путь байт-в-байт · панель (:3284-3310): вложенный cond (auto-checking → checking → кнопка) + `rx.moment(interval=6000, on_change=TerramonState.verify_lightning, display="none")`, гейт на `lightning_auto_verify` (таймер размонтируется при остановке)
- Тесты: +8 (3 source-guard: wired-on-invoice / auto-path-guarded / panel-timer-wired; 5 поведенческих: arm-on-invoice / settle-records-mint / poll-не-затирает-маркер / gives-up-to-manual+fallback-минт / manual-маркер-байт-в-байт) → **437 passed, 0 failed** · `reflex export --frontend-only --no-zip` exit 0 · все 7 KPI-маркеров байт-в-байт (проверено grep + marker-contract тесты)
- RESEARCH-референсы: **BTCPay Server** (docs.btcpayserver.org ecommerce-integration-guide / Invoices FAQ): create invoice → poll/event на статус → deliver на «settled»; LN-инвойсы сеттлятся мгновенно; таймер истечения → REPLICATE: ограниченный auto-poll (30×6с) + аккуратный ручной fallback; AVOID: безлимитный polling и внешняя checkout-страница (у нас инлайн BOLT11+QR). **Reflex periodic callback** (reflex-dev discussion #1970): `rx.moment(interval, on_change, display="none")` — единственный штатный периодический паттерн в Reflex 0.9.x (rx.timer НЕТ) → REPLICATE (on_change передаёт datetime → параметр `_tick=None`). **Alby Hub** (getalby/hub, NIP-47): `verify_payment`/lookup — оракул settle; мгновенный LN-settle → каденс 6с достаточен → REPLICATE без изменений.
- Ограничение честности: гео — симуляция device-разрешения (Playwright grant_permissions), нужен реальный девайс; TMA — injected-mock (headless без Telegram runtime), initData hash FAKE без бот-токена; auto-verify проверен юнит-тестами на фейковом Alby — боевой settle ждёт реального платежа.

---

**NSS: 75/100** · Сделано: Lightning auto-verify (минт записывается сам при settle — 0 кликов, ручной verify как fallback, KPI-маркер защищён), /health tests count 429→437 + починен сломанный с iter-16 guard (421→429→437), +8 гвардов, 437 тестов. · **След. итерация**: (1) перепроверить KPI после деплоя (ждём `tests:437` + auto-verify активен на проде: в probe-сессии после клика mint появятся тики опроса), (2) полировка home-card mint-зоны (визуальный акцент кнопок выше сгиба — M5), (3) подготовка D7-кохорт (player_id → first_seen → возвраты) под боевую формулу. · **Действие владельца (критично для NSS=100)**: оплатить LN-инвойс ~3000 sats → минт запишется АВТОМАТИЧЕСКИ → M7=1 → NSS=100; примонтировать Railway volume (data_persisted); разослать бота (M6/M8).
