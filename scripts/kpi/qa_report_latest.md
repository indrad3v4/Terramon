# Terramon — North Star Gap Report (v3, win-centric) · 2026-08-13 (iter-31)

Fingerprint: `c1fbef8e` (прод: `tests:527`, `data_persisted:false`, `seed_count:91`, `share_count:21`, `mint_count:0`, `complete_releases:0`, `alby_configured:true`) · Playwright/Chromium headless + TMA-mock · Target: https://terramon-tma-production.up.railway.app

---

## 0. ВЕРДИКТ ДНЯ (TL;DR)

- **North Star Score: 28.5/100** — формула v3: `60·min(complete_releases,1) + 25·Geo% + 15·ShareRate` = `60·0 + 25·1.0 + 15·(22/95≈23.2%)` (share 21→22 live, seed 91 + 4 probe-сида этого рана)
- Топ-3 блокера: **1) complete_releases=0 — 60/100 заперты за РЕАЛЬНЫМ платежом ритуала (M9 снова доказан live: живой BOLT11 на Alby-ноде; win-path достижим — нужен один настоящий платёж) 2) НОВОЕ (фикс в этом коммите): тупик жизненного цикла инвойса ритуала — истёкший BOLT11 (Alby default ~1ч) невозможно пересоздать, авто-проверка не ограничена по попыткам → кнопка «✅ I've paid — verify» НИКОГДА не появляется; игрок, вернувшийся позже часа, намертво застревал на единственном пути к +60 3) Stars-рельса ритуала не оплачиваема: TERRAMON_STARS_INVOICE_URL не задан (действие владельца: BotFather invoice link)**
- Kill-condition монитор: share_rate 23.2% (22/95) · mint 0 · days_mint_zero: 0/30 → **НЕ триггернут** ✅
- 🚀 **СОБЫТИЕ iter-31 — escape hatch для ритуала**: авто-проверка платежа ритуала теперь ограничена 30 попытками (~3 мин, зеркало mint-пути LIGHTNING_VERIFY_MAX_ATTEMPTS); после лимита панель показывает «✅ I've paid — verify» (ручная проверка) + НОВУЮ кнопку **«🔄 Новый инвойс»** — пересоздаёт BOLT11/QR, пере-взводит авто-проверку, сбрасывает счётчик. Защита от потери денег: перед пересозданием refresh делает финальный verify старого ref — если платёж ВСЁ-ТАКИ прошёл, ритуал завершается (complete release), а не пересоздаётся. Паттерн — из OSS: lnbits (★1230, статус инвойса pending/paid/expired + пересоздание) и BTCPay (★6.5k, pending→expired + re-issue). Это де-фрикция ЕДИНСТВЕННОГО пути к +60 NSS: игрок больше не может «потерять» оплачиваемый момент из-за истёкшего инвойса.

## 1. NORTH STAR SCORE (v3, win-centric)

| Компонент | Вес | Сегодня | Значение |
|---|---|---|---|
| Win-path: PAID complete release (final words + real geo, ритуал оплачен) | 60 | **0** | complete_releases=0; win-path достижим + монетизирован (M9: живой BOLT11 на Alby), ждёт реальный платёж → 0/60 |
| Geo% (якорь победы) | 25 | **25** | 100% headless-сим (geo_ok_rounds:[1], map-url 50.0619,19.9368) — ждёт device-проверки |
| ShareRate (share/seed) | 15 | **3.5** | 22/95 = 23.2% (share 21→22 live, deep-link ✅) |
| **ИТОГО** | 100 | **28.5/100** | |

Lore/MintLoop — ДИАГНОСТИКА (не NSS): M2 lore = 1 (OYE-кнопка в DOM) · M7: mint_count=0, инвойс-нога LIVE (⚡3000 sats, mint-площадь в этом ране не была live — свежий belief-файл после редеплоя, записано честно) · M9 ритуал: BOLT11 LIVE.

## 2. ГЭП-ТАБЛИЦА (мост «инженерия → северная звезда»)

| # | Метрика | Что меряет | Сегодня | Цель | Гэп | Блокирует | Измерение |
|---|---|---|---|---|---|---|---|
| M1 | Geo% | доля существ с реальными координатами | 100% (map-url, симуляция) | 100% | 🟢 код-ок; **ждёт device** | сам win (без якоря release не полный) | AUTO + **device** |
| M2 | Vision-lore | кнопка «Open your eyes» + рендер | 1 (main_card_oye_after_care:1) | 1 | 🟢 ок | эмоцию/арт | AUTO |
| M3 | Win-path (depth) | complete_releases: release с final words + real geo, ритуал ОПЛАЧЕН | **0** (ритуал ДОСТИЖИМ: M9 доказан) | 1 (1 = 100%) | 🔴 **ждёт РЕАЛЬНЫЙ платёж** | 60/100 NSS | AUTO + **платёж владельца** |
| M4 | Дубликаты | unique/total | 12/91 | 1.0 | 🟢 ок | экономику минта | AUTO |
| M5 | Фрикция | гейт/модалки | 0 блоков (failed_rounds: []) | 0 | 🟢 ок | онбординг | AUTO |
| M6 | Share-funnel | share_count/seed_count | 22/95 = 23.2% (21→22 live) | ≥2% (kill <2%) | 🟢 ок | охват (kill-condition) | AUTO |
| M7 | Mint loop | mint_count / инвойс-нога | 0; инвойс-нога LIVE (⚡3000 sats, STARS 25) | ≥2% | 🔴 **settle ждёт платёж** | метрику минта | AUTO + **платёж** |
| M8 | D7 retention | возврат на 7-й день | 0/0/0.0 (нет игроков) | кохортный бенчмарк | 🔴 нет игроков | 2-ю половину NSS | AUTO + **люди** |
| M9 | RitualPaid | monetised win-path: «⚡ Ритуал отпускания:» инвойс-маркер | **1 — ПОДТВЕРЖДЁН** (ritual_panel_seen=True, ritual_invoice_marker=True, BOLT11 на Alby) | 1 | 🟢 **доказано live** | доказательство live-монетизации | AUTO (инвойс = доказательство; платёж — никогда) |

Регрессионные guard (AUTO): **554+ тестов зелёные** (iter-31 добавит ~6) · reflex export --frontend-only --no-zip OK · py_compile OK · /health tests:527 (константа, синхронизирована на iter-27).

## 3. ТОП-3 БЛОКЕРА (ранжировано)

1. **complete_releases=0 — 60/100 заперты за РЕАЛЬНЫМ платежом** — win-path достижим и монетизирован (M9: живой BOLT11 на Alby-ноде, auto-verify вооружён, обе рельсы — Lightning 3000 sats и Stars 5⭐, оплата в 1 тап «⚡ Открыть кошелёк»). Нужен ОДИН настоящий платёж ритуала: призвать → заботиться → EVOLVE×2 → финальные слова → реальная геолокация (⟳) → «⚡ Открыть кошелёк» → оплатить 3000 sats (Lightning) или 5⭐ (Stars). После settle complete_releases 0→1 → +60 NSS (28.5 → 88.5).
2. **Тупик жизненного цикла инвойса ритуала (ФИКС В ЭТОМ КОММИТЕ)** — BOLT11 живёт ~1ч (Alby default), панель не умела пересоздавать инвойс, а авто-проверка крутилась бесконечно (30/30 — косметика), поэтому «✅ I've paid — verify» никогда не рендерилась: игрок, оплативший позже окна или вернувшийся после истечения, застревал навсегда. Теперь: лимит попыток → ручная кнопка + «🔄 Новый инвойс» (с финальной проверкой старого ref — деньги не теряются, оплаченный ритуал завершается).
3. **Stars-рельса ритуала не оплачиваема: нет реального инвойс-линка** — `_STARS_INVOICE_URL` читается из env `TERRAMON_STARS_INVOICE_URL` (плейсхолдер по умолчанию). Владельцу: BotFather → Settings → Payments → Stars → создать invoice link («Ритуал Отпускания», 5⭐) → задать env на Railway. Код готов и ЧЕСТЕН (релиз только по колбэку 'paid').

## 4. EVIDENCE

KPI run (EXIT=0): `geo_ok_rounds: [1]` (map-url 50.0619,19.9368) · `distinct_archetypes: 12` · `oye_buttons_total: 1` · `m7_probe_postloop: mint-площадь не live (свежий belief-файл после редеплоя; mint_ui_state='free summon', invoice_ok=None — записано честно, НЕ код-баг)` · `m6: share 21→22, deep-link ✅, карточка с birthplace '📍 Краков'` · `depth_release_probe: released_clicked=True, words_entered=True, ritual_panel_seen=True, ritual_invoice_marker=True, ritual_free_release_clicked=True, receipt_seen=False, complete_delta=0` (free-path не считает — by construction; проба НИКОГДА не платит) · `complete_releases: 0→0` · `mint_count: 0` · `failed_rounds: []` · kill-condition share_rate 23.2% НЕ триггернут.

Фикс iter-31 (в этом коммите): `terramon_tma/terramon_tma.py` — константа `RITUAL_RELEASE_VERIFY_MAX_ATTEMPTS = 30` (рядом с LIGHTNING_VERIFY_MAX_ATTEMPTS); `verify_release_ritual` (L1694): счётчик попыток, по достижению лимита → `release_ritual_auto_verify=False` + hint (agent_message трогается ТОЛЬКО на лимите, маркер «⚡ Ритуал отпускания:» в первые секунды не затирается); новый обработчик `refresh_ritual_invoice` — финальный verify старого ref (settled → complete release, без пересоздания) иначе `create_ritual_invoice()` (новый BOLT11/QR, сброс попыток, ре-арм авто-проверки); `ritual_payment_panel` (L4089): при выключенной авто-проверке — vstack «✅ I've paid — verify» (как в mint-панели) + **«🔄 Новый инвойс»** + hint «Инвойс жив ~1 час — если оплата не прошла, создай новый»; счётчик в строке авто-проверки теперь от константы. + `tests/test_ritual_invoice_refresh.py` (source-guards + функциональные с fake-портами: лимит → ручная кнопка; refresh пересоздаёт; refresh НЕ пересоздаёт поверх оплаченного). OSS-референсы: lnbits/lnbits (★1230 — жизненный цикл инвойса: pending/paid/expired + пересоздание; РЕПЛИЦИРУЕМ escape-hatch, НЕ реплицируем бэкенд-машину состояний), btcpayserver/btcpayserver (★6.5k — pending→expired + re-issue; РЕПЛИЦИРУЕМ явный «истёк → пересоздай», НЕ реплицируем тяжёлый state-machine), alby/hub — API не отдаёт статус 'expired', только pending/settled → escape-hatch обязан жить на клиенте (наш кэп + refresh). Пуш: `0d2fdff..<iter-31>` — Railway авто-деплой.
