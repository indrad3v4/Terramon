# Terramon — North Star Gap Report (v3, win-centric) · 2026-08-13 (iter-32)

Fingerprint: `f2ac49e7` (прод: `tests:527`, `data_persisted:false`, `seed_count:98`, `share_count:23`, `mint_count:0`, `complete_releases:0`, `alby_configured:true`) · Playwright/Chromium headless + TMA-mock · Target: https://terramon-tma-production.up.railway.app

---

## 0. ВЕРДИКТ ДНЯ (TL;DR)

- **North Star Score: 28.5/100** — формула v3: `60·min(complete_releases,1) + 25·Geo% + 15·ShareRate` = `60·0 + 25·1.0 + 15·(23/98≈23.5%)`
- Топ-3 блокера: **1) complete_releases=0 — 60/100 заперты за РЕАЛЬНЫМ платежом ритуала (M9 СНОВА доказан live в этом ране прямым зондом: ритуал-панель + живой BOLT11 lnbc30u1p48… на 3000 sats; win-path достижим — нужен один настоящий платёж) 2) Stars-рельса ритуала не оплачиваема: TERRAMON_STARS_INVOICE_URL не задан (действие владельца: BotFather invoice link) 3) mint_count=0 — первый реальный минт/платёж (инвойс-нога LIVE, settle ждёт)**
- Kill-condition монитор: share_rate 23.5% (23/98) · mint 0 · days_mint_zero: 0/30 → **НЕ триггернут** ✅
- 🛠️ **СОБЫТИЕ iter-32 — измерение снова честное**: KPI depth-проба в этом ране НЕ подтвердила M9 (words_entered=False — textarea не найден за 10s), НО прямой wire-диаг (diag_iter32b.py) доказал, что приложение в порядке: диалог рендерит ровно один `<textarea>` (visible, placeholder «Последние слова…»), и полный флоу «слова → confirm → ритуал-панель» работает на проде: ritual_panel_seen=True, ritual_invoice_marker=True (настоящий BOLT11 на Alby-ноде, 3000 sats = RITUAL_RELEASE_SATS). Это была флаки-проба, не регрессия кода. Фикс (в этом коммите): полл textarea 10s→**30s**, полл ритуал-маркеров 12s→**20s** (Reflex 0.9.8 применяет дельты асинхронно, латентность документирована 0.8s–>15s+), при таймауте — самодиагностирующий блок (count/visible/bbox/placeholder textarea+input, наличие текста диалога, сниппет body). Паттерн — из OSS: reflex-dev/reflex (★28.8k, `reflex/testing.py::_poll_for` — deadline-поллинг вместо фикс-снов) и microsoft/playwright (auto-wait: ретраи до дедлайна + явная диагностика при провале).

## 1. NORTH STAR SCORE (v3, win-centric)

| Компонент | Вес | Сегодня | Значение |
|---|---|---|---|
| Win-path: PAID complete release (final words + real geo, ритуал оплачен) | 60 | **0** | complete_releases=0; win-path ДОСТИЖИМ и монетизирован (M9: живой BOLT11 на Alby, прямой зонд iter-32), ждёт реальный платёж → 0/60 |
| Geo% (якорь победы) | 25 | **25** | 100% headless-сим (geo_ok_rounds:[1], map-url 50.0619,19.9368) — ждёт device-проверки |
| ShareRate (share/seed) | 15 | **3.5** | 23/98 = 23.5% (share 22→23 live, deep-link ✅) |
| **ИТОГО** | 100 | **28.5/100** | |

Lore/MintLoop — ДИАГНОСТИКА (не NSS): M2 lore = 1 (OYE-кнопка в DOM) · M7: mint_count=0, инвойс-нога LIVE (⚡3000 sats / STARS 25⭐, auto-verify вооружён 1/30) · M9 ритуал: BOLT11 LIVE (прямой зонд).

## 2. ГЭП-ТАБЛИЦА (мост «инженерия → северная звезда»)

| # | Метрика | Что меряет | Сегодня | Цель | Гэп | Блокирует | Измерение |
|---|---|---|---|---|---|---|---|
| M1 | Geo% | доля существ с реальными координатами | 100% (map-url, симуляция) | 100% | 🟢 код-ок; **ждёт device** | сам win (без якоря release не полный) | AUTO + **device** |
| M2 | Vision-lore | кнопка «Open your eyes» + рендер | 1 (main_card_oye_after_care:1) | 1 | 🟢 ок | эмоцию/арт | AUTO |
| M3 | Win-path (depth) | complete_releases: release с final words + real geo, ритуал ОПЛАЧЕН | **0** (ритуал ДОСТИЖИМ: M9 прямой зонд) | 1 (1 = 100%) | 🔴 **ждёт РЕАЛЬНЫЙ платёж** | 60/100 NSS | AUTO + **платёж владельца** |
| M4 | Дубликаты | unique/total | 12/98 | 1.0 | 🟢 ок | экономику минта | AUTO |
| M5 | Фрикция | гейт/модалки | 0 блоков (failed_rounds: []) | 0 | 🟢 ок | онбординг | AUTO |
| M6 | Share-funnel | share_count/seed_count | 23/98 = 23.5% (22→23 live) | ≥2% (kill <2%) | 🟢 ок | охват (kill-condition) | AUTO |
| M7 | Mint loop | mint_count / инвойс-нога | 0; инвойс-нога LIVE (⚡3000 sats, STARS 25⭐, auto-verify 1/30) | ≥2% | 🔴 **settle ждёт платёж** | метрику минта | AUTO + **платёж** |
| M8 | D7 retention | возврат на 7-й день | 0/0/0.0 (нет игроков) | кохортный бенчмарк | 🔴 нет игроков | 2-ю половину NSS | AUTO + **люди** |
| M9 | RitualPaid | monetised win-path: «⚡ Ритуал отпускания:» инвойс-маркер | **1 — ПОДТВЕРЖДЁН прямым зондом** (ritual_panel_seen=True, ritual_invoice_marker=True, BOLT11 lnbc30u1p48… 3000 sats на Alby) | 1 | 🟢 **доказано live** | доказательство live-монетизации | AUTO (инвойс = доказательство; платёж — никогда) |

Регрессионные guard (AUTO): **563 теста зелёные** (регрессий 0) · reflex export --frontend-only --no-zip OK · py_compile OK · /health tests:527 (константа).

## 3. ТОП-3 БЛОКЕРА (ранжировано)

1. **complete_releases=0 — 60/100 заперты за РЕАЛЬНЫМ платежом** — win-path достижим и монетизирован (M9: прямой зонд iter-32 создал живой BOLT11 на Alby-ноде, auto-verify вооружён, обе рельсы — Lightning 3000 sats и Stars 5⭐, оплата в 1 тап «⚡ Открыть кошелёк», escape-hatch «🔄 Новый инвойс» на месте). Нужен ОДИН настоящий платёж ритуала: призвать → заботиться → EVOLVE×2 → финальные слова → реальная геолокация (⟳) → «⚡ Открыть кошелёк» → оплатить 3000 sats (Lightning) или 5⭐ (Stars). После settle complete_releases 0→1 → +60 NSS (28.5 → 88.5).
2. **Stars-рельса ритуала не оплачиваема: нет реального инвойс-линка** — `_STARS_INVOICE_URL` читается из env `TERRAMON_STARS_INVOICE_URL` (плейсхолдер по умолчанию). Владельцу: BotFather → Settings → Payments → Stars → создать invoice link («Ритуал Отпускания», 5⭐) → задать env на Railway. Код готов и ЧЕСТЕН (релиз только по колбэку 'paid').
3. **mint_count=0 — монетизация минта ждёт первого реального платежа** — инвойс-нога live (⚡3000 sats / 25⭐, auto-verify 1/30 виден), но settle-колбэка ещё не было. Диагностика, не NSS; первый реальный минт/ритуал разблокирует и метрику, и доход.

## 4. EVIDENCE

KPI run (EXIT=0): `geo_ok_rounds: [1]` (map-url 50.0619,19.9368) · `distinct_archetypes: 12` · `oye_buttons_total: 1` · `m7_probe_postloop: MINT live, invoice_ok=True, auto_verify_seen=True ('⏳ Auto-checking payment… 1/30'), ⚡3000 sats / STARS 25⭐` · `m6: share 22→23 live, deep-link ✅, карточка с birthplace '📍 Краков'` · `depth_release_probe: released_clicked=True, words_entered=False, ritual_panel_seen=False, ritual_invoice_marker=False` (ПРОБА флакнула на шаге слов — текст диалога был в body, но textarea не найден за 10s; зафиксировано честно) · `complete_releases: 0→0` · `mint_count: 0` · `failed_rounds: []` · kill-condition share_rate 23.5% НЕ триггернут.

**Прямой wire-диаг iter-32 (diag_iter32b.py, тот же прод-деплой):** диалог рендерит ровно 1 `<textarea>` (visible=True, bbox 274×48, placeholder «Последние слова (необязательно)...»), geo-якорь на месте («📍 Краков, Польша»), полный флоу: слова → confirm → **ritual_panel_seen=True, ritual_invoice_marker=True** (реальный BOLT11 `lnbc30u1p48…` на 3000 sats; платёж НЕ выполнялся — создание инвойса и есть доказательство). Вывод: приложение в порядке, M9 live, флаки была в пробе.

Фикс iter-32 (в этом коммите): `scripts/kpi/play_to_win.py` — `run_depth_release_probe`: полл textarea 10s→**30s** (L834, зеркалит 40s-полл кнопки релиза), полл ритуал-маркеров 12s→**20s** (L936, Alby HTTP-латентность); при таймауте textarea — самодиагностирующий блок (L848-890): count/visible/bounding_box/placeholder всех textarea и input, наличие текста диалога «Существо останется жить» в body, сниппет body на 200 симв. Маркеры и ключи depth_probe не тронуты. OSS-референсы: reflex-dev/reflex (★28.8k — `reflex/testing.py::_poll_for`: deadline-поллинг для асинхронных state-дельт; РЕПЛИЦИРУЕМ дедлайн-поллинг, НЕ реплицируем внутренности фреймворка), microsoft/playwright (auto-wait + retry-семантика `expect().to_be_visible(timeout)`; РЕПЛИЦИРУЕМ «ретраи до дедлайна + явная диагностика провала»), codingforentrepreneurs/full-stack-python (★138 — Reflex E2E: ждать UI-изменений по событию, никогда фикс-сны; поддерживает). Проверено: py_compile OK · pytest **563 passed** (регрессий 0) · reflex export --frontend-only --no-zip OK. Пуш: `<iter-31>..<iter-32>` — Railway авто-деплой.
