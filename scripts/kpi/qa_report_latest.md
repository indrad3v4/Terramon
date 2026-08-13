# Terramon — North Star Gap Report (v3, win-centric) · 2026-08-13 (iter-28)

Fingerprint: `53cfc114` (прод: `tests:527`, `data_persisted:false`, `seed_count:81`, `share_count:18`, `mint_count:0`, `complete_releases:0`, `alby_configured:true`) · Playwright/Chromium headless + TMA-mock · Target: https://terramon-tma-production.up.railway.app

---

## 0. ВЕРДИКТ ДНЯ (TL;DR)

- **North Star Score: 28.5/100** — формула v3: `60·min(complete_releases,1) + 25·Geo% + 15·ShareRate` = `60·0 + 25·1.0 + 15·(19/81)` (рост с 27.8 за счёт ShareRate 18.75%→23.5%)
- Топ-3 блокера: **1) complete_releases=0 — 60/100 заперты: win-path ДОСТИЖИМ и монетизирован (M9 доказан на проде!), но нужен ОДИН РЕАЛЬНЫЙ платёж ритуала (владелец) 2) Stars-рельса ритуала не оплачиваема: инвойс-линк BotFather не создан (env TERRAMON_STARS_INVOICE_URL) 3) M1 ждёт device-проверки (headless-симуляция, не реальное устройство)**
- Kill-condition монитор: share_rate 23.5% (19/81) · mint 0 · days_mint_zero: 0/30 → **НЕ триггернут** ✅
- 🚧 **ПУШ НЕ ПРОШЁЛ (блокер окружения, НЕ код)**: коммит `c235a3d` готов локально, но `GH_PAT` на хосте НЕДЕЙСТВИТЕЛЕН (GitHub API: 401 «Bad credentials»; push: «Invalid username or token»). Репозиторий публичный (чтение анонимное работает), но запись требует валидный fine-grained PAT. **Owner-action: обновить env `GH_PAT`** (fine-grained token, доступ `Contents: Read and write` к indrad3v4/Terramon) — следующий триггер запушит коммит, Railway задеплоит.
- 🎯 **ГЛАВНОЕ СОБЫТИЕ iter-28 — M9 ПОДТВЕРЖДЁН НА ПРОДЕ**: KPI-проба прошла ВЕСЬ ритуал: `ritual_panel_seen=True`, `ritual_invoice_marker=True` — «⚡ Ритуал отпускания:» с ЖИВЫМ BOLT11 (создан на Alby-ноде) — win-path РАЗБЛОКИРОВАН фиксом iter-27 и монетизация LIVE. complete_releases=0 честно: проба никогда не платит, реальных платежей ещё не было (free-path не считает ПО КОНСТРУКЦИИ).
- 🛡️ **НОВЫЙ ФИКС iter-28 — честность Stars-рельсы**: раньше `pay_ritual_stars` завершал релиз ОПТИМИСТИЧНО по клику, а `_STARS_INVOICE_URL` был ПЛЕЙСХОЛДЕРОМ (неоплачиваемый линк) → complete_releases (60/100!) можно было накрутить БЕЗ оплаты. Теперь релиз завершается ТОЛЬКО по реальному статусу `'paid'` колбэка openInvoice (паттерн nikandr-surkov/telegram-mini-app-stars-payments); URL читается из env. +11 тестов (538 зелёных).

## 1. NORTH STAR SCORE (v3, win-centric)

| Компонент | Вес | Сегодня | Значение |
|---|---|---|---|
| Win-path: PAID complete release (final words + real geo, ритуал оплачен) | 60 | **0** | complete_releases=0; win-path достижим + монетизирован (M9), ждёт реальный платёж → 0/60 |
| Geo% (якорь победы) | 25 | **25** | 100% headless-сим (geo_ok_rounds:[1], map-url 50.0619,19.9368) — ждёт device-проверки |
| ShareRate (share/seed) | 15 | **3.5** | 19/81 = 23.5% (live-проба share 18→19, deep-link ✅) |
| **ИТОГО** | 100 | **28.5/100** | |

Lore/MintLoop — ДИАГНОСТИКА (не NSS): M2 lore = 1 (OYE-кнопка в DOM) · M7 инвойс-нога LIVE (⚡3000 sats, auto-verify «⏳ 1/30» вооружён) · mint_count=0 (нет реального платежа).

## 2. ГЭП-ТАБЛИЦА (мост «инженерия → северная звезда»)

| # | Метрика | Что меряет | Сегодня | Цель | Гэп | Блокирует | Измерение |
|---|---|---|---|---|---|---|---|
| M1 | Geo% | доля существ с реальными координатами | 100% (map-url, симуляция) | 100% | 🟢 код-ок; **ждёт device** | сам win (без якоря release не полный) | AUTO + **device** |
| M2 | Vision-lore | кнопка «Open your eyes» + рендер | 1 (main_card_oye_after_care:1) | 1 | 🟢 ок | эмоцию/арт | AUTO |
| M3 | Win-path (depth) | complete_releases: release с final words + real geo, ритуал ОПЛАЧЕН | **0** (ритуал ДОСТИЖИМ: M9 доказан) | 1 (1 = 100%) | 🔴 **ждёт РЕАЛЬНЫЙ платёж** | 60/100 NSS | AUTO + **платёж владельца** |
| M4 | Дубликаты | unique/total | 12/81 | 1.0 | 🟢 ок | экономику минта | AUTO |
| M5 | Фрикция | гейт/модалки | 0 блоков (failed_rounds: []) | 0 | 🟢 ок | онбординг | AUTO |
| M6 | Share-funnel | share_count/seed_count | 19/81 = 23.5% (18→19 live) | ≥2% (kill <2%) | 🟢 ок | охват (kill-condition) | AUTO |
| M7 | Mint loop | mint_count / инвойс-нога | 0; инвойс LIVE (⚡3000 sats, STARS 15) | ≥2% | 🔴 **settle ждёт платёж** | метрику минта | AUTO + **платёж** |
| M8 | D7 retention | возврат на 7-й день | 0/0/0.0 (нет игроков) | кохортный бенчмарк | 🔴 нет игроков | 2-ю половину NSS | AUTO + **люди** |
| M9 | RitualPaid | monetised win-path: «⚡ Ритуал отпускания:» инвойс-маркер | **1 — ПОДТВЕРЖДЁН** (ritual_panel_seen=True, ritual_invoice_marker=True, BOLT11 на Alby) | 1 | 🟢 **доказано live** | доказательство live-монетизации | AUTO (инвойс = доказательство; платёж — никогда) |

Регрессионные guard (AUTO): **538 тестов зелёные** (+11 к прошлому, регрессий 0) · reflex export --frontend-only --no-zip OK · py_compile OK.

## 3. ТОП-3 БЛОКЕРА (ранжировано)

1. **complete_releases=0 — 60/100 заперты за РЕАЛЬНЫМ платежом** — win-path достижим и монетизирован (M9: живой BOLT11 на Alby-ноде, auto-verify вооружён, обе рельсы — Lightning 3000 sats и Stars 5⭐). Нужен ОДИН настоящий платёж ритуала: владельцу — призвать → заботиться → EVOLVE×2 → финальные слова → реальная геолокация (⟳) → оплатить 3000 sats (Lightning) или 5⭐ (Stars). После settle complete_releases 0→1 → +60 NSS (28.5 → 88.5).
2. **Stars-рельса ритуала не оплачиваема: нет реального инвойс-линка** — `_STARS_INVOICE_URL` теперь читается из env `TERRAMON_STARS_INVOICE_URL` (плейсхолдер по умолчанию). Владельцу: BotFather → Settings → Payments → Stars → создать invoice link («Ритуал Отпускания», 5⭐) → задать env на Railway. Код готов: релиз завершится по колбэку 'paid' (честный гейт, никаких накруток).
3. **M1: headless-геолокация — не реальное устройство** — Playwright `grant_permissions + set_geolocation` симулирует разрешение; реальный гео-якорь на телефоне владельца нужен для финального подтверждения Geo%=100% (и это обязательное условие complete release).

## 4. EVIDENCE

KPI run (EXIT=0): `geo_ok_rounds: [1]` (map-url 50.0619,19.9368) · `distinct_archetypes: 12` · `oye_buttons_total: 1` · `m7_probe_postloop: invoice_ok=True, lightning_price_sats=3000, mint_price_sats=15 (STARS), auto_verify_marker='⏳ Auto-checking payment… 1/30', alby_configured=True` · `m6: share 18→19, deep-link ✅, карточка с birthplace '📍 Краков'` · `depth_release_probe: released_clicked=True, words_entered=True, ritual_panel_seen=True, ritual_invoice_marker=True, ritual_free_release_clicked=True, receipt_seen=False, complete_delta=0` (free-path не считает — by construction) · `complete_releases: 0→0` · `mint_count: 0` · `failed_rounds: []` · kill-condition share_rate 23.5% НЕ триггернут.

Фикс iter-28 (в этом коммите): `terramon_tma/terramon_tma.py` — `_RITUAL_STARS_JS` (async-IIFE openInvoice→статус), `pay_ritual_stars` → payment-GATED (pending-флаг + `callback=TerramonState.on_ritual_stars_status`), новый `on_ritual_stars_status` (релиз ТОЛЬКО на 'paid'), `ritual_stars_pending` state + «⏳ Ожидание оплаты Stars…» в панели, `_STARS_INVOICE_URL` из env, сброс pending в free-path и verify. + `tests/test_ritual_stars_honest.py` (11 тестов: не-оптимистичность, колбэк-гейт, JS-мост, pending-state, env-url, функциональные paid/cancelled/failed/free). OSS-референсы: nikandr-surkov/telegram-mini-app-stars-payments (⭐23 — openInvoice callback, награда только в 'paid'), byteoxo/telegram-star-payments (Python — successful_payment как авторитетный сигнал; upgrade-путь). KPI-инструмент: `scripts/kpi/play_to_win.py` — робастный 40s-полл «💨 Отпустить» (эвиденс iter-33: LLM-латентность evolve 0.8-15s).
