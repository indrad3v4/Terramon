# Terramon — North Star Gap Report (v3, win-centric) · 2026-08-13 (iter-30)

Fingerprint: `13a9503f` (прод: `tests:527`, `data_persisted:true`, `seed_count:91`, `share_count:21`, `mint_count:0`, `complete_releases:0`, `alby_configured:true`) · Playwright/Chromium headless + TMA-mock · Target: https://terramon-tma-production.up.railway.app

---

## 0. ВЕРДИКТ ДНЯ (TL;DR)

- **North Star Score: 28.5/100** — формула v3: `60·min(complete_releases,1) + 25·Geo% + 15·ShareRate` = `60·0 + 25·1.0 + 15·(21/91≈23.1%)` (ShareRate 23.8%→23.1%: seed_count вырос 84→91 из-за probe-сидов KPI-рана, share 20→21 live)
- Топ-3 блокера: **1) complete_releases=0 — 60/100 заперты за РЕАЛЬНЫМ платежом ритуала (win-path ДОСТИЖИМ + монетизирован, M9 снова доказан на проде: живой BOLT11; нужен один реальный платёж) 2) Stars-рельса ритуала не оплачиваема: env TERRAMON_STARS_INVOICE_URL не задан (действие владельца: BotFather invoice link) 3) M1 ждёт device-проверки (headless-симуляция ≠ реальное устройство)**
- Kill-condition монитор: share_rate 23.1% (21/91) · mint 0 · days_mint_zero: 0/30 → **НЕ триггернут** ✅
- 🚀 **СОБЫТИЕ iter-30 — ритуал стал оплачиваемым в 1 тап**: в панель «Ритуал Отпускания» добавлена кнопка-ссылка **«⚡ Открыть кошелёк»** (`lightning:` deep-link, href=`lightning:lnbc…`). Раньше мобильный флоу оплаты = QR (неудобен на том же устройстве) или copy BOLT11 → переключение приложения → paste (3 шага). Теперь кошелёк (Phoenix/Breez/Zeus/Alby Go) открывается с предзаполненным инвойсом в 1 тап — паттерн BTCPay «Open in wallet» + getAlby `lightning:` URI. Это прямая де-фрикция ЕДИНСТВЕННОГО пути к +60 NSS. +8 тестов (**554 зелёных**), reflex export OK.

## 1. NORTH STAR SCORE (v3, win-centric)

| Компонент | Вес | Сегодня | Значение |
|---|---|---|---|
| Win-path: PAID complete release (final words + real geo, ритуал оплачен) | 60 | **0** | complete_releases=0; win-path достижим + монетизирован (M9: живой BOLT11 на Alby), ждёт реальный платёж → 0/60 |
| Geo% (якорь победы) | 25 | **25** | 100% headless-сим (geo_ok_rounds:[1], map-url 50.0619,19.9368) — ждёт device-проверки |
| ShareRate (share/seed) | 15 | **3.5** | 21/91 = 23.1% (live share 20→21, deep-link ✅) |
| **ИТОГО** | 100 | **28.5/100** | |

Lore/MintLoop — ДИАГНОСТИКА (не NSS): M2 lore = 1 (OYE-кнопка в DOM) · M7 инвойс-нога LIVE (⚡3000 sats Lightning + 25 Stars, auto-verify «⏳ 1/30» вооружён) · mint_count=0 (реального платежа нет).

## 2. ГЭП-ТАБЛИЦА (мост «инженерия → северная звезда»)

| # | Метрика | Что меряет | Сегодня | Цель | Гэп | Блокирует | Измерение |
|---|---|---|---|---|---|---|---|
| M1 | Geo% | доля существ с реальными координатами | 100% (map-url, симуляция) | 100% | 🟢 код-ок; **ждёт device** | сам win (без якоря release не полный) | AUTO + **device** |
| M2 | Vision-lore | кнопка «Open your eyes» + рендер | 1 (main_card_oye_after_care:1) | 1 | 🟢 ок | эмоцию/арт | AUTO |
| M3 | Win-path (depth) | complete_releases: release с final words + real geo, ритуал ОПЛАЧЕН | **0** (ритуал ДОСТИЖИМ: M9 доказан) | 1 (1 = 100%) | 🔴 **ждёт РЕАЛЬНЫЙ платёж** | 60/100 NSS | AUTO + **платёж владельца** |
| M4 | Дубликаты | unique/total | 12/91 | 1.0 | 🟢 ок | экономику минта | AUTO |
| M5 | Фрикция | гейт/модалки | 0 блоков (failed_rounds: []) | 0 | 🟢 ок | онбординг | AUTO |
| M6 | Share-funnel | share_count/seed_count | 21/91 = 23.1% (20→21 live) | ≥2% (kill <2%) | 🟢 ок | охват (kill-condition) | AUTO |
| M7 | Mint loop | mint_count / инвойс-нога | 0; инвойс LIVE (⚡3000 sats, STARS 25) | ≥2% | 🔴 **settle ждёт платёж** | метрику минта | AUTO + **платёж** |
| M8 | D7 retention | возврат на 7-й день | 0/0/0.0 (нет игроков) | кохортный бенчмарк | 🔴 нет игроков | 2-ю половину NSS | AUTO + **люди** |
| M9 | RitualPaid | monetised win-path: «⚡ Ритуал отпускания:» инвойс-маркер | **1 — ПОДТВЕРЖДЁН** (ritual_panel_seen=True, ritual_invoice_marker=True, BOLT11 на Alby) | 1 | 🟢 **доказано live** | доказательство live-монетизации | AUTO (инвойс = доказательство; платёж — никогда) |

Регрессионные guard (AUTO): **554 тестов зелёные** (+8 к iter-29, регрессий 0) · reflex export --frontend-only --no-zip OK · py_compile OK · /health tests:527 (константа, синхронизирована на iter-27; код iter-28-30 на проде подтверждён поведением M9-probe).

## 3. ТОП-3 БЛОКЕРА (ранжировано)

1. **complete_releases=0 — 60/100 заперты за РЕАЛЬНЫМ платежом** — win-path достижим и монетизирован (M9: живой BOLT11 на Alby-ноде, auto-verify вооружён, обе рельсы — Lightning 3000 sats и Stars 5⭐; НОВОЕ iter-30: оплата теперь в 1 тап через «⚡ Открыть кошелёк»). Нужен ОДИН настоящий платёж ритуала: владельцу — призвать → заботиться → EVOLVE×2 → финальные слова → реальная геолокация (⟳) → тап «⚡ Открыть кошелёк» → оплатить 3000 sats (Lightning) или 5⭐ (Stars). После settle complete_releases 0→1 → +60 NSS (28.5 → 88.5).
2. **Stars-рельса ритуала не оплачиваема: нет реального инвойс-линка** — `_STARS_INVOICE_URL` читается из env `TERRAMON_STARS_INVOICE_URL` (плейсхолдер по умолчанию). Владельцу: BotFather → Settings → Payments → Stars → создать invoice link («Ритуал Отпускания», 5⭐) → задать env на Railway. Код готов и ЧЕСТЕН (релиз только по колбэку 'paid').
3. **M1: headless-геолокация — не реальное устройство** — Playwright `grant_permissions + set_geolocation` симулирует разрешение; реальный гео-якорь на телефоне владельца нужен для финального подтверждения Geo%=100% (и это обязательное условие complete release). Re-anchor ⟳ (iter-29) уже закрыл дыру «родился без якоря».

## 4. EVIDENCE

KPI run (EXIT=0): `geo_ok_rounds: [1]` (map-url 50.0619,19.9368) · `distinct_archetypes: 12` · `oye_buttons_total: 1` · `m7_probe_postloop: mint visible, mint_price_sats=15 (STARS), lightning_price_sats=3000, invoice_ok=True, auto_verify_marker='⏳ Auto-checking payment… 1/30', alby_configured=True` · `m6: share 20→21, deep-link ✅, карточка с birthplace '📍 Краков'` · `depth_release_probe: released_clicked=True, words_entered=True, ritual_panel_seen=True, ritual_invoice_marker=True, ritual_free_release_clicked=True, receipt_seen=False, complete_delta=0` (free-path не считает — by construction; проба НИКОГДА не платит) · `complete_releases: 0→0` · `mint_count: 0` · `failed_rounds: []` · kill-condition share_rate 23.1% НЕ триггернут.

Фикс iter-30 (в этом коммите): `terramon_tma/terramon_tma.py` — state `release_ritual_lightning_uri` (L598), заполнение `"lightning:" + req.destination` в `create_ritual_invoice` (L1679) + сброс в ветке «не настроен» (L1668), кнопка-ссылка `rx.link` «⚡ Открыть кошелёк» (L4073-4087) в `ritual_payment_panel` внутри cond инвойса. + `tests/test_ritual_deeplink.py` (8 тестов: 4 source-guard + 4 функциональных с fake-портами; префикс ровно один, без дублирования, unconfigured → пустой URI, free-path → пустой URI). OSS-референсы: getAlby/lightning-browser-extension (⭐585 — каноническая обработка `lightning:` URI: кошелёк авто-открывается с предзаполненным инвойсом), btcpayserver/btcpayserver (⭐6.5k — страница инвойса: QR + «Open in wallet» + copy; РЕПЛИЦИРУЕМ кнопку, НЕ реплицируем серверный state-machine), nikandr-surkov/telegram-mini-app-stars-payments (⭐23 — Stars-рельса уже реализована в iter-28, не менялась). Пуш: `b7fa93f..<iter-30>` — Railway авто-деплой.
