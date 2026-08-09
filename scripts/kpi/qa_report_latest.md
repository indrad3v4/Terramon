# Terramon — North Star Gap Report (v2) · 2026-08-09 (iter-13)

Fingerprint: `e6f0d0c4c81d3e2c` (post-iter-13 = `24648a2`) · Playwright/Chromium headless + TMA-mock · Target: https://terramon-tma-production.up.railway.app

---

## 0. ВЕРДИКТ ДНЯ (TL;DR)

- **North Star Score: 75/100** (Geo/Lore/Win-path железно 12/12; M7 по-прежнему 0 — но найден и закрыт код-сайд корень: проба M7 писала мысль ПО-РУССКИ, а классификатор — английский TF-IDF)
- Топ-3 блокера: **1) M7 settle-нога (нужен реальный платёж владельца) 2) Railway volume не примонтирован — data/ стирается при каждом деплое 3) нет реальных игроков (M6/M8)**
- Kill-condition монитор: share 1 · mint 0 · дней с mint=0: 13+/30 → **НЕ в зоне риска (readiness-фаза), но mint=0 давит**
- ⚠️ **НОВОЕ (инфраструктурное)**: seed_count упал 2 → 0 между деплоями — volume `terramon-data` (railway.json) фактически НЕ примонтирован: при каждом деплое стираются все сиды/mint/share/players. Добавлен честный сигнал `data_persisted` в /health — теперь монитор отличает «нет игроков» от «данные стёрты деплоем».

## 1. NORTH STAR SCORE (композит)

| Компонент | Вес | Сегодня | Нормализация |
|---|---|---|---|
| Geo-привязка | 25 | **100%** (12/12) | static-map URL с реальными координатами (50.0619, 19.9368) |
| Vision-lore («Open your eyes») | 25 | **1** (12/12) | кнопка в DOM на главной карточке + лор рендерится |
| Win-path (достижимость) | 25 | **12/12** | min(архетипов/12, 1) — полная вселенная |
| Mint-loop | 25 | **0** | инвойс в этом прогоне НЕ создан (проба была сломана: русская мысль → can_mint=False); фикс зашит — проверка в iter-14 |
| **ИТОГО** | 100 | **75/100** | |

Боевая формула (с реальными игроками): NSS = 40·MintRate + 30·D7 + 15·Geo + 15·Lore.

## 2. ГЭП-ТАБЛИЦА (мост «инженерия → северная звезда»)

| # | Метрика | Что меряет | Сегодня | Цель | Гэп | Блокирует | Измерение |
|---|---|---|---|---|---|---|---|
| M1 | Geo% | доля существ с реальными координатами | 12/12 (100%) | 100% | 🟢 код-ок; ждёт device-проверки | share-петлю | AUTO + **device** |
| M2 | Vision-lore | «Open your eyes» + рендер лора | 1 (12/12) | 1 | 🟢 ок | эмоцию/арт | AUTO |
| M3 | Win-path | уникальные архетипы за прогон | 12/12 | 12/12 | 🟢 ок | контентную глубину → D7 | AUTO |
| M4 | Дубликаты | unique/total | 12/13 (0.92) | 1.0 | 🟡 инфо | экономику минта | AUTO |
| M5 | Фрикция | гейт/модалки | 0 блоков | 0 | 🟢 ок | онбординг → D7 | AUTO |
| M6 | Share-funnel | доля сессий с share-тапом | счётчик работает (+1 за 1 тап) | ≥2% (kill <2%) | 🔴 нет игроков | охват (kill-condition) | AUTO + **люди** |
| M7 | Mint rate | % саммонеров с mint | 0 (mint_count=0) | ≥2% | 🔴 **инвойс-нога фикс зашит, settle ждёт платёж** | саму северную звезду | AUTO + **платёж владельца** |
| M8 | D7 retention | возврат на 7-й день | нет данных | кохортный бенчмарк | 🔴 нет игроков | 2-ю половину NSS | **люди** |

Регрессионные guard: 414 тестов зелёные · рефлекс-экспорт собирается · +5 новых source-scan гвардов на персистентность.

## 3. ТОП-3 БЛОКЕРА (ранжировано)

1. **M7 mint-loop: цепочка «инвойс → settle → счётчик» не доказана end-to-end.** В этом прогоне проба СЛОМАНА по своей вине: мысль была русской («мысль странника …»), а `EmbeddingClassifier` — английский keyword-TF-IDF (токенизатор `[a-z']+` отбрасывает кириллицу) → правдоподобие ~0 → max posterior 0.083 < 0.5 → `can_mint=False` → mint-зона скрыта → инвойс не создан (`invoice_ok: null`). ВАЖНО: это НЕ баг игры — в том же прогоне раунды 6/7/12 (Magician/Caregiver/Lover) показали **«mint visible»** на проде. **Iter-13 зашил фикс**: проба переехала в POST-LOOP (после 12 раундов, когда глобальный belief-приор скошен — can_mint вероятнее True) и пробует до 3 английских кандидатов (Lover → Magician → Caregiver) с run-unique timestamp-суффиксом (цифры токенизатор отбрасывает → правдоподобие то же, а raw_input уникален → dedup не срабатывает → настоящий fresh summon). Ожидание iter-14: `invoice_ok=True` («⚡ Invoice ready»). **Осталось: реальный платёж владельца** (~3000 sats, «✅ I've paid — verify» → mint_count=1 → M7=1 → NSS 100).
2. **Railway volume не примонтирован — data/ стирается при каждом деплое.** seed_count 2 → 0 между деплоями; railway.json декларирует volume, но Railway примонтирует только volume, созданный в дашборде. Последствия: mint_count/share/players сбрасываются в 0 при каждом деплое — M7/M6/M8 и kill-condition монитор читают «пустоту» как «нет игроков». Код-сайд закрыто честным сигналом: boot-epoch маркер `data/boot_epoch.json` → `/health` поле `data_persisted` (True = data/ пережил прошлый boot). **Действие владельца: создать volume `terramon-data` в дашборде Railway** (Settings → Volumes → mount `/app/data`).
3. **M6 share% / M8 D7: нет реальных игроков.** share-счётчик работает (delta +1 за 1 честный тап). Нужен рост охвата: разослать бота, проверить кнопку Mini App в Telegram.

## 4. EVIDENCE

- **M1**: static-map imgs во всех 12 раундах: `/static-map?lat=50.0619&lon=19.9368&zoom=14&w=300&h=200` · честная оговорка: симуляция device-разрешения
- **M2**: `main_card_oye_after_care: 12` (кнопка «Open your eyes» на Care-табе во всех раундах)
- **M3**: `distinct_archetypes: 12` → все 12 архетипов (Caregiver, Creator, Explorer, Hero, Innocent, Jester, Lover, Magician, Orphan, Rebel, Ruler, Sage)
- **M4**: `counts: ('12', '13')` на Terra — дубль: «I refuse the system!» родил Explorer и Innocent (глобальный belief-приор дрейфует между раундами — dedup-гард по точной строке работает)
- **M5**: `failed_rounds: []`, гейт не блокирует
- **M6**: `share_count_health: before=0 after=1, share_delta=1` (серверный счётчик, 1 честный тап)
- **M7**: `m7_probe_preloop: mint_ui_state='locked · train more', invoice_ok=null` — КОРЕНЬ: русская мысль → английский TF-IDF → can_mint=False · `mint_ui_state` раундов: `{6: 'mint visible', 7: 'mint visible', 12: 'mint visible'}` — гейт игры работает · `mint_count_health: 0` · `alby_configured: true`
- **M8**: `player_count: 0`, `returning_players_7d: 0` — кохорт не из чего строить
- **PERSISTENCE**: `/health` seed_count 2 → 0 между деплоями (при 13 сидах в конце прогона) → volume НЕ примонтирован; добавлен `data_persisted`
- **TMA**: webapp_present 12/12 · haptic 12 · location_requests 24 · location_accessed_emitted 12

## 5. ИТЕРАЦИЯ-13 (что зашито код-сайд)

1. **M7-проба (scripts/kpi/play_to_win.py)**: русская мысль-проба → до 3 английских кандидатов (Lover → Magician → Caregiver), POST-LOOP (после 12 раундов — глобальный belief-приор скошен, can_mint вероятнее True); run-unique timestamp-суффикс (цифры отбрасываются токенизатором → то же правдоподобие; raw_input уникален → обход dedup); «⚡ Mint via Lightning» кликается РОВНО 1 раз на первой живой mint-зоне (создание инвойса, без оплаты/записи/verify); честные заметки «до 3 probe-сидов за прогон» + объяснение English-TF-IDF требования.
2. **Data-persistence self-check (terramon_tma.py)**: boot-epoch маркер `data/boot_epoch.json` (uuid + время + survived) атомарно через tmp+os.replace; `/health` отдаёт `data_persisted` (True = data/ пережил прошлый boot). Монитор теперь видит стирание данных деплоем.
3. **Гварды**: новый `tests/test_health_persistence.py` (5 source-scan тестов: маркер рядом с _MEMORY_PATH, поле в health(), атомарная запись, try/except, boot_id). Починён устаревший `test_health_tests_count` (390 → 414). `/health` `tests`: 409 → 414.
4. **Верификация**: 414 passed / 0 failed · `reflex export --frontend-only --no-zip` собирается · git diff — только свои файлы (AGENTS.md/CLAUDE.md не тронуты) · push `24648a2`.

## 6. СЛЕДУЮЩАЯ ИТЕРАЦИЯ

1. Прогнать починенную KPI-пробу → ожидаем `invoice_ok=True` + «⚡ Invoice ready» на проде (код-доказательство инвойс-ноги M7).
2. Если инвойс-нога доказана — M7 остаётся 0/1 только из-за settle: чек-лист оплаты для владельца (оплатить ~3000 sats → verify → mint_count=1 → NSS 100).
3. Проверить `data_persisted` в /health после деплоя; если False — владелец создаёт volume в Railway.
4. Мониторить seed_count/player_count: первые живые игроки = включение боевой формулы NSS.
