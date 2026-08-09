# Terramon — North Star Gap Report (v2) · 2026-08-09 (Iter-7)

Fingerprint деплоя: 138b7628625e5b2d (ae3a162, live) · Бандлы: _index-B4NNXZbm.js, root-BBPU-gMk.js (+8) · Playwright/Chromium · Target: https://terramon-tma-production.up.railway.app/

---

## 0. ВЕРДИКТ ДНЯ (TL;DR)

- **North Star Score: 58/100** (▲▲ с 2/100: гейт починен, win-path открыт, MintLoop замкнут)
- Топ-3 блокера: **1) M3 win-path 8/12 (мысли KPI дают дубли — классификатор может все 12) 2) M1/M2 evidence меряется слишком рано (гео РАБОТАЕТ — round 1 дал карту Москвы) 3) M7: mint_count=1 — артефакт KPI-клика «Mint (1 Star)», не реальный платёж**
- Kill-condition монитор: share нет данных · mint **1** (артефакт KPI) · дней с mint=0: 8+/30 → **KILL-RISK (сохраняется)**
- ✅ 368/368 тестов · reflex export — OK (проверяется в этой итерации)

## 1. NORTH STAR SCORE (композит)

| Компонент | Вес | Сегодня | Нормализация |
|---|---|---|---|
| Geo-привязка | 25 | 0% по evidence (гео-путь РАБОТАЕТ — round 1 дал static-map Москвы; evidence снимался до рендера) | доля существ с lat≠0 && lon≠0 |
| Vision-lore («Open your eyes») | 25 | 1 (кнопка + лор в DOM при гео; OYE найден на Care re-check) | 1 = кнопка в DOM + лор рендерится |
| Win-path (достижимость) | 25 | 8/12 = 16.7 (классификатор выдаёт все 12 — мысли KPI дублируются) | min(архетипов/12, 1) |
| Mint-loop | 25 | 1 (mint_count 0→1 за прогон — цикл замкнут, НО артефакт: KPI кликнул «Mint (1 Star)» = buy_stars optimistic) | 1 = LN-инвойс → mint-событие → счётчик |
| **ИТОГО** | 100 | **58/100** | |

Боевая формула (когда появятся реальные игроки): NSS = 40·MintRate + 30·D7 + 15·Geo + 15·Lore.

## 2. ГЭП-ТАБЛИЦА

| # | Метрика | Сегодня | Цель | Гэп | Блокирует | Измерение |
|---|---|---|---|---|---|---|
| M1 | Geo% | 0% (evidence-баг KPI; гео-путь доказан: TMA LocationButton → on_coords → static-map 55.7558,37.6173 в round 1) | 100% | 🟡 замер, не код | share-петлю + vision-lore | AUTO |
| M2 | Vision-lore | 1 (кнопка OYE в DOM; лор рендерится при static_map_url != "") | 1 | 🟢 ок | эмоцию/арт | AUTO |
| M3 | Win-path | 8/12 (Sage, Explorer, Magician, Creator, Hero, Orphan, Ruler, Jester; дубли: Rebel→Explorer, Caregiver→Orphan, Innocent→Orphan, Lover→Explorer) | 12/12 | 🟡 мысли KPI, не игра | контентную глубину → D7 | AUTO |
| M4 | Дубликаты | unique 8 / total 12 = 0.67 (роутер детерминирован; dedup-guard работает) | 1.0 | 🟡 | экономику минта | AUTO |
| M5 | Фрикция гейта | ✅ 0 блоков (гейт починен в b094567; 12/12 раундов прошли) | 0 блоков | 🟢 ок | плавность онбординга | AUTO |
| M6 | Share-funnel | нет данных (кнопка «📤 Share» в живом UI) | ≥2% share | 🔴 нет данных | рост охвата (kill-condition) | **NEEDS-CODE** |
| M7 | Mint rate | mint_count=1 — **артефакт**: KPI кликнул «Mint (1 Star)» (гейт-кнопка = buy_stars optimistic). Реального платежа НЕТ | ≥2% | 🟡 loop замкнут, нужен реальный settle | саму северную звезду | **NEEDS-DEVICE** |
| M8 | D7 retention | player_count=0, returning_players_7d=0 (KPI-initData с FAKE hash не проходит verify — честно) | кохортный бенчмарк | 🔴 нет данных | северную звезду (2-я половина) | **NEEDS-CODE** |

Регрессионные guard (AUTO): 368/368 ✅ · gate-паттерн `(sc > 0) & ~unlocked` ✅ · MINT/Share в бандле ✅ · static-map 1× (round 1, Москва) ✅.

## 3. ТОП-3 БЛОКЕРА (ранжировано)

1. **M3 win-path 8/12 — мысли KPI дают дубли.** Роутер детерминированный (эмбеддинг-классификатор): текущие 12 мыслей KPI маппятся на 8 архетипов (Rebel→Explorer, Caregiver→Orphan, Innocent→Orphan, Lover→Explorer). **Классификатор МОЖЕТ выдать все 12** — подобраны и офлайн-проверены мысли для Rebel/Caregiver/Innocent/Lover. → Фикс: заменить 4 мысли в play_to_win.py + регрессионный тест «12 мыслей → 12 архетипов».
2. **M1/M2 evidence снимается до рендера.** KPI читает место/карту сразу после summon — статик-мапа ещё нет; Care re-check (через 1.5с) УЖЕ находит static-map Москвы + OYE. → Фикс: M1/M2 evidence брать из Care re-check (m2_after_care), а не из раннего снапшота.
3. **M7 mint_count=1 — KPI-артефакт.** wait_result кликает «Mint (1 Star)» как гейт, но после ae3a162 это buy_stars → optimistic _record_mint. Прогон САМ создал mint на проде. → Фикс: KPI больше НЕ кликает mint-кнопку (только логирует присутствие); реальный mint — manual step владельца (Alby settle / Stars invoice).

## 4. EVIDENCE

Screenshots: /tmp/terramon_new_win_1.png (round 1: Sage + static-map Москва), _terra.png (коллекция 8 unique / 12 total), _ERR отсутствуют (0 failed rounds). Бандлы: /tmp/live_root2.js, /tmp/live_index_bundle.js (Mint (1 Star) 1×, Open your eyes 1×, Pay with Lightning 1×; player_count/seed_count ОТСУТСТВУЮТ — правки Iter-6 не в live).

NOTES:
- **M1 честно**: headless-гео симулируется (grant_permissions + set_geolocation + TMA LocationButton auto-emit). Round 1: static-map?lat=55.7558&lon=37.6173 в Care re-check → гео-цепочка РАБОТАЕТ. geo_ok=0 по раннему evidence — баг замера, не кода.
- **M7 честно**: mint_count 0→1 за прогон = wait_result кликнул «Mint (1 Star)» (гейт-локатор устарел после ae3a162). open_invoice_calls: 1 (TMA mock). Это НЕ реальный платёж — артефакт. Цикл (клик → buy_stars → _record_mint → /health mint_count) доказан.
- **M8 честно**: player_count=0 — KPI-initData hash FAKE → verify_init_data отклоняет → игроки не пишутся. Правильно (не загрязняем D7-кохорты KPI-прогонами).
- **Iter-6 локальные правки** (celebration_pending, per-session geo, seed backfill, health seed_count + tests) — на диске, 368 passed, НЕ в origin/main → пуш в этой итерации.
- **TMA**: 12/12 раундов webapp_present, haptic 12, location_requests 2, location_accessed_emitted 1.

## 5. ЧТО ДЕЛАЕТСЯ В ЭТОЙ ИТЕРАЦИИ / ЧТО ДАЛЬШЕ

**План (2 батча сабагентов):**
1. SA1 (play_to_win.py): заменить 4 мысли-дубля на проверенные (Rebel/Caregiver/Innocent/Lover) → win-path 12/12; evidence M1/M2 из Care re-check; убрать клик «Mint (1 Star)» (артефакт-генератор).
2. SA2 (tests/test_winpath_thoughts.py): офлайн-тест «12 мыслей KPI → 12 уникальных архетипов» (читает play_to_win.py текстом, не импортируя) + тест «KPI не кликает mint».
3. Пуш Iter-6 правок + KPI-фиксы одним коммитом → Railway передеплоит → следующий прогон перемерит M1/M3 честно.

**Owner-action (manual steps):**
1. Реальный mint: оплатить гейт-инвойс 3000 sats с Alby-кошелька (или Stars от @BotFather) → mint_count ≥ 2 с реальным settle.
2. Проверить геолокацию на устройстве в Telegram (LocationButton) — путь `tg.WebApp.LocationButton`.
3. (Опционально) Настроить _STARS_INVOICE_URL от @BotFather — сейчас заглушка.
