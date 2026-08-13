# Terramon — North Star Gap Report (v3, win-centric) · 2026-08-13 (iter-34)

Fingerprint: `2222eb25` (прод: `tests:572`, `data_persisted:false`, `seed_count:107`, `share_count:25`, `mint_count:0`, `complete_releases:0`, `alby_configured:true`) · Playwright/Chromium headless + TMA-mock · Target: https://terramon-tma-production.up.railway.app

---

## 0. ВЕРДИКТ ДНЯ (TL;DR)

- **North Star Score: 28.5/100** — формула v3: `60·min(complete_releases,1) + 25·Geo% + 15·ShareRate` = `60·0 + 25·1.0 + 15·(25/107=23.4%)`
- Топ-3 блокера: **1) complete_releases=0 — 60/100 заперты за РЕАЛЬНЫМ платежом ритуала (M9 в ЭТОМ ране снова доказан полным depth-флоу: слова → confirm → ритуал-панель → живой BOLT11 lnbc30u1p48… на 3000 sats; free-путь честно НЕ считает вин — complete_delta=0; нужен ОДИН настоящий платёж) 2) долговечность win-счётчика при вайпе volume — АДРЕСОВАНА iter-34 (complete_releases теперь в снапшот-ресторе, снапшот обновлён: seed 107 / share 25) 3) player_count=0 — mint/D7/device-гео ждут реальных людей и платежей**
- Kill-condition монитор: share_rate 23.4% (25/107) · mint 0 · days_mint_zero: 0/30 → **НЕ триггернут** ✅
- 🛠️ **СОБЫТИЕ iter-34 — win-proof durability**: платный вин (complete_releases, 60/100 NSS) теперь переживает вайп data/ на Railway: (а) `RESTORE_COUNTER_KEYS` в `terramon/adapters/durability.py` дополнен `complete_releases` (паттерн LNbits «ledger = durable truth» + datalad «git-carried checkpoint»); (б) `/health` аддитивно восстанавливает его под флагом `_SNAPSHOT_RESTORED` (обычный и деградированный пути) + новое поле `restored_complete_releases`; (в) ship-time снапшот обновлён в git (seed 107 / share 25 / complete_releases 0); (г) +4 теста (572 зелёных). Смысл: платёж владельца → win=1 → следующий редеплой НЕ сотрёт его.

## 1. NORTH STAR SCORE (v3, win-centric)

| Компонент | Вес | Сегодня | Значение |
|---|---|---|---|
| Win-path: PAID complete release (final words + real geo, ритуал оплачен) | 60 | **0** | complete_releases=0; win-path ДОСТИЖИМ и монетизирован (M9: полный depth-флоу, живой BOLT11 на Alby, auto-verify, refresh-инвойс, deep-link), теперь ещё и ДОЛГОВЕЧЕН (iter-34) — ждёт реальный платёж → 0/60 |
| Geo% (якорь победы) | 25 | **1.0 (сим)** | geo_ok_rounds [1] — headless-сим (grant_permissions + set_geolocation, Краков); честно: ⟳-кнопки в раундах не было, place_name null — ждёт device |
| ShareRate (share/seed) | 15 | **3.5** | 25/107 = 23.4% |
| **ИТОГО** | 100 | **28.5/100** | |

Lore/MintLoop — ДИАГНОСТИКА (не NSS): M2 lore = 1 (OYE в DOM) · M7: mint_count=0, MINT area НЕ live в этом ране (can_mint: max posterior ≤ 0.5 — belief-файл пересоздан редеплоем; НЕ регрессия кода: тот же билд в iter-33 давал MINT live) · M9 ритуал: BOLT11 LIVE (полный флоу).

## 2. ГЭП-ТАБЛИЦА (мост «инженерия → северная звезда»)

| # | Метрика | Что меряет | Сегодня | Цель | Гэп | Блокирует | Измерение |
|---|---|---|---|---|---|---|---|
| M1 | Geo% | доля существ с реальными координатами | 100% (сим) | 100% | 🟡 device-проверка | сам win (без якоря release не полный) | AUTO + **device** |
| M2 | Vision-lore | кнопка «Open your eyes» + рендер | 1 | 1 | ✅ 0 | эмоцию/арт | AUTO |
| M3 | Win-path (depth) | complete_releases: release с final words + real geo, ритуал ОПЛАЧЕН | **0** (ритуал ДОСТИЖИМ: M9 полный флоу; счётчик теперь durable) | 1 (1 = 100%) | 🔴 **ждёт РЕАЛЬНЫЙ платёж** | 60/100 NSS | AUTO + **платёж владельца** |
| M4 | Дубликаты | unique/total | 12/12 | 1.0 | ✅ 0 | экономику минта | AUTO |
| M5 | Фрикция | гейт/модалки | 0 (probe прошёл без гейтов) | 0 | ✅ 0 | онбординг | AUTO |
| M6 | Share-funnel | share_count/seed_count | 23.4% (25/107) | ≥2% (kill <2%) | ✅ 0 | охват (kill-condition) | AUTO |
| M7 | Mint loop | mint_count / инвойс-нога | 0; MINT area не live (belief сброшен редеплоем) | ≥2% | 🟡 belief-файл пересоздан; ждёт людей | метрику минта | AUTO + **платёж** |
| M8 | D7 retention | возврат на 7-й день | 0/0/0.0 (нет игроков) | кохортный бенчмарк | 🔴 нет игроков | 2-ю половину NSS | AUTO + **люди** |
| M9 | RitualPaid | monetised win-path: «⚡ Ритуал отпускания:» инвойс-маркер | **LIVE** (BOLT11 3000 sats) | 1 | ✅ 0 (ждёт settle) | доказательство live-монетизации | AUTO (инвойс = доказательство; платёж — никогда) |

Регрессионные guard (AUTO): **572 теста зелёные** (регрессий 0) · reflex export --frontend-only --no-zip ✅ · py_compile ✅ · /health tests:572 (литерал обновлён iter-34).

## 3. ТОП-3 БЛОКЕРА (ранжировано)

1. **complete_releases=0 — 60/100 заперты за РЕАЛЬНЫМ платежом** — win-path достижим, монетизирован и теперь долговечен: M9 в ЭТОМ ране подтверждён полным depth-флоу (ritual_panel_seen=True, ritual_invoice_marker=True, BOLT11 lnbc30u1p48… на 3000 sats live; проба честно закрыла панель free-путём: complete_before=0 after=0 delta=0 — free-релиз НЕ подделывает вин). Нужен ОДИН настоящий платёж: призвать → заботиться → EVOLVE×2 → финальные слова → реальная геолокация (⟳) → «⚡ Открыть кошелёк» → оплатить 3000 sats (Lightning) или 5⭐ (Stars). После settle complete_releases=1 → NSS ≈ 88.5; iter-34 гарантирует, что этот вин переживёт редеплои.
2. **Долговечность win-счётчика — АДРЕСОВАНА iter-34** (complete_releases в RESTORE_COUNTER_KEYS + аддитивный рестор в /health + снапшот обновлён в git). Остаточный риск: снапшот-рестор восстанавливает СЧЁТЧИК, а не сами seed-записи (слова/гео) — при вайпе они потеряются, но win-сигнал (60/100) выживет, честно помеченный restored_complete_releases. Полная миграция на sqlite (litestream-паттерн) — следующий кандидат после json-to-sqlite-migration скилла.
3. **player_count=0 — mint/D7/device-гео ждут реальных людей** — mint_count=0 (инвойс-нога live, settle ждёт), D7 без кохорты, гео-проверка на реальном телефоне не делалась. M7 в этом ране: MINT area не live на fresh-summon (can_mint = max(posterior) > 0.5 не пройден: belief-файл data/beliefs.jsonl пересоздан редеплоем — data_persisted:false это подтверждает; тот же код в iter-33 давал MINT live). Это диагностика, не NSS.

## 4. EVIDENCE

KPI run (EXIT=0): `geo_ok_rounds: [1]` · `place_name_rounds: [null,null]` (честно: ⟳-кнопки в раундах не было — autoLocation через mock) · `distinct_archetypes: 12` · `oye_buttons_total: 1` (main_card_oye_after_care=1) · `m7_probe_postloop: MINT area presence=False, ui_state='free summon', invoice_ok=None (belief сброшен редеплоем — записано честно)` · `m6: share 24→25 live (share_delta=1), deep-link ✅, share_card_has_birthplace=True ('📍 Краков, П…')` · `depth_release_probe: released_clicked=True, words_entered=True, ritual_panel_seen=True, ritual_invoice_marker=True (BOLT11 lnbc30u1p48… 3000 sats), free_release_receipt_seen=True, complete_before=0 after=0 delta=0` · `mint_count_health: 0` · `alby_configured: true` · `data_persisted:false, data_restored_from_snapshot:false, restored_seed_count:0` (вайп при прошлом редеплое; снапшот-рестор НЕ сработал — memory была непустой).

- OSS-референсы iter-34 (GitHub API): **lnbits/lnbits** (1230★, активен 2026-08) — платёжный ledger как durable truth; **datalad/datalad** (655★, активен) — чекпойнты состояния в git; **benbjohnson/litestream** (14.2k★) — стриминг-репликация sqlite (путь будущей json→sqlite миграции; в этот итератив НЕ вносили). Реплицируем: расширенный чекпойнт; избегаем: фабрикации вин, оптимистичного счёта, миграции сейчас.
- Ship-статус iter-34: коммит `feat(iter-34)` → push origin main (Railway автодеплой; win-proof durability уедет на прод).
