# Terramon — North Star Gap Report (v3, win-centric) · 2026-08-13 (iter-33)

Fingerprint: `de7e43d9` (прод: `tests:527`, `data_persisted:false`, `seed_count:100`, `share_count:24`, `mint_count:0`, `complete_releases:0`, `alby_configured:true`) · Playwright/Chromium headless + TMA-mock · Target: https://terramon-tma-production.up.railway.app

---

## 0. ВЕРДИКТ ДНЯ (TL;DR)

- **North Star Score: 28.6/100** — формула v3: `60·min(complete_releases,1) + 25·Geo% + 15·ShareRate` = `60·0 + 25·1.0 + 15·(24/100=24%)`
- Топ-3 блокера: **1) complete_releases=0 — 60/100 заперты за РЕАЛЬНЫМ платежом ритуала (M9 в этом ране доказан ПОЛНЫМ depth-флоу: слова → confirm → ритуал-панель → живой BOLT11 lnbc30u1p48… 3000 sats; нужен один настоящий платёж) 2) Stars-рельса ритуала заглушена честно («— скоро») пока владелец не задаст TERRAMON_STARS_INVOICE_URL (мёртвый placeholder больше не кликабелен — тупик убран iter-33) 3) player_count=0 — mint/D7/device-гео ждут реальных людей и платежей**
- Kill-condition монитор: share_rate 24% (24/100) · mint 0 · days_mint_zero: 0/30 → **НЕ триггернут** ✅
- 🛠️ **СОБЫТИЕ iter-33 — последние метры win-path**: (а) убран тупик на единственном пути к +60: Stars-кнопка ритуала с мёртвым placeholder-URL (openInvoice → ошибка Telegram) теперь гейтится флагом `_STARS_RAIL_LIVE` (env `TERRAMON_STARS_INVOICE_URL` задан = live; иначе disabled «— скоро» + guard в `pay_ritual_stars`); (б) чек отпускания получил боевую CTA «📤 Поделиться отпусканием» → share_count растёт прямо из момента победы (ShareRate = 15% NSS); (в) KPI-проба честно меряет рендер чека после free-release (`free_release_receipt_seen`, 10s-полл). Паттерны — из OSS: btcpay/btcpayserver (★7.7k, active) — «никогда не веди пользователя на мёртвую платёжную рельсу», Priler/telegramStarsBot (★42) + xep1x/telegram-bot-payments (★25, active 2025-11) — openInvoice требует РЕАЛЬНЫЙ BotFather invoice link, placeholder = ошибка; getAlby/lightning-browser-extension (★585) — BOLT11-copy + deep-link в паре (уже live, не тронуто).

## 1. NORTH STAR SCORE (v3, win-centric)

| Компонент | Вес | Сегодня | Значение |
|---|---|---|---|
| Win-path: PAID complete release (final words + real geo, ритуал оплачен) | 60 | **0** | complete_releases=0; win-path ДОСТИЖИМ и монетизирован (M9: полный depth-флоу, живой BOLT11 на Alby, auto-verify, refresh-инвойс, deep-link), ждёт реальный платёж → 0/60 |
| Geo% (якорь победы) | 25 | **25** | 100% headless-сим (geo_ok_rounds:[1,2], map-url 50.0619,19.9368) — ждёт device-проверки |
| ShareRate (share/seed) | 15 | **3.6** | 24/100 = 24% (share 23→24 live, deep-link ✅, карточка с birthplace) |
| **ИТОГО** | 100 | **28.6/100** | |

Lore/MintLoop — ДИАГНОСТИКА (не NSS): M2 lore = 2 (OYE в DOM) · M7: mint_count=0, инвойс-нога LIVE (⚡3000 sats / 15⭐, auto-verify 1/30 armed) · M9 ритуал: BOLT11 LIVE (полный флоу).

## 2. ГЭП-ТАБЛИЦА (мост «инженерия → северная звезда»)

| # | Метрика | Что меряет | Сегодня | Цель | Гэп | Блокирует | Измерение |
|---|---|---|---|---|---|---|---|
| M1 | Geo% | доля существ с реальными координатами | 100% (map-url, симуляция; place_name [null,null]) | 100% | 🟢 код-ок; **ждёт device** | сам win (без якоря release не полный) | AUTO + **device** |
| M2 | Vision-lore | кнопка «Open your eyes» + рендер | 2 (main_card_oye_after_care:2) | 1 | 🟢 ок | эмоцию/арт | AUTO |
| M3 | Win-path (depth) | complete_releases: release с final words + real geo, ритуал ОПЛАЧЕН | **0** (ритуал ДОСТИЖИМ: M9 полный флоу) | 1 (1 = 100%) | 🔴 **ждёт РЕАЛЬНЫЙ платёж** | 60/100 NSS | AUTO + **платёж владельца** |
| M4 | Дубликаты | unique/total | 12/100 | 1.0 | 🟢 ок | экономику минта | AUTO |
| M5 | Фрикция | гейт/модалки | 0 блоков (failed_rounds: []) | 0 | 🟢 ок | онбординг | AUTO |
| M6 | Share-funnel | share_count/seed_count | 24/100 = 24% (23→24 live) | ≥2% (kill <2%) | 🟢 ок | охват (kill-condition) | AUTO |
| M7 | Mint loop | mint_count / инвойс-нога | 0; инвойс-нога LIVE (⚡3000 sats, 15⭐, auto-verify 1/30) | ≥2% | 🔴 **settle ждёт платёж** | метрику минта | AUTO + **платёж** |
| M8 | D7 retention | возврат на 7-й день | 0/0/0.0 (нет игроков) | кохортный бенчмарк | 🔴 нет игроков | 2-ю половину NSS | AUTO + **люди** |
| M9 | RitualPaid | monetised win-path: «⚡ Ритуал отпускания:» инвойс-маркер | **1 — ПОДТВЕРЖДЁН полным флоу** (released_clicked=True, words_entered=True, ritual_panel_seen=True, ritual_invoice_marker=True, BOLT11 lnbc30u1p48… 3000 sats на Alby; платёж НЕ выполнялся) | 1 | 🟢 **доказано live** | доказательство live-монетизации | AUTO (инвойс = доказательство; платёж — никогда) |

Регрессионные guard (AUTO): **568 тестов зелёные** (было 563, +5 новых, регрессий 0) · reflex export --frontend-only --no-zip OK · py_compile OK · /health tests:527 (константа).

## 3. ТОП-3 БЛОКЕРА (ранжировано)

1. **complete_releases=0 — 60/100 заперты за РЕАЛЬНЫМ платежом** — win-path достижим и монетизирован: M9 в ЭТОМ ране подтверждён ПОЛНЫМ depth-флоу (фикс 30s-полла iter-32 сработал: `words_entered=True`, ритуал-панель открылась, BOLT11 lnbc30u1p48… на 3000 sats live; проба честно закрыла панель free-путём). Нужен ОДИН настоящий платёж: призвать → заботиться → EVOLVE×2 → финальные слова → реальная геолокация (⟳) → «⚡ Открыть кошелёк» → оплатить 3000 sats (Lightning) или 5⭐ (Stars). После settle complete_releases 0→1 → +60 NSS (28.6 → 88.6).
2. **Stars-рельса ритуала: честно заглушена до настройки инвойса** — iter-33 убрал мёртвый placeholder-URL (openInvoice с ним = ошибка Telegram): `_STARS_RAIL_LIVE` гейтит кнопку (disabled «— скоро» + guard в `pay_ritual_stars`). Владельцу: BotFather → Settings → Payments → Stars → invoice link («Ритуал Отпускания», 5⭐) → env `TERRAMON_STARS_INVOICE_URL` на Railway — кнопка оживёт сама, код готов и ЧЕСТЕН (релиз только по колбэку 'paid').
3. **player_count=0 — mint/D7/device-гео ждут реальных людей** — mint_count=0 (инвойс-нога live, settle ждёт), D7 без кохорты, гео-проверка на реальном телефоне не делалась. Диагностика/вторая половина NSS; первый реальный игрок/платёж разблокирует.

## 4. EVIDENCE

KPI run (EXIT=0): `geo_ok_rounds: [1,2]` (map-url 50.0619,19.9368) · `place_name_rounds: [null,null]` (честно: ⟳-кнопки в раундах не было — autoLocation через mock) · `distinct_archetypes: 12` · `oye_buttons_total: 2` · `m7_probe_postloop: MINT live, invoice_ok=True, auto_verify_seen=True ('⏳ Auto-checking payment… 1/30'), ⚡3000 sats / STARS 15⭐` · `m6: share 23→24 live (share_delta=1), deep-link ✅, share_card_has_birthplace=True ('📍 Краков, Пол…')` · `depth_release_probe: released_clicked=True, words_entered=True (30s-полл сработал), ritual_panel_seen=True, ritual_invoice_marker=True (BOLT11 lnbc30u1p48myxcdrs… 3000 sats, Alby), ritual_free_release_clicked=True, receipt_seen=False (чек до free-клика — by design), complete_releases: 0→0` · `mint_count: 0` · `failed_rounds: []` · kill-condition share_rate 24% НЕ триггернут.

**Изменения iter-33 (коммит c0c3648, запушен, Railway авто-деплой):**
- `terramon_tma/terramon_tma.py`: `_STARS_RAIL_LIVE` (L300) — гейт Stars-рельсы ритуала; guard в `pay_ritual_stars` (L1817-1825, до `ritual_stars_pending=True`); панель: live-ветка побайтово прежняя + disabled-ветка «Оплатить ритуал · 5 Stars — скоро»/`disabled=True`/«Stars-инвойс ещё не подключён — используй ⚡ Lightning.» (L4220-4269); чек отпускания: CTA «📤 Поделиться отпусканием» → `share_creature` (L3216) + подсказка с сохранённым маркером «отпустил свою мысль» (L3222).
- `scripts/kpi/play_to_win.py`: `free_release_receipt_seen` (инит L726, 10s-полл после free-клика L966-984, пометка в NSS-EVIDENCE L1370).
- `tests/`: +5 тестов (test_ritual_stars_honest.py: rail-флаг, порядок guard, disabled-состояние панели, offline-click функциональный; test_ritual_release.py: receipt share CTA); функциональная фикстура симулирует LIVE Stars-рельсу.
- Проверено: py_compile OK · pytest **568 passed** (регрессий 0) · reflex export --frontend-only --no-zip OK. Пуш: `fc772e3..c0c3648` — remote подтвердил.
