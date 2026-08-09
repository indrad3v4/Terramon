# Terramon — North Star Gap Report (v2) · 2026-08-10 (iter-15)

Fingerprint: `baa8de05` (post-iter-14 deploy; новый билд, данные ПЕРЕЖИЛИ редеплой) · Playwright/Chromium headless + TMA-mock · Target: https://terramon-tma-production.up.railway.app

---

## 0. ВЕРДИКТ ДНЯ (TL;DR)

- **North Star Score: 75/100** (→ плато 4-я итерация; Geo/Lore/Win-path железно; M7 код-сайд ЗАКРЫТ и ДВАЖДЫ доказан на проде)
- Топ-3 блокера: **1) M7 settle-нога: нужен РЕАЛЬНЫЙ ПЛАТЁЖ владельца (~3000 sats) 2) нет реальных игроков (M6/M8) 3) полировка воронки (кнопки mint выше сгиба)**
- Kill-condition монитор: share 1 · mint 0 · дней с mint=0: ~16/30 → **НЕ в зоне риска (readiness-фаза)**
- 🎯 **ГЛАВНОЕ СОБЫТИЕ**: (а) инвойс снова создан на проде (`invoice_ok: true`, «⚡ Invoice ready» — Care-панель, post-loop проба); (б) **данные ПЕРЕЖИЛИ редеплой**: seed_count 16→19 + share_count=1 между двумя фингерпринтами — Railway volume, похоже, примонтирован; (в) QR-код инвойса переведён с внешнего api.qrserver.com на ЛОКАЛЬНУЮ генерацию segno (BOLT11 больше не уходит третьей стороне).

## 1. NORTH STAR SCORE (композит)

| Компонент | Вес | Сегодня | Нормализация |
|---|---|---|---|
| Geo-привязка | 25 | **100%** (12/12) | static-map URL с реальными координатами (50.0619, 19.9368); headless-симуляция, ждёт device-проверки |
| Vision-lore («Open your eyes») | 25 | **1** | кнопка в DOM на главной карточке + лор рендерится |
| Win-path (достижимость) | 25 | **12/12** | min(архетипов/12, 1) — полная вселенная |
| Mint-loop | 25 | **0** | инвойс создан (invoice_ok=True), settle не было → mint_count=0 |
| **ИТОГО** | 100 | **75/100** | |

Боевая формула (с реальными игроками): NSS = 40·MintRate + 30·D7 + 15·Geo + 15·Lore.

## 2. ГЭП-ТАБЛИЦА (мост «инженерия → северная звезда»)

| # | Метрика | Что меряет | Сегодня | Цель | Гэп | Блокирует | Измерение |
|---|---|---|---|---|---|---|---|
| M1 | Geo% | доля существ с реальными координатами | 12/12 (100%) | 100% | 🟢 код-ок; ждёт device-проверки | share-петлю | AUTO + **device** |
| M2 | Vision-lore | «Open your eyes» + рендер лора | 1 | 1 | 🟢 ок | эмоцию/арт | AUTO |
| M3 | Win-path | уникальные архетипы за прогон | 12/12 | 12/12 | 🟢 ок | контентную глубину → D7 | AUTO |
| M4 | Дубликаты | unique/total | 12/21 (0.57) | 1.0 | 🟡 инфо (часть — probe-сиды) | экономику минта | AUTO |
| M5 | Фрикция | гейт/модалки | 0 блоков | 0 | 🟢 ок | онбординг → D7 | AUTO |
| M6 | Share-funnel | доля сессий с share-тапом | счётчик работает (+1 честный тап) | ≥2% (kill <2%) | 🔴 нет игроков | охват (kill-condition) | AUTO + **люди** |
| M7 | Mint rate | % саммонеров с mint | 0 (mint_count=0) | ≥2% | 🔴 **инвойс-нога ДОКАЗАНА (2-й раз); settle ждёт платёж** | саму северную звезду | AUTO + **платёж владельца** |
| M8 | D7 retention | возврат на 7-й день | нет данных | кохортный бенчмарк | 🔴 нет игроков | 2-ю половину NSS | **люди** |

Регрессионные guard: **421 тест зелёные** (418 + 3 новых) · reflex export собирается · +3 source-scan гварда (локальный QR, запрет внешнего QR-сервиса, age-based persistence).

## 3. ТОП-3 БЛОКЕРА (ранжировано)

1. **M7 mint-loop: код-сайд цепочка доказана полностью (2-й прогон подряд), остался 1 реальный платёж.** Проба снова кликнула «⚡ Mint via Lightning» (Care-панель) → **`invoice_ok: true`, «⚡ Invoice ready: 3000 sats»** — Alby Hub создаёт инвойс на проде. MintLoop=0 только потому, что инвойс никто не оплатил (settle → `verify_lightning` → `_record_mint` → mint_count=1). **Действие владельца: оплатить инвойс из любого LN-кошелька (~3000 sats) и нажать «✅ I've paid — verify» в игре → M7=1 → NSS=100.** Это ЕДИНСТВЕННЫЙ оставшийся шаг до 100/100 (readiness).
2. **M6/M8: нет реальных игроков.** share-счётчик честно работает (+1 тап/прогон), но kill-condition меряется на пустой аудитории. **Действие владельца: разослать бота, проверить кнопку Mini App в Telegram.** Полировка (кнопки mint выше сгиба на home-карточке) — код-сайд сделана частично в iter-14 (карточка скроллится, ничего не перекрыто), визуальный акцент — следующий проход.
3. **data_persisted — сигнал теперь ЧЕСТНЫЙ (age-based).** В этом прогоне данные ПЕРЕЖИЛИ редеплой (seed_count 16→19, share_count 1 — между фингерпринтами f821d7914 и baa8de05, т.е. билд сменился, а data/ уцелела) → volume, похоже, примонтирован. Чтобы убрать класс ложноположительных срабатываний (маркер выжил, данные стёрты), `DATA_PERSISTED` теперь = выжил маркер **И** файл памяти старше свежего маркера boot'а (`_MEMORY_PATH.stat().st_mtime < _BOOT_MARKER.stat().st_mtime`). След. деплой покажет честное значение.

## 4. ЧТО СДЕЛАНО В ITER-15 (все изменения проверены на диске: grep + pytest + export)

1. **Локальный QR вместо внешнего сервиса (self-custody-фикс, M7-качество)**. Раньше `rx.image(src="https://api.qrserver.com/...")` — BOLT11 инвойс утекал третьей стороне (api.qrserver.com) при каждом показе; при недоступности API QR пропадал. Теперь: `import segno` (стр. 46), хелпер `_qr_data_uri()` (стр. 3175, `segno.make_qr("lightning:" + invoice).png_data_uri(scale=4)` — URI-схема `lightning:` по спецификации BOLT11), state-var `lightning_qr` (стр. 345), заполняется в `mint_lightning` (стр. 1705) и `pay_lightning` (стр. 1820), рендер через `rx.cond(lightning_qr != "", rx.image(...), rx.text("QR unavailable…"))` (стр. 3191-3202). `api.qrserver.com` в модуле: **0 вхождений** (grep подтверждён). Рефы: segno (BSD-3, zero-dep, pure-Python), lightning/bolts BOLT11 (`lightning:` URI), BlitzWallet (self-custodial web — QR локально).
2. **Age-based `DATA_PERSISTED` (честность kill-condition монитора)**. Стр. 172-187: после записи свежего маркера `DATA_PERSISTED = _boot_survived and _MEMORY_PATH.exists() and _MEMORY_PATH.stat().st_mtime < _BOOT_MARKER.stat().st_mtime`. Маркер boot_id/boot_time/survived не тронут.
3. **`/health` tests count синхронизирован: 414 → 421** (стр. 4081) + guard `test_health_tests_count` обновлён на 421 (tests/test_mint_lightning.py:235).
4. **3 новых source-scan гварда**: `test_local_segno_qr_wiring` (import segno + точная строка `segno.make_qr("lightning:" + invoice).png_data_uri(scale=4)` + state-var), `test_no_external_qr_service_anywhere` (api.qrserver.com запрещён по всему модулю), `test_data_persisted_age_based` (mtime-сравнение в boot-регионе, tests/test_health_persistence.py:180-196). Обновлён guard панели: «qrserver not in source» + локальная цепочка `_qr_data_uri` → `lightning_qr` → panel.
5. **requirements.txt**: `segno>=1.6.6` (pure-python, zero deps — безопасно для slim-образа).
6. Верификация: **421 passed, 0 failed** · `reflex export --frontend-only --no-zip` exit 0 · grep'ом подтверждены все 8 точек изменений.

## 5. RESEARCH-РЕФЕРЕНСЫ (обоснование решений iter-15)

- **heuer/segno** (PyPI, BSD-3, pure-Python, НОЛЬ зависимостей; `QRCode.png_data_uri()`; активный, v1.6.6 2025): паттерн «QR-код генерируется локально, инвойс не покидает приложение» → **REPLICATE** (сделано). Архитектура: изолированный энкодер ISO/IEC 18004:2015, никаких сетевых вызовов — идеально для self-custody.
- **lightning/bolts BOLT11** (спецификация инвойсов, QR-ready): QR-код для LN должен кодировать URI-схему `lightning:<bolt11>` — так его сканируют кошельки (Alby, Phoenix и др.) → **REPLICATE** (сделано: `segno.make_qr("lightning:" + invoice)`).
- **BlitzWallet/blitz-web-app** (self-custodial web-платежи, Apache-2.0): принцип «ключи и инвойсы не покидают клиент; QR локально» → **REPLICATE**; их React Native/Expo-стек → **AVOID** (у нас Reflex, переписывать нечего).
- **getalby/hub** (активный, self-custodial LN-нода, NIP-47): паттерн «инвойс → lookup → settled» в `verify_lightning` → **REPLICATE** (уже реализовано; settle ждёт платёж).

---

**NSS: 75/100** · Сделано: локальный segno-QR (BOLT11 больше не утекает на api.qrserver.com), age-based data_persisted (честный сигнал; данные пережили редеплой — volume работает), /health tests 414→421, +3 гварда, 421 тест. · **След. итерация**: (1) перепроверить KPI после деплоя (ждём data_persisted=true + seed_count НЕ сброшен), (2) полировка home-card mint-зоны (кнопки выше сгиба), (3) если появились игроки — старт боевой формулы NSS. · **Действие владельца (критично для NSS=100)**: оплатить LN-инвойс ~3000 sats → «✅ I've paid — verify» → M7=1 → NSS=100; разослать бота (M6/M8).
