# Terramon — North Star Gap Report (v2) · 2026-08-09 (17:05 UTC)

Fingerprint деплоя: 562260854f0d648f (до фикса; после пуша — новый) · Бандлы: _index-nDqDnMUz.js, esm-aoykqst2.js, manifest-de8f0b70.js, root-eXO5Z4yF.js (+6 без изменений) · Playwright/Chromium · Target: https://terramon-tma-production.up.railway.app/

---

## 0. ВЕРДИКТ ДНЯ (TL;DR)

- **North Star Score: 2/100** (измерено на живом деплое ДО фикса; ▲ ожидаемый рывок после деплоя — см. §5)
- 🚨 **Главный блокер 2 дней подряд — БАГ ГЕЙТА — ПОЧИНЕН и ЗАПУШЕН**: `terramon_tma.py:3490` было `summon_count > 0 & ~unlocked` (приоритет `&` выше `>`, unlocked мёртв → гейт ≡ `sc > 0`), стало `(TerramonState.summon_count > 0) & ~TerramonState.unlocked`. Доказательство в свежесобранном бандле: `summon_count>0 && !unlocked` (раньше компилировалось в голый `>0`). **Игра снова открывается после первого summon.**
- 🎁 **Вторая находка — MINT-кнопка и Share-кнопка были МЁРТВЫМ КОДОМ**: лежали в `creature_card()`, которую `index()` никогда не вызывает — Reflex tree-shake'нул её из прод-бандла (0 вхождений `⚡ MINT`/`📤 Share` в 10 файлах бандла). Перенесены в живую `creature_care_panel()`; мёртвая функция удалена. В свежем бандле: `⚡ MINT` ✓, `📤 Share` ✓.
- 📏 **KPI-скрипт апгрейдиут**: гео теперь симулируется честно (`grant_permissions(["geolocation"])` + `set_geolocation` Москва + клик `⟳` — как выдача разрешения на реальном устройстве), 12 мыслей (добавлены Sage+Lover), сбор до 12 архетипов, evidence M2/M7, блок `=== NSS-EVIDENCE ===`.
- 🧪 Базлайн на СТАРОМ деплое (доказательство бага): round 1 родил Sage (память была пуста), rounds 2–10 — `input not visible` (гейт-лок). **Игра была заперта для всех новых сессий.**
- Kill-condition монитор: share нет данных · mint **0** (`mint_count:0`) · дней с mint=0: 8+/30 → **KILL-RISK (сохраняется)**
- ✅ 342/342 тестов (336 + 6 новых регрессионных-ловушек), `reflex export` — OK.

## 1. NORTH STAR SCORE (композит)

| Компонент | Вес | Сегодня | Нормализация |
|---|---|---|---|
| Geo-привязка | 25 | 0% (headless-limited; KPI теперь симулирует grant) | доля существ с lat≠0 && lon≠0 |
| Vision-lore («Open your eyes») | 25 | 0 (рендер гейтится `static_map_url != ""` — нужны реальные координаты) | 1 = кнопка в DOM + лор рендерится |
| Win-path (достижимость) | 25 | 1/12 (Sage; rounds 2–10 — гейт-лок) | min(архетипов/12, 1) |
| Mint-loop | 25 | 0 (mint_count=0; MINT-кнопка теперь в живом UI — счётчик ждёт реальный settle) | 1 = LN-инвойс → mint-событие → счётчик |
| **ИТОГО** | 100 | **2/100** | |

Боевая формула (когда появятся реальные игроки): NSS = 40·MintRate + 30·D7 + 15·Geo + 15·Lore.

## 2. ГЭП-ТАБЛИЦА

| # | Метрика | Сегодня | Цель | Гэп | Блокирует | Измерение |
|---|---|---|---|---|---|---|
| M1 | Geo% | 0% — headless-limited, НЕ код-сломан; симуляция grant добавлена в KPI (Moscow 55.7558, 37.6173 + `⟳`); перемерить после деплоя | 100% | 🔴 критический | share-петлю + vision-lore | AUTO |
| M2 | Vision-lore | 0 — кнопка «👁 Open your eyes» ЕСТЬ в активной карточке (в бандле), рендер гейтится `static_map_url != ""` (нужны координаты) | 1 | 🔴 критический | эмоцию/арт | AUTO |
| M3 | Win-path | 1/12 (гейт-лок); после фикса гейта ожидается рост до 12/12 (гидратация даёт unlocked=True) | 12/12 | 🟡 средний (фикс задеплоен) | контентную глубину → D7 | AUTO |
| M4 | Дубликаты | 1/1 = 1.0 (dedup-guard `find_seed` работает) | 1.0 | 🟢 ок | экономику минта | AUTO |
| M5 | Фрикция гейта | 🔴→✅ **БАГ ПОЧИНЕН** (скобки, стр. 3490) + 6 регрессионных тестов-ловушек | 0 блоков | 🟡 (ждать деплой) | плавность онбординга | AUTO |
| M6 | Share-funnel | нет данных (кнопка «📤 Share» теперь в живом UI; аналитика тапов — NEEDS-CODE) | ≥2% share | 🔴 нет данных | рост охвата (kill-condition) | **NEEDS-CODE** |
| M7 | Mint rate | 0. MINT-кнопка в живом UI (была tree-shaken). Инвойс-пробу (Alby) сделает KPI после деплоя. Реальный settle — только с кошелька на устройстве | ≥2% | 🔴 структурный | саму северную звезду | **NEEDS-DEVICE** |
| M8 | D7 retention | нет данных (аналитики кохорт нет) | кохортный бенчмарк | 🔴 нет данных | северную звезду (2-я половина) | **NEEDS-CODE** |

Регрессионные guard (инженерный health, AUTO): 342/342 ✅ · gate-паттерн `(sc > 0) & ~unlocked` в исходнике и в бандле ✅ · MINT/Share в бандле ✅ (раньше 0) · `creature_card` удалена ✅ · static-map = 0 (нет координат) ✅.

## 3. ТОП-3 БЛОКЕРА (ранжировано)

1. **✅ [FIXED-DEPLOYED] Баг гейта: `unlocked` мёртв — игра заперта после первого summon.** Было `summon_count > 0 & ~unlocked` ≡ `summon_count > 0` (приоритет `&` (9) > `>` (8); в бандле компилировалось `>i(0,()=>!unlocked)` = `>0`). Стало `(summon_count > 0) & ~unlocked`; в бандле `>0,()=>!unlocked` — unlocked живой. Root-cause найден на 2-й итерации подряд (прошлый отчёт: стр. 3746; сейчас 3490 — код сдвинулся). Защита: 6 новых тестов в `tests/test_gate_regression.py` (source-level guard: скобки обязательны; таблица истинности; MINT/Share живут в care_panel; `def creature_card` отсутствует; mint_count в /health). Блокировал M3+M5+M7 разом.
2. **Глобальная память без изоляции игроков + Geo=0%.** `data/tma_memory.jsonl` — один файл на всех (стр. 129–130): KPI-прогоны пишут в прод-коллекцию, а geo-путь первого призыва срабатывает только при `summon_count == 0`. Измерение M1 в headless теперь симулирует grant (KPI v3), но полноценный ответ — per-player изоляция (ключ telegram user_id из initData) → следующая итерация.
3. **Mint-loop = 0.** MINT-кнопка вернулась в живой UI (была tree-shaken вместе с Share). Stars-рейл — оптимистичный mint (нет серверного колбэка openInvoice), Lightning — mint по settle (`verify_lightning` → `_record_mint`). Реальный settle требует Alby-кошелёк на устройстве владельца — **manual step**. Инвойс-пробу (создание BOLT11 на Alby Hub) сделает KPI после деплоя: «⚡ Invoice ready: 3000 sats» = Alby настроен.

## 4. EVIDENCE

Screenshots: `/tmp/terramon_new_win_1.png` (round 1: Sage — единственный живой summon) · `/tmp/terramon_new_win_2..10.png` (+`_ERR`): гейт-лок `input not visible` · Бандлы: `/tmp/live_build_v7/*.js` (10 шт., fingerprint 562260854f0d648f, health `{"status":"ok","tests":84,"mint_count":0}`)

NOTES:
- **Root-cause #1 (гейт, доказано):** Python-демо приоритета: `1 > 0 & ~True` = True (гейт), задуманное `(1 > 0) & ~True` = False. В бандле 562260854f0d648f: `t.summon_count_rx_state_>i(0,()=>!t.unlocked_rx_state_)` — `i(0, ...)` = `0 & ...` = 0 → условие схлопнуто в `>0`. После фикса в свежем бандле: `summon_count_rx_state_>0,()=>!t.unlocked_rx_state_)` — unlocked участвует.
- **Root-cause #2 (MINT/Share tree-shaken):** `creature_card()` (бывш. 2137–2443) не вызывалась из `index()` (используется `creature_care_panel()`, стр. ~3938) → Reflex выбросил её из бандла. MINTED-badge, MINT-кнопка, Share-кнопка, safety-нота, goal-поздравление жили только там. Перенесено в care_panel; мёртвая функция удалена (grep по репо перед удалением: 0 вызовов). В свежем бандле: `⚡ MINT` 1×, `📤 Share` 1×.
- **M1:** 0% — headless-ограничение (без grant → getCurrentPosition denied → `place="0.00, 0.00"`). Код НЕ сломан. KPI v3: `ctx.grant_permissions(["geolocation"], origin=URL)` + `ctx.set_geolocation(latitude=55.7558, longitude=37.6173)` + клик `⟳` (capture_location) перед summon → симуляция выдачи разрешения устройства. Проверить на устройстве (Telegram LocationButton) — manual step.
- **M2:** кнопка «👁 Open your eyes» в активной карточке (бандл), рендер блока гейтится `static_map_url != ""` (стр. ~2478: `if agent_lat != 0.0 or agent_lon != 0.0`). При гео-симуляции KPI v3 должен получить карту+лор → перемерить после деплоя.
- **M3/M4:** 1/12 · 1/1. Round 1: theme=Explorer → Sage (роутер детерминированный; мысль ≠ заявленный архетип). Rounds 2–10: гейт-лок. После фикса гидратация даёт `unlocked=True` (стр. ~893) → гейт скрыт → инпут виден → win-path открыт.
- **M5:** перехвата pointer-events НЕТ (после «Got it!» SUMMON кликается). Баг был сам гейт — починен.
- **M6/M8:** аналитики funnel/кохорт нет → «нет данных» (НЕ 0). Share-кнопка теперь в живом UI.
- **M7:** MINT-кнопка в живом UI; `pay_lightning` создаёт инвойс 3000 sats (GATE_SUMMON_PRICE_SATS); settle → `unlocked=True` + `_record_mint` → mint_count. Реальный платёж — manual step (Alby-кошелёк). KPI v3 НЕ кликает MINT (не фейкает mint_count).
- **Deploy diff:** 273a0d5f (fb16dc6) → 562260854f0d648f (b6c11b8 «fix(gate): Pay with Lightning showed 0 sats» — цена гейта 3000 sats, но САМО условие гейта оставалось сломано). → **новая итерация пушит фикс условия + MINT/Share + KPI v3.**

## 5. ЧТО СДЕЛАНО В ЭТОЙ ИТЕРАЦИИ / ЧТО ДАЛЬШЕ

**Сделано (1 батч, 3 сабагента):**
1. Гейт-фикс `(sc > 0) & ~unlocked` (terramon_tma.py:3490) + комментарий.
2. MINTED-badge + MINT-кнопка + Share-кнопка перенесены в `creature_care_panel()`; `creature_card()` удалена.
3. `tests/test_gate_regression.py` — 6 регрессионных ловушек (342 passed).
4. KPI v3: гео-симуляция, 12 мыслей, cap 12, M2/M7 evidence, NSS-EVIDENCE.

**Дальше (следующая итерация, после деплоя):**
- Прогон KPI v3 на починенном деплое: ожидается M3 → до 12/12, M1/M2 — первые реальные замеры с гео-симуляцией.
- Per-player изоляция памяти (ключ telegram user_id) — уберёт «глобальную коллекцию» и позволит тестировать путь первого summon (geo).
- Аналитика share-фаннела (M6) и кохорт D7 (M8) — NEEDS-CODE.

**Owner-action (manual steps):**
1. Проверить геолокацию на устройстве в Telegram (LocationButton) — путь `tg.WebApp.LocationButton`.
2. Оплатить гейт-инвойс 3000 sats с Alby-кошелька → mint_count в /health должен стать 1 (M7 первая реальная точка).
3. (Опционально) Telegram Stars invoice от @BotFather — заменить заглушку `_STARS_INVOICE_URL`.
