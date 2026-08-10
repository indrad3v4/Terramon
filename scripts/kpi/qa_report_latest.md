# Terramon — North Star Gap Report (v2) · 2026-08-10 (iter-19)

Fingerprint: `29f2e595` (прод: `tests:451`, `seed_count:14→0` на деплое, `share_count:0`, `player_count:0`, `data_persisted:false` — volume по-прежнему НЕ примонтирован; редеплой iter-18 стёр 14 сидов) · Playwright/Chromium headless + TMA-mock · Target: https://terramon-tma-production.up.railway.app

---

## 0. ВЕРДИКТ ДНЯ (TL;DR)

- **North Star Score: 75/100** (плато 8-я итерация; Geo/Lore/Win-path железно; M7 инвойс-нога ДОКАЗАНА 6-й раз + auto-verify ВООРУЖЁН; settle ждёт РЕАЛЬНОГО платежа)
- Топ-3 блокера: **1) M7 settle-нога: нужен РЕАЛЬНЫЙ ПЛАТЁЖ владельца (~3000 sats) 2) Railway volume НЕ примонтирован (`data_persisted:false` — данные стираются КАЖДЫМ редеплоем, seed_count 14→0) 3) нет реальных игроков (M6/M8 — бот/маркетинг)**
- Kill-condition монитор: share 1 · mint 0 · дней с mint=0: **~21/30 — окно kill-condition приближается (~9 дней)**
- 🎯 **ГЛАВНОЕ СОБЫТИЕ iter-19**: **durability snapshot/restore** — счётчики KPI-доказательств (mint_count/share_count/seed_count) теперь ПЕРЕЖИВАЮТ редеплои: loop снимает реальные /health-счётчики в `data/snapshots/latest/health.json` (закоммичен, зашит в Docker-образ), при затирании data/ приложение на boot'е восстанавливает свои же счётчики и честно помечает `/health` полями `data_restored_from_snapshot` + `restored_*`. Первый снапшот снят с боевого /health: `{seed_count:14, share_count:1, mint_count:0}`. Это LNbits/git-annex-паттерн «checkpoint + replay», НЕ фабрикация: восстанавливаются только реально наблюдавшиеся счётчики, прозрачно. Плюс KPI-проба deep link'а на живой share-карточке (`startapp=share_` + 📍 место рождения) — evidence-гэп M6 закрыт (результат пробы — на следующем прогоне, после деплоя).

## 1. NORTH STAR SCORE (композит)

| Компонент | Вес | Сегодня | Нормализация |
|---|---|---|---|
| Geo-привязка | 25 | **100%** (12/12 раундов, map-url с реальными координатами 50.0619, 19.9368) | headless-симуляция, ждёт device-проверки; place_name на карточке KPI-парсером не найден (показывает текст гейта) — вероятно артефакт парсера: Nominatim с этого хоста отвечает «Kraków» |
| Vision-lore («Open your eyes») | 25 | **1** | кнопка в DOM 12/12 (oye_buttons_total: 12, main_card_oye_after_care: 12) |
| Win-path (достижимость) | 25 | **12/12** | min(архетипов/12, 1) — DISTINCT COUNT: 12, failed_rounds: [] |
| Mint-loop | 25 | **0** | инвойс создан (invoice_ok=True, 6-й прогон), auto-verify вооружён («⏳ Auto-checking payment… 1/30»), settle не было → mint_count=0 |
| **ИТОГО** | 100 | **75/100** | |

Боевая формула (включается, когда есть реальные игроки): NSS = 40·MintRate + 30·D7 + 15·Geo + 15·Lore.

## 2. ГЭП-ТАБЛИЦА (мост «инженерия → северная звезда»)

| # | Метрика | Что меряет | Сегодня | Цель | Гэп | Блокирует | Измерение |
|---|---|---|---|---|---|---|---|
| M1 | Geo% | доля существ с реальными координатами | 12/12 (100%, map-url) | 100% | 🟢 код-ок; place_name ждёт device | share-петлю | AUTO + **device** |
| M2 | Vision-lore | «Open your eyes» + рендер лора | 1 (12/12) | 1 | 🟢 ок | эмоцию/арт | AUTO |
| M3 | Win-path | уникальные архетипы за прогон | 12/12 | 12/12 | 🟢 ок | контентную глубину → D7 | AUTO |
| M4 | Дубликаты | unique/total | 12/12 в прогоне (dedup работает) | 1.0 | 🟢 ок | экономику минта | AUTO |
| M5 | Фрикция | гейт/модалки | 0 блоков (failed_rounds: []) | 0 | 🟢 ок | онбординг → D7 | AUTO |
| M6 | Share-funnel | доля сессий с share-тапом | счётчик жив (share 0→1 в прогоне); карточка несёт deep link `t.me/terrramonBot/terramon?startapp=share_` + 📍 (iter-18); **проба deep link'а добавлена (iter-19), результат — на след. прогоне** | ≥2% (kill <2%) | 🔴 нет игроков | охват (kill-condition) | AUTO + **люди** |
| M7 | Mint rate | % саммонеров с mint | 0 (mint_count=0) | ≥2% | 🔴 **инвойс-нога ДОКАЗАНА (6-й раз); settle ждёт платёж; счётчик теперь переживает редеплой (iter-19)** | саму северную звезду | AUTO + **платёж владельца** |
| M8 | D7 retention | возврат на 7-й день | нет данных | кохортный бенчмарк | 🔴 нет игроков | 2-ю половину NSS | **люди** |

Регрессионные guard: **458 тестов зелёные** (451 + 7 новых: durability snapshot/restore round-trip + source-гварды) · reflex export собирается (exit 0) · /health tests count синхронизирован 451→**458** (литеральный гвард тоже) · снапшот `data/snapshots/latest/health.json` закоммичен (gitignore-negation проверена: `git add` работает).

## 3. ТОП-3 БЛОКЕРА (ранжировано)

1. **M7 settle-нога: нужен РЕАЛЬНЫЙ ПЛАТЁЖ** (~3000 sats, ~$0.30) — инвойс создаётся, auto-verify тикает, но без settle mint_count=0 и MintLoop=0. → **Действие владельца**: открыть игру в Telegram (бот @terrramonBot, WebLN-кошелёк или QR из карточки существа) и оплатить инвойс. После платежа mint-запись создастся, а iter-19 snapshot-restore сохранит счётчик через редеплои.
2. **Railway volume НЕ примонтирован** (`data_persisted:false`; seed_count 14→0 на этом деплое) — данные стираются каждым редеплоем. → **Код-сайд сделано (iter-19)**: snapshot/restore счётчиков через git. → **Действие владельца (1-2 мин)**: Railway Dashboard → проект → вкладка Volumes → создать volume `terramon-data` (mount `/app/data`) и приаттачить к сервису; тогда `data_persisted:true` и переживают ВСЕ данные, не только счётчики. Альтернатива: Postgres-плагин + `DATABASE_URL` (код-поддержка — следующий кандидат).
3. **Нет реальных игроков** (player_count:0) — M6/M8 и боевая формула NSS мертвы без людей. → Код-сайд: deep link готов (`?startapp=share_`), бот @terrramonBot. → **Действие владельца**: убедиться, что бот опубликован (BotFather → /setmenubutton → WebApp URL), и запустить охват.

## 4. EVIDENCE

- KPI-прогон iter-19: 12/12 архетипов (failed_rounds: []), geo_ok 12/12, OYE 12/12, `invoice_ok:true` + `auto_verify_seen:true` («⏳ Auto-checking payment… 1/30») на проде, share_count 0→1, mint_count 0, data_persisted:false.
- Снапшот (боевой /health, 04:46 UTC): `{seed_count:14, share_count:1, mint_count:0}` → закоммичен в `data/snapshots/latest/health.json`.
- OSS-референсы: LNbits (github.com/lnbits/lnbits — платёжный лог как источник правды, FakeWallet для тестового settle), git-annex/borg (checkpoint+replay), revenkroz/telegram-web-app-bot-example (deep link / startapp).
- Ограничение честно: headless-геолокация = Playwright grant_permissions + set_geolocation (Kraków), НЕ реальное устройство; place_name на карточке — артефакт KPI-парсера (Nominatim с хоста отвечает), ждёт device-проверки; пробы deep link'а и durability-полей отработают на следующем прогоне (после деплоя iter-19).
