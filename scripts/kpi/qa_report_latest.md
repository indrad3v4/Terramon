# Terramon — North Star Gap Report (v2) · 2026-08-10 (iter-18)

Fingerprint: `b3b58f7` (прод: `tests:437`, `seed_count:14→17`, `share_count:1`, `player_count:0`, `data_persisted:false` — volume по-прежнему НЕ примонтирован) · Playwright/Chromium headless + TMA-mock · Target: https://terramon-tma-production.up.railway.app

---

## 0. ВЕРДИКТ ДНЯ (TL;DR)

- **North Star Score: 75/100** (плато 7-я итерация; Geo/Lore/Win-path железно; M7 инвойс-нога ДОКАЗАНА 5-й раз + auto-verify ВООРУЖЁН на проде; settle ждёт реального платежа)
- Топ-3 блокера: **1) M7 settle-нога: нужен РЕАЛЬНЫЙ ПЛАТЁЖ владельца (~3000 sats) 2) нет реальных игроков (M6/M8) 3) Railway volume НЕ примонтирован (`data_persisted:false` — данные стираются редеплоем)**
- Kill-condition монитор: share 1 · mint 0 · дней с mint=0: ~19/30 → **НЕ в зоне риска (readiness-фаза)**
- 🎯 **ГЛАВНОЕ СОБЫТИЕ iter-18**: **share-карточка получила гео-идентичность + Telegram deep link с share_code** — карточка теперь несёт строку «📍 <место рождения>» (self.place → geo_place → координаты 2 знака, «0.00, 0.00» отсекается) и вместо косметического «🌍 terramon.app» — реальную ссылку `https://t.me/terrramonBot/terramon?startapp=share_XXXX` (8-символьный код из timestamp, та же деривация, что в AgentSummoned). Это прямой удар по M6-петле (kill-condition: share ≥2%): карточка стала НОСИТЕЛЕМ идентичности существа + виральным входом в игру для того, кто её получил. KPI-прогон подтвердил на проде: auto-verify тикает (`⏳ Auto-checking payment… 1/30`), `invoice_ok:true`, 12/12 архетипов.

## 1. NORTH STAR SCORE (композит)

| Компонент | Вес | Сегодня | Нормализация |
|---|---|---|---|
| Geo-привязка | 25 | **100%** (map-url 1/1) | static-map URL с реальными координатами (50.0619, 19.9368); headless-симуляция, ждёт device-проверки; **НОВОЕ: place_name=None — человеческое имя места на карточке KPI-парсером не найдено, помечено «ждёт device-проверки»** |
| Vision-lore («Open your eyes») | 25 | **1** | кнопка в DOM на главной карточке + после Care-таба (oye: 1, main_card_oye_after_care: 1) |
| Win-path (достижимость) | 25 | **12/12** | min(архетипов/12, 1) — полная вселенная |
| Mint-loop | 25 | **0** | инвойс создан (invoice_ok=True, 5-й прогон), auto-verify вооружён, settle не было → mint_count=0 |
| **ИТОГО** | 100 | **75/100** | |

Боевая формула (включается, когда есть реальные игроки): NSS = 40·MintRate + 30·D7 + 15·Geo + 15·Lore.

## 2. ГЭП-ТАБЛИЦА (мост «инженерия → северная звезда»)

| # | Метрика | Что меряет | Сегодня | Цель | Гэп | Блокирует | Измерение |
|---|---|---|---|---|---|---|---|
| M1 | Geo% | доля существ с реальными координатами | 12/12 (100%, map-url) | 100% | 🟢 код-ок; place_name ждёт device | share-петлю | AUTO + **device** |
| M2 | Vision-lore | «Open your eyes» + рендер лора | 1 | 1 | 🟢 ок | эмоцию/арт | AUTO |
| M3 | Win-path | уникальные архетипы за прогон | 12/12 | 12/12 | 🟢 ок | контентную глубину → D7 | AUTO |
| M4 | Дубликаты | unique/total | 12/12 в прогоне (probe-сиды 17 на проде) | 1.0 | 🟢 ок (dedup работает) | экономику минта | AUTO |
| M5 | Фрикция | гейт/модалки | 0 блоков (failed_rounds: []) | 0 | 🟢 ок | онбординг → D7 | AUTO |
| M6 | Share-funnel | доля сессий с share-тапом | счётчик работает (share=1 на проде); **карточка теперь несёт 📍 место + deep link с share_code (iter-18)** | ≥2% (kill <2%) | 🔴 нет игроков | охват (kill-condition) | AUTO + **люди** |
| M7 | Mint rate | % саммонеров с mint | 0 (mint_count=0) | ≥2% | 🔴 **инвойс-нога ДОКАЗАНА (5-й раз); auto-verify ВООРУЖЁН на проде (маркер «⏳ Auto-checking…»); settle ждёт платёж** | саму северную звезду | AUTO + **платёж владельца** |
| M8 | D7 retention | возврат на 7-й день | нет данных | кохортный бенчмарк | 🔴 нет игроков | 2-ю половину NSS | **люди** |

Регрессионные guard: **451 тест зелёный** (437 + 14 новых: 13 source/behavior-гвардов share-card geo + deep link, 1 поведенческий) · reflex export собирается (exit 0) · /health tests count синхронизирован 437→**451** (guard, рассинхронизированный в рабочем дереве — ожидал 437 при коде 451 — починен) · 7 KPI-маркеров байт-в-байт.

## 3. ТОП-3 БЛОКЕРА (ранжировано)

1. **M7 settle-нога — нужен реальный платёж владельца.** Инвойс-создание доказано на проде 5 раз подряд (`invoice_ok:true`, «⚡ Invoice ready» — Caregiver post-loop проба; auto-verify тикает «⏳ Auto-checking payment… 1/30» на живой пробе). mint_count=0, потому что никто не платил. → **Owner action**: открыть приложение в Telegram, призвать существо (англ. мысль, 1-5 призывов), дождаться mint-кнопки, нажать «⚡ Mint via Lightning» (~3000 sats), оплатить из LN-кошелька — минт запишется АВТОМАТИЧЕСКИ → mint_count станет 1 → M7=1 → **NSS = 100**.
2. **Нет реальных игроков (M6/M8).** Все 17 seed_count на проде — probe-сиды KPI-прогонов. → **Owner action**: запустить тестовую аудиторию/друзей; share-карточка теперь готова к виральности (📍 место + t.me deep link).
3. **Railway volume НЕ примонтирован**: `data_persisted:false` на текущем деплое — mint-рекорды/игроки не переживут редеплой. → **Owner action**: в Railway dashboard примонтировать volume `terramon-data` к сервису (railway.json уже декларирует mount /app/data).

## 4. EVIDENCE

- NSS-прогон: geo_ok 1/1 раундов (map-url: `/static-map?lat=50.0619&lon=19.9368`) · distinct 12/12 · OYE 1 в DOM (main + Care) · mint_ui_state: «mint visible» в post-loop пробе · `invoice_ok:true` + «⚡ Invoice ready» (Caregiver) · **auto_verify_seen:true, маркер «⏳ Auto-checking payment… 1/30»** (live-деплой, ~7с после клика) · mint_count_health: 0 · m6 share_count: 1 · place_name_rounds: [null] · failed_rounds: [] · TMA: injected-mock, initData hash FAKE (без бот-токена), open_invoice_calls: 0 (presence-only политика, минт-кнопка не кликается в основном прогоне)
- Share-card geo identity (iter-18, terramon_tma.py): `_share_code_from_seed` (:333-350, getattr-guarded, timestamp-деривация байт-в-байт как в summon_service AgentSummoned) · state `share_code: str = ""` (:371) · заполнение в обоих путях: свежий summon (:731) и M4-dedup hydrate (:1134) · `share_creature` (:2030-2049): `_MEMORY.record_share()` ПЕРВОЙ строкой → `_place`-цепочка (place → geo_place → lat/lon 2 знака, «0.00, 0.00» → "") → `📍 {_place}` строка → deep link `t.me/terrramonBot/terramon?startapp=share_XXXX` с fallback на голый bot-линк; маркер «📤 Creature card copied! Share it anywhere.» байт-в-байт сохранён
- KPI-апгрейд (scripts/kpi/play_to_win.py): `place_name_from_body` — M1-свидетельство человеческого имени места с карточки («Kraków, Polska» стиль); `auto_verify_seen`/`auto_verify_marker` — фиксация вооружённости auto-verify на проде (False никогда не считается пассом)
- Тесты: +14 (13 source-гвардов: record_share первой строкой / 📍-строка / fallback-цепочка + zero-guard / deep-link с share_code / fallback-линк / маркер байт-в-байт / state-var / оба пути заполнения / helper-юниты: None-seed, stored-code, timestamp-деривация, never-raises, кросс-чек с summon_service, формат t.me/<bot>/<app>?startapp=; 1 guard /health 437→451) → **451 passed, 0 failed** · `reflex export --frontend-only --no-zip` exit 0
- RESEARCH-референсы: **Make-TON-Telegram-Mini-App-3** (nikandr-surkov, GitHub, Next.js 14 + TS): referral-система через инвайт-кнопку + инвайт-линк — `?startapp=<param>` передаётся мини-аппу как tgWebAppStartParam → REPLICATE: наш deep link `?startapp=share_<code>` (зафиксирован source-гвардом); AVOID: file-based storage без персистентности (у нас JsonMemory + volume). **Telegram core docs** (core.telegram.org/bots/webapps): непустой `startapp` в прямой ссылке → start_param + tgWebAppStartParam → REPLICATE: share_code в startapp для будущего онбординга «ты пришёл за существом друга»; AVOID: полагаться на `shareMessage` (требует bot API 7.2+ и медиа-подготовку — у нас текстовый clipboard-флоу, работает в любом клиенте)
- Ограничение честности: гео — симуляция device-разрешения (Playwright grant_permissions + set_geolocation), place_name на карточке не подтверждён на headless (Nominatim-резолв идёт на бэкенде при summon; KPI place_name=None в этом прогоне — может быть артефактом headless/mock, нужен реальный девайс); TMA — injected-mock (headless без Telegram runtime), initData hash FAKE без бот-токена; auto-verify проверен юнит-тестами + маркер на живой пробе, боевой settle ждёт реального платежа; share=1 на проде — без дельты (раунд без успешного summon), вероятно от прошлых прогонов/реального визита.

---

**NSS: 75/100** · Сделано: share-карточка обрела гео-идентичность («📍 место рождения») + Telegram deep link с 8-символьным share_code (M6-петля: карточка = носитель идентичности + виральный вход), KPI-зонды place_name + auto-verify (подтверждён ВООРУЖЁННЫМ на проде: «⏳ Auto-checking payment… 1/30»), guard /health 437→451, +14 гвардов, **451 тест зелёный**, reflex export exit 0. · **След. итерация**: (1) перепроверить KPI после деплоя (ждём tests:451 на проде + share deep link в карточке), (2) полировка home-card mint-зоны (визуальный акцент кнопок выше сгиба — M5), (3) подготовка D7-кохорт (player_id → first_seen → возвраты) под боевую формулу. · **Действие владельца (критично для NSS=100)**: оплатить LN-инвойс ~3000 sats → минт запишется АВТОМАТИЧЕСКИ → M7=1 → NSS=100; примонтировать Railway volume (data_persisted); разослать бота (M6/M8).
