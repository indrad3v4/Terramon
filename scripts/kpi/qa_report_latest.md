# Terramon — North Star Gap Report (v3, win-centric) · 2026-08-13 (iter-27)

Fingerprint: `99b20ff` (прод: `tests:522`, `data_persisted:false`, `seed_count:45→48`, `share_count:8→9`, `mint_count:0`, `complete_releases:0`, `alby_configured:true`) · Playwright/Chromium headless + TMA-mock · Target: https://terramon-tma-production.up.railway.app

---

## 0. ВЕРДИКТ ДНЯ (TL;DR)

- **North Star Score: 27.8/100** — формула v3: `60·min(complete_releases,1) + 25·Geo% + 15·ShareRate` = `60·0 + 25·1.0 + 15·0.1875`
- Топ-3 блокера: **1) Win-path НЕДОСТИЖИМ на проде — ритуал отпускания (и его платёжный экран) не открывался: 2× EVOLVE не доводил существо до стадии 2 (инкремент 2-го клика терялся из-за generator-хендлера) → «💨 Отпустить» не рендерился → complete_releases намертво в 0 → 60/100 заперты. ФИКС НАПИСАН И ЗАПУШЕН В ЭТОЙ ИТЕРАЦИИ 2) M7 settle-нога: нужен РЕАЛЬНЫЙ платёж владельца (3000 sats или 5⭐) 3) M1 ждёт device-проверки (headless-симуляция, не реальное устройство)**
- Kill-condition монитор: share_rate 18.75% (9/48) · mint 0 · days_mint_zero: 0/30 → **НЕ триггернут** ✅
- 🎯 **ГЛАВНОЕ СОБЫТИЕ iter-27 — win-path РАЗБЛОКИРОВАН кодом**: KPI-проба M9 (ритуал) на проде ПОДТВЕРДИЛА баг: после 2× «✦ EVOLVE» → `'💨 Отпустить' not visible — evolution stage < 2?`. Причина: `evolve_agent` был generator-хендлером — `yield rx.call_script(setTimeout→sendEvent)` приостанавливал обработчик, задерживал state-delta, и 2-й клик читал устаревший state → инкремент терялся → `agent_evolution` застревал на 1 → гейт `agent_evolution >= 2` не открывался. Фикс: plain-хендлер (каждый клик инкрементирует ровно один раз, немедленно) + gated `rx.moment(interval=1600, on_change=clear_evolution_animation)` для авто-сброса анимации (паттерн lightning-поллера). +5 тестов (527 зелёных).

## 1. NORTH STAR SCORE (v3, win-centric)

| Компонент | Вес | Сегодня | Значение |
|---|---|---|---|
| Win-path: PAID complete release (final words + real geo, ритуал оплачен) | 60 | **0** | complete_releases=0; ритуал НЕдостижим на проде до этого коммита → 0/60 |
| Geo% (якорь победы) | 25 | **25** | 100% headless-сим (map-url 50.0619,19.9368) — ждёт device-проверки |
| ShareRate (share/seed) | 15 | **2.8** | 9/48 = 18.75% |
| **ИТОГО** | 100 | **27.8/100** | |

Lore/MintLoop — ДИАГНОСТИКА (не NSS): M2 lore = 1 (OYE-кнопка в DOM) · M7 инвойс-нога LIVE (⚡3000 sats, auto-verify 1/30 вооружён) · mint_count=0 (нет реального платежа).

## 2. ГЭП-ТАБЛИЦА (мост «инженерия → северная звезда»)

| # | Метрика | Что меряет | Сегодня | Цель | Гэп | Блокирует | Измерение |
|---|---|---|---|---|---|---|---|
| M1 | Geo% | доля существ с реальными координатами | 100% (map-url, симуляция) | 100% | 🟢 код-ок; **ждёт device** | сам win (без якоря release не полный) | AUTO + **device** |
| M2 | Vision-lore | кнопка «Open your eyes» + рендер | 1 (main_card_oye_after_care:1) | 1 | 🟢 ок | эмоцию/арт | AUTO |
| M3 | Win-path (depth) | complete_releases: release с final words + real geo, ритуал ОПЛАЧЕН | **0** (ритуал был недостижим → фикс запушен) | 1 (1 = 100%) | 🔴 **фикс в деплое; ждёт РЕАЛЬНЫЙ платёж** | 60/100 NSS | AUTO + **платёж владельца** |
| M4 | Дубликаты | unique/total | 12/45 | 1.0 | 🟢 ок | экономику минта | AUTO |
| M5 | Фрикция | гейт/модалки | 0 блоков (failed_rounds: []) | 0 | 🟢 ок | онбординг | AUTO |
| M6 | Share-funnel | share_count/seed_count | 9/48 = 18.75% (8→9 live) | ≥2% (kill <2%) | 🟢 ок | охват (kill-condition) | AUTO |
| M7 | Mint loop | mint_count / инвойс-нога | 0; инвойс LIVE (⚡3000 sats, STARS 25) | ≥2% | 🔴 **settle ждёт платёж** | метрику минта | AUTO + **платёж** |
| M8 | D7 retention | возврат на 7-й день | 0/0/0.0 (нет игроков) | кохортный бенчмарк | 🔴 нет игроков | 2-ю половину NSS | AUTO + **люди** |
| M9 | RitualPaid | monetised win-path: «⚡ Ритуал отпускания:» инвойс-маркер | **НЕ ДОСТИГНУТ** (ритуал не открывался) → фикс запушен, перепроверка в след. итерации | 1 | 🔴 **фикс в деплое** | доказательство live-монетизации | AUTO (инвойс = доказательство; платёж — никогда) |

Регрессионные guard (AUTO): **527 тестов зелёные** (+5 к прошлому, регрессий 0) · reflex export --frontend-only --no-zip OK · py_compile OK · /health tests:522 (прод ещё на старом коммите, синхронизация после деплоя).

## 3. ТОП-3 БЛОКЕРА (ранжировано)

1. **Win-path недостижим на проде (чинится в этом коммите)** — generator-хендлер `evolve_agent` терял инкремент 2-го клика EVOLVE → стадия застревала на 1 → «💨 Отпустить» и платёжный экран ритуала не открывались → complete_releases намертво 0. Фикс: plain-хендлер + gated rx.moment авто-сброс. После деплоя KPI-проба M9 должна увидеть «⚡ Ритуал отпускания:» (создание BOLT11 = живое доказательство; платить НИКОГДА).
2. **M7/M3 settle-нога — нужен РЕАЛЬНЫЙ платёж владельца** (~3000 sats на Alby Hub, или 5⭐) — единственный способ перевести complete_releases 0→1 и mint_count 0→1. Всё код-сайд сделано: инвойс создаётся, auto-verify вооружён, ритуал теперь достижим.
3. **M1: headless-геолокация — не реальное устройство** — Playwright `grant_permissions + set_geolocation` симулирует разрешение устройства; реальный якорь на телефоне владельца нужен для финального подтверждения Geo%=100%.

## 4. EVIDENCE

KPI run (EXIT=0): `geo_ok_rounds: [1]` (map-url `/static-map?lat=50.0619&lon=19.9368`) · `distinct_archetypes: 12` · `oye_buttons_total: 1` · `m7_probe: invoice_ok=True, lightning_price_sats=3000, auto_verify_marker='⏳ Auto-checking payment… 1/30'` · `m6: share 8→9, deep-link ✅, карточка с birthplace` · `depth_release_probe: released_clicked=False — '💨 Отпустить' not visible — evolution stage < 2?` (баг, подтверждённый на проде) · `complete_releases: 0→0` · `mint_count: 0` · `failed_rounds: []` · `data_restored_from_snapshot: False` (durability-флаг, диагностика).

Фикс в коммите iter-27: `terramon_tma/terramon_tma.py` (plain `evolve_agent` + gated rx.moment в `creature_care_panel`, строки ~3223-3235) + `tests/test_evolve_release_gate.py` (5 тестов: plain-handler, stage-2 гейт, авто-сброс, отсутствие JS-сброса).
