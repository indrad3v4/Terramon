# Terramon — North Star Gap Report (v2) · 2026-08-13 (iter-23)

Fingerprint: `2a1e478` (прод: `tests:502*`, `data_persisted:false` ⚠️ — регресс vs iter-22 (было true), `data_restored_from_snapshot:false`, живой `seed_count:21`, `share_count:3`, `mint_count:0`, `alby_configured:true`) · Playwright/Chromium headless + TMA-mock · Target: https://terramon-tma-production.up.railway.app · *502 — счётчик в /health синхронизирован этим коммитом (был 496; +6 тестов).

---

## 0. ВЕРДИКТ ДНЯ (TL;DR)

- **North Star Score: 75/100** (плато 11-я итерация; Geo/Lore/Win-path железно; инвойс-нога M7 доказана live 9-й раз; MintLoop=0 — ждёт РЕАЛЬНОГО платежа владельца)
- Топ-3 блокера: **1) M7 settle-нога: нужен РЕАЛЬНЫЙ ПЛАТЁЖ владельца (~3000 sats) — kill-окно пошло: часы kill-condition ПОЧИНЕНЫ и теперь тикают от первого призыва 2) data_persisted:false — durability-регресс на проде (volume снова не подтверждён) 3) нет реальных игроков (player_count:0)** + M1 ждёт device-проверки
- Kill-condition монитор: share 3 · mint 0 · **kill-часы РАНЬШЕ НИКОГДА НЕ ЗАПУСКАЛИСЬ (days_mint_zero:null вечно)** — iter-23 чинит это: якорь = первый призыв
- 🎯 **ГЛАВНОЕ СОБЫТИЕ iter-23 — починен СЛЕПОЙ kill-condition watchdog**: (а) `days_mint_zero` = days_since_last_mint, а когда минта НЕ БЫЛО НИКОГДА — якорь на `days_since_first_seed()` (первый призыв = запуск игры), т.е. «mint=0 за 30 дней» теперь реально сработает (раньше null навсегда → kill-condition НИКОГДА не мог триггернуться); (б) `share_rate` вычисляется честно = share_count/seed_count (было захардкожено None); (в) `triggered` = days_mint_zero >= 30 (форма сохранена). +6 тестов (502 зелёных). Плюс: смержен незакоммиченный sync 466→496 (HEAD был КРАСНЫЙ — тест утверждал 466 при source 496) и обновлён durability-снапшот (21/3/0) — прошлая сессия его скачала, но не закоммитила.

## 1. NORTH STAR SCORE (композит)

| Компонент | Вес | Сегодня | Нормализация |
|---|---|---|---|
| Geo-привязка | 25 | **100%** (map-url 50.0619, 19.9368) | headless-симуляция, ждёт device-проверки |
| Vision-lore («Open your eyes») | 25 | **1** | кнопка в DOM (main_card_oye_after_care: 1) |
| Win-path (достижимость) | 25 | **12/12** | min(архетипов/12, 1) — distinct 12, failed_rounds: [] |
| Mint-loop | 25 | **0** | инвойс создан (invoice_ok:true, 9-й прогон), auto-verify вооружён («⏳ 1/30»), settle не было → mint_count=0 |
| **ИТОГО** | 100 | **75/100** | |

Боевая формула (включается, когда есть реальные игроки): NSS = 40·MintRate + 30·D7 + 15·Geo + 15·Lore.

## 2. ГЭП-ТАБЛИЦА (мост «инженерия → северная звезда»)

| # | Метрика | Что меряет | Сегодня | Цель | Гэп | Блокирует | Измерение |
|---|---|---|---|---|---|---|---|
| M1 | Geo% | доля существ с реальными координатами | 100% (map-url) | 100% | 🟢 код-ок; ждёт device | share-петлю | AUTO + **device** |
| M2 | Vision-lore | «Open your eyes» + рендер лора | 1 | 1 | 🟢 ок | эмоцию/арт | AUTO |
| M3 | Win-path | уникальные архетипы за прогон | 12/12 | 12/12 | 🟢 ок | контентную глубину → D7 | AUTO |
| M4 | Дубликаты | unique/total | 12/19 в прогоне (dedup работает) | 1.0 | 🟢 ок | экономику минта | AUTO |
| M5 | Фрикция | гейт/модалки | 0 блоков (failed_rounds: []) | 0 | 🟢 ок | онбординг → D7 | AUTO |
| M6 | Share-funnel | доля сессий с share-тапом | счётчик жив (2→3 live); deep-link + 📍 в клипборде | ≥2% (kill <2%) | 🔴 нет игроков | охват (kill-condition) | AUTO + **люди** |
| M7 | Mint rate | % саммонеров с mint | 0 (mint_count=0) | ≥2% | 🔴 **инвойс-нога доказана (9-й раз); settle ждёт платёж** | саму северную звезду | AUTO + **платёж владельца** |
| M8 | D7 retention | возврат на 7-й день | замерен кодом (0/0/0.0 — нет игроков) | кохортный бенчмарк | 🔴 нет игроков | 2-ю половину NSS | AUTO + **люди** |

Регрессионные guard (инженерный health, AUTO): **502 теста зелёные** (+6 к iter-22, регрессий 0) · reflex export --frontend-only --no-zip (запущен) · py_compile OK · /health tests count синхронизирован (502).

## 3. ТОП-3 БЛОКЕРА (ранжировано)

1. **M7 settle-нога: нужен РЕАЛЬНЫЙ ПЛАТЁЖ** (~3000 sats, ~$0.30). Инвойс создаётся (invoice_ok:true), auto-verify тикает («⏳ 1/30»), settle→mint-запись→счётчик юнит-доказаны, лейблы честные (Stars vs sats), Copy BOLT11 есть. **Kill-часы iter-23 ПОЧИНЕНЫ**: раньше days_mint_zero был null навсегда (kill-condition слепой) — теперь якорь на первый призыв, окно реально идёт. → **Действие владельца (2 мин)**: бот @terrramonBot → призвать свежее существо → Care → «⚡ Mint via Lightning · 3000 sats» → оплатить (WebLN/QR/BOLT11). mint_count станет 1 → MintLoop=1 → **NSS 100/100**.
2. **data_persisted:false на проде — durability-регресс** (iter-22 было true, volume был примонтирован; сейчас false, restore не сработал, restored 0). Снапшот обновлён и закоммичен (21/3/0) — следующая пересборка забейкает свежий baseline в /app/boot_snapshots. → **Действие владельца**: Railway dashboard → проект Terramon → Volume `terramon-data` @ `/app/data` — проверить, что примонтирован (после редеплоя /health должен показать data_persisted:true).
3. **Нет реальных игроков** (player_count:0, returning_players_7d:0) — M6/M8 и боевая формула мертвы без людей; рост seed 16→19→21 неразличим между KPI-пробами и анонимными пользователями (бота-токена нет). → **Действие владельца**: TERRAMON_BOT_TOKEN в Railway env (initData-верификация → player_count оживёт) + публикация бота (BotFather → /setmenubutton → WebApp URL).

## 4. EVIDENCE

- KPI-прогон iter-23: distinct 12/12 (failed_rounds: []), geo map-url 50.0619/19.9368, OYE 1, `invoice_ok:true` («⚡ Invoice ready») + `auto_verify_seen:true` («⏳ Auto-checking payment… 1/30») + `lightning_price_sats:3000` (честная цена Lightning-кнопки) + `mint_price_sats:15` (единица — STARS, не sats), share_count 2→3 live (deep link + «📍 Краков» в клипборде), mint_count 0, data_persisted:false (⚠️), alby_configured:true.
- Новый код (grep-верифицирован): `def days_since_first_seed` (json_memory.py:393, мин. timestamp первого сида, defensive как days_since_last_mint), `days_mint_zero = days_since_last_mint if ... else days_since_first_seed` + `share_rate = (share_count / seed_count) if seed_count > 0 else None` (terramon_tma.py:4419-4424), `_dsfs = getattr(_MEMORY, "days_since_first_seed", None)` (getattr-фолбэк, деградация честная), tests: `test_days_since_first_seed_*` ×4, `test_health_kill_clock_anchors_to_first_seed_when_no_mint` + `test_health_share_rate_computed` (test_d7_retention.py, test_health_persistence.py).
- OSS-референсы iter-23: **dead-man-switch паттерн** — spinov001-art/data-pipeline-monitoring (health checks + dead man switch: «нет heartbeat N дней → алерт»; РЕПЛИЦИРОВАНО: якорь kill-часов на первый activity), Drew-Opexcell/hushbeat (silent-until-broken, stdlib-only; AVOID: зависимости не нужны — у нас getattr-фолбэк); cohort/retention: maladeep/cohort-retention-rate-analysis-in-python (форма eligible/retained/rate — РЕПЛИЦИРОВАНА в iter-22); TMA+LN: getalby/lightning-browser-extension (585★, BOLT11-ясность), mozharov/zapgram (Telegram-нативный LN, copy-paste BOLT11 — РЕПЛИЦИРОВАНО в iter-22).
- Ограничение честно: headless-геолокация = Playwright-симуляция, НЕ устройство; place_name в headless = гейт-баннер; mint-проба никогда не платит (присутствие-only); kill_condition.days_mint_zero при отсутствии и минта и сидов = null (нет данных — не поломка); data_persisted:false — это «volume не подтверждён на текущем деплое», а не «код сломан».
