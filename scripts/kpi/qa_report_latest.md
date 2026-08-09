# Terramon — North Star Gap Report (v2) · 2026-08-09 (Iter-8)

Fingerprint деплоя: 8efa65ac53336e0a (live) · Бандлы: _index-BDHI-iE_.js, root-DBvl26DB.js (+8) · Playwright/Chromium · Target: https://terramon-tma-production.up.railway.app/

---

## 0. ВЕРДИКТ ДНЯ (TL;DR)

- **North Star Score: 75/100** (▲▲ с 58/100: win-path 12/12 подтверждён в live, M1-измерение починено — гео-цепочка доказана)
- Топ-3 блокера: **1) M7 MintLoop=0 — нет ни одного реального settle (нужен Alby LSP-фонд + платёж владельца) 2) M6 share — нет счётчика тапов в коде 3) M8 D7 — player_count=0 (нужны реальные игроки)**
- Kill-condition монитор: share нет данных · mint **0** · дней с mint=0: 9+/30 → **KILL-RISK (сохраняется)**
- ✅ 377/377 тестов (372 → +5) · reflex export — OK · KPI-прогон: 0 failed rounds

## 1. NORTH STAR SCORE (композит)

| Компонент | Вес | Сегодня | Нормализация |
|---|---|---|---|
| Geo-привязка | 25 | **100%** (map-URL coords, 12/12 раундов static-map с реальными 50.0619,19.9368) | доля существ с lat≠0 && lon≠0 |
| Vision-lore («Open your eyes») | 25 | 1 (кнопка 12/12 раундов, лор рендерится) | 1 = кнопка в DOM + лор рендерится |
| Win-path (достижимость) | 25 | **12/12** (live-коллекция: все 12 архетипов существуют на проде) | min(архетипов/12, 1) |
| Mint-loop | 25 | 0 (mint_count=0, settle не случался; гейт-проба: gate_seen=false — см. §3) | 1 = LN-инвойс → mint-событие → счётчик |
| **ИТОГО** | 100 | **75/100** | |

Боевая формула (когда появятся реальные игроки): NSS = 40·MintRate + 30·D7 + 15·Geo + 15·Lore.

## 2. ГЭП-ТАБЛИЦА (мост «инженерия → северная звезда»)

| # | Метрика | Что меряет | Сегодня | Цель | Гэп | Блокирует | Измерение |
|---|---|---|---|---|---|---|---|
| M1 | Geo% | доля существ с реальными координатами | 100% (map-URL; headless-симуляция, ждёт device-проверки) | 100% | 🟢 ок (измерение починено) | share-петлю | AUTO |
| M2 | Vision-lore | кнопка «Open your eyes» + рендер лора | 1 (12/12) | 1 | 🟢 ок | эмоцию/арт | AUTO |
| M3 | Win-path | уникальные архетипы на проде | 12/12 | 12/12 | 🟢 ок | контентную глубину → D7 | AUTO |
| M4 | Дубликаты | unique/total | 12/12 = 1.0 (dedup-guard работает: повторная мысль НЕ создаёт дубль) | 1.0 | 🟢 ок | экономику минта | AUTO |
| M5 | Фрикция гейта | перехват pointer-events, гейт «Summon (1 Star)» | 0 блоков (0 failed rounds) | 0 блоков | 🟢 ок | плавность онбординга | AUTO |
| M6 | Share-funnel | доля сессий с share-тапом | нет данных (кнопка «📤 Share» в UI есть, счётчика нет) | ≥2% share (kill <2%) | 🔴 NEEDS-CODE | рост охвата (kill-condition) | **NEEDS-CODE** |
| M7 | Mint rate | % саммонеров, сделавших mint | mint_count=0; loop в коде есть (инвойс→settle→mint), settle не случался | ≥2% (kill: <2% & mint=0 за 30 дн) | 🔴 структурный | саму северную звезду | **NEEDS-DEVICE** |
| M8 | D7 retention | возврат на 7-й день | player_count=0 (KPI-initData FAKE hash отклоняется verify — честно) | кохортный бенчмарк | 🔴 нет данных | северную звезду (2-я половина) | **NEEDS-PLAYERS** |

Регрессионные guard (AUTO): 377/377 ✅ · KPI не кликает mint-кнопки (presence-only) ✅ · geo-координаты читаются из map-URL ✅ · гейт-проба честно логирует gate_seen ✅.

## 3. ТОП-3 БЛОКЕРА (ранжировано)

1. **M7 MintLoop=0 — структурный.** Цикл в коде замкнут (pay_lightning → BOLT11-инвойс на Alby Hub → verify_lightning → _record_mint → /health mint_count), НО ни один инвойс не был оплачен: mint_count=0, player_count=0. Гейт-проба KPI в этом прогоне честно вернула `gate_seen: false` — ВАЖНОЕ ОТКРЫТИЕ: все 12 мыслей KPI уже засеяны на проде → срабатывает dedup-guard → summon_count не растёт → гейт (условие `summon_count>0 & ~unlocked`) не рендерится. → Фикс (код, след. итерация): гейт-проба с run-unique мыслью, чтобы гейт реально открылся и мы увидели статус инвойса (Alby настроен или нет). → Фикс (владелец, manual): залить sats в Alby Hub (incoming liquidity ≥3000), прописать ALBY_HUB_URL/ALBY_HUB_API_KEY на Railway, оплатить инвойс с реального кошелька → mint_count=1 → MintLoop=1 → NSS 100.
2. **M6 Share-funnel — NEEDS-CODE.** Кнопка «📤 Share» есть, но тап нигде не считается → метрика «нет данных» навсегда. → Фикс: счётчик share-тапов (персист), /health share_count, KPI-проба клика по Share (клик по share безопасен — не создаёт mint).
3. **M8 D7 — NEEDS-PLAYERS.** player_count=0 — KPI-initData с FAKE hash корректно отклоняется verify_init_data (не загрязняем D7-кохорты — правильно). Нужны реальные игроки (owner: пригласить тестеров через бота @terramon_bot) → тогда /health player_count/returning_players_7d начнут расти.

## 4. EVIDENCE

Прогон KPI (после фикса измерения): `geo_ok: True (body: False, map-url: True)` — карта static-map?lat=50.0619&lon=19.9368 рендерится, KPI теперь читает координаты из URL, а не только из текста (place_name человекочитаемый — «Kraków, Poland», regex по телу не срабатывал — это был баг замера, не кода). 0 failed rounds. OYE 1. Win-path 12/12 из live-коллекции. mint_count_health: 0. Гейт-проба: gate_seen=false (dedup, см. §3).

Screenshots: /tmp/terramon_new_win_1.png, /tmp/terramon_new_win_1_terra.png (live-коллекция 12 архетипов).

NOTES:
- **M1 честно**: гео симулируется (Playwright grant_permissions + set_geolocation + TMA LocationButton auto-emit 50.0619,19.9368). Цепочка доказана end-to-end: TMA mock → on_coords → GeoContext → seed с lat/lon → static_map_url с реальными координатами. Headless ≠ устройство: финальная device-проверка за владельцем (открыть в Telegram на телефоне, разрешить геолокацию).
- **M7 честно**: клик по «Pay with Lightning» в гейт-пробе БЕЗОПАСЕН (создаёт инвойс, не платит, mint не записывает). В этом прогоне гейт не открылся из-за dedup — записано честно, не подделано. Mint-кнопки («⚡ MINT»/«Mint (1 Star)») KPI НЕ кликает (presence-only) — mint_count не фабрикуется.
- **M8 честно**: player_count=0 — KPI-initData hash FAKE → verify_init_data отклоняет → игроки не пишутся. Правильно.
- **Iter-8 правки**: play_to_win.py (+62/−4): helper `geo_ok_from_map_url` (координаты из static-map URL) + гейт-проба `m7_gate_probe` (round 1, клик Pay-with-Lightning один раз, чтение invoice-статуса). tests/test_kpi_geo_gate.py (+5 тестов): контракты geo-хелпера, гейт-пробы, presence-only mint-политики, 12 архетипов.

## 5. ЧТО ДЕЛАЕТСЯ В ЭТОЙ ИТЕРАЦИИ / ЧТО ДАЛЬШЕ

**Сделано:**
1. SA1 — scripts/kpi/play_to_win.py: M1-измерение починено (map-URL coords = реальное гео-доказательство), добавлена M7 гейт-проба (честный статус инвойса), presence-only mint-политика сохранена.
2. SA2 — tests/test_kpi_geo_gate.py: 5 регрессионных контрактов (стиль test_iter6_regression.py, offline source-level).
3. Верификация: py_compile OK · 377 passed (372→+5) · reflex export OK · KPI-прогон 0 failed.
4. Пуш одним коммитом → Railway передеплоит → следующий фингерпринт перемерит.

**План след. итерации:**
1. Гейт-проба с run-unique мыслью (обход dedup) → увидим реальный статус Alby-инвойса на проде (настроен/нет) — это решит, нужен ли владельцу только LSP-фонд или и конфиг.
2. M6: счётчик share-тапов + /health share_count + KPI-проба Share.
3. Проверить, что /health tests=84 — это хардкод; синхронизировать с реальным числом (косметика, низкий приоритет).

**Owner-action (manual steps):**
1. **M7 (главное)**: залить ≥3000 sats в Alby Hub (LSP/канал), убедиться что ALBY_HUB_URL + ALBY_HUB_API_KEY заданы на Railway; оплатить один инвойс с реального LN-кошелька → mint_count ≥ 1 → MintLoop=1. Либо настроить настоящий Stars-инвойс от @BotFather (сейчас заглушка https://t.me/terramon_bot/TERRAMON_STAR_INVOICE).
2. **M1**: открыть игру в Telegram на телефоне, разрешить геолокацию → проверить «📍 Kraków» на карточке существа (device-подтверждение гео).
3. **M8**: пригласить первых реальных игроков в @terramon_bot → /health начнёт показывать player_count>0.
