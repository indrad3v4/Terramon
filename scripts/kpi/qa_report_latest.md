# Terramon — North Star Gap Report (v2) · 2026-08-10 (iter-20)

Fingerprint: `54973835` (прод: `tests:458`, `data_restored_from_snapshot:true`, `restored_seed_count:14`, `restored_share_count:1`, живой `seed_count:29`, `share_count:2`, `mint_count:0`, `data_persisted:false` — volume по-прежнему НЕ примонтирован; durability snapshot/restore (iter-19) РАБОТАЕТ на проде: счётчики пережили редеплой) · Playwright/Chromium headless + TMA-mock · Target: https://terramon-tma-production.up.railway.app

---

## 0. ВЕРДИКТ ДНЯ (TL;DR)

- **North Star Score: 75/100** (плато 9-я итерация; Geo/Lore/Win-path железно; M7 инвойс-нога ДОКАЗАНА 7-й раз + auto-verify ВООРУЖЁН; settle ждёт РЕАЛЬНОГО платежа владельца)
- Топ-3 блокера: **1) M7 settle-нога: нужен РЕАЛЬНЫЙ ПЛАТЁЖ владельца (~3000 sats, кнопка «⚡ Mint via Lightning» на свежем существе) 2) Railway volume НЕ примонтирован (`data_persisted:false` — полные данные стираются редеплоем; выживают только счётчики-снапшоты) 3) нет реальных игроков (M6/M8 — бот/маркетинг)**
- Kill-condition монитор: share 2 · mint 0 · дней с mint=0: **~22/30 — окно kill-condition сокращается (~8 дней)**
- 🎯 **ГЛАВНОЕ СОБЫТИЕ iter-20**: **M6-проба починена и ДОКАЗАНА live** — найден и исправлен реальный баг KPI-пробы: (а) итерация по Playwright-Locator (`for a in locator` → `TypeError: 'Locator' object is not iterable`) — deep-link evidence никогда не снимался; (б) share-карточка пишется в КЛИПБОРД (`rx.set_clipboard`), а проба сканировала DOM — deep link в DOM в принципе не бывает; теперь проба читает `navigator.clipboard.readText()` с `grant_permissions(["clipboard-read","clipboard-write"])`; (в) триггер пробы был `round_no == 1 and has_summoned` — но все 12 архетипов уже засеяны на проде, раунд 1 ВСЕГДА dedup → проба структурно голодала; теперь логика вынесена в модульный `run_share_probe()` и срабатывает на ПЕРВОМ живом пути сессии: либо первый fresh summon в раундах, либо гарантированный fresh summon пост-цикловой M7-пробы (`m6_share_probe_postloop` в m7_probe dict; флаг `M6_SHARE_PROBE_DONE` — один клик «📤 Share» за сессию). Плюс M7-проба теперь снимает `mint_price_sats` (live: 25 — это Stars-прайс на лейбле «⚡ MINT · N sats»; Lightning-инвойс считается через `lightning_mint_price()` с флором 3000 sats — владельцу платить ~3000).

## 1. NORTH STAR SCORE (композит)

| Компонент | Вес | Сегодня | Нормализация |
|---|---|---|---|
| Geo-привязка | 25 | **100%** (12/12 раундов, map-url с реальными координатами 50.0619, 19.9368) | headless-симуляция, ждёт device-проверки |
| Vision-lore («Open your eyes») | 25 | **1** | кнопка в DOM 12/12 (oye_buttons_total: 12) |
| Win-path (достижимость) | 25 | **12/12** | min(архетипов/12, 1) — DISTINCT COUNT: 12, failed_rounds: [] |
| Mint-loop | 25 | **0** | инвойс создан (invoice_ok=True, 7-й прогон), auto-verify вооружён («⏳ Auto-checking payment… 1/30»), settle не было → mint_count=0 |
| **ИТОГО** | 100 | **75/100** | |

Боевая формула (включается, когда есть реальные игроки): NSS = 40·MintRate + 30·D7 + 15·Geo + 15·Lore.

## 2. ГЭП-ТАБЛИЦА (мост «инженерия → северная звезда»)

| # | Метрика | Что меряет | Сегодня | Цель | Гэп | Блокирует | Измерение |
|---|---|---|---|---|---|---|---|
| M1 | Geo% | доля существ с реальными координатами | 12/12 (100%, map-url) | 100% | 🟢 код-ок; ждёт device | share-петлю | AUTO + **device** |
| M2 | Vision-lore | «Open your eyes» + рендер лора | 1 (12/12) | 1 | 🟢 ок | эмоцию/арт | AUTO |
| M3 | Win-path | уникальные архетипы за прогон | 12/12 | 12/12 | 🟢 ок | контентную глубину → D7 | AUTO |
| M4 | Дубликаты | unique/total | 12/12 в прогоне (dedup работает) | 1.0 | 🟢 ок | экономику минта | AUTO |
| M5 | Фрикция | гейт/модалки | 0 блоков (failed_rounds: []) | 0 | 🟢 ок | онбординг → D7 | AUTO |
| M6 | Share-funnel | доля сессий с share-тапом | счётчик жив (share 4→5 в прогоне); **deep-link evidence ДОКАЗАНО live: `share_deep_link:true` + `share_card_has_birthplace:true` (`📍 Краков, Польша`) + `clipboard_read:true`** | ≥2% (kill <2%) | 🔴 нет игроков | охват (kill-condition) | AUTO + **люди** |
| M7 | Mint rate | % саммонеров с mint | 0 (mint_count=0) | ≥2% | 🔴 **инвойс-нога ДОКАЗАНА (7-й раз); settle ждёт платёж; счётчик переживает редеплой (iter-19)** | саму северную звезду | AUTO + **платёж владельца** |
| M8 | D7 retention | возврат на 7-й день | нет данных | кохортный бенчмарк | 🔴 нет игроков | 2-ю половину NSS | **люди** |

Регрессионные guard: **458 тестов зелёные** (без регрессий) · reflex export собирается (exit 0) · py_compile OK · /health tests count синхронизирован (458).

## 3. ТОП-3 БЛОКЕРА (ранжировано)

1. **M7 settle-нога: нужен РЕАЛЬНЫЙ ПЛАТЁЖ** (~3000 sats, ~$0.30) — инвойс создаётся (invoice_ok=True), auto-verify тикает («⏳ 1/30»), но без settle mint_count=0 и MintLoop=0. → **Действие владельца**: открыть игру в Telegram (бот @terrramonBot), призвать существо, нажать «⚡ Mint via Lightning» на свежем существе и оплатить инвойс (WebLN-кошелёк или QR). После платежа mint-запись создастся, snapshot-restore сохранит счётчик через редеплои. Уточнение iter-20: лейбл «⚡ MINT · 25 sats» показывает Stars-прайс (единица — Stars, legacy-поле price_sats); Lightning-инвойс считается с флором 3000 sats (LIGHTNING_MIN_MINT_SATS, JIT-канал Alby Hub) — платить надо ~3000.
2. **Railway volume НЕ примонтирован** (`data_persisted:false`) — полные данные (seeds/players/shares) стираются каждым редеплоем; выживают только счётчики-снапшоты (iter-19, доказано live). → **Действие владельца (1-2 мин)**: Railway Dashboard → проект → Volumes → создать volume `terramon-data` (mount `/app/data`) и приаттачить к сервису; тогда `data_persisted:true`. Код-кандидат след. итерации: полный data-снапшот (litestream-паттерн checkpoint+replay, расширение iter-19) — если volume так и не примонтируют.
3. **Нет реальных игроков** (player_count:0) — M6/M8 и боевая формула NSS мертвы без людей. → Код-сайд: deep link готов (`?startapp=share_`), share-карточка пишется в клипборд. → **Действие владельца**: убедиться, что бот опубликован (BotFather → /setmenubutton → WebApp URL), и запустить охват.

## 4. EVIDENCE

- KPI-прогон iter-20 (5 шт): 12/12 архетипов (failed_rounds: []), geo_ok 12/12, OYE 12/12, `invoice_ok:true` + `auto_verify_seen:true` + `mint_price_sats:25/15` (live, свежие существа), share_count 1→5 на проде (каждый прогон +1), mint_count 0, data_restored_from_snapshot:true (restored seed=14/share=1, живой seed=29+).
- **Live-доказательство M6 (итоговый прогон)**: `m6_share_probe_postloop: {share_before:4, share_after:5, share_delta:1, share_clicked:true, clipboard_error:null, clipboard_read:true, share_deep_link:true, share_link_in_text:false, share_card_has_birthplace:true, share_card_text_snippet:"🃏 Terramon — Lover ✦ Rarity: uncommon ✦ ... Lv.12 · Встречено 0 из 5 мыслей 📍 Кра..."}` — share-карточка на проде РЕАЛЬНО несёт deep link `startapp=share_` + 📍 место рождения; прочитано из клипборда (фикс: origin-scoped `grant_permissions` + `--enable-features=ClipboardReadWrite` + `bring_to_front`).
- Live-доказательство фикса: M6-проба ПОЛНОСТЬЮ ДОКАЗАНА (см. выше: clipboard_read:true, share_deep_link:true, share_card_has_birthplace:true, share_delta:1 — серверный счётчик 4→5); M7-проба сняла mint_price_sats с живой карточки (invoice_ok=true в большинстве прогонов).
- OSS-референсы iter-20: playwright.dev/docs/api/class-locator (locator.all() — Locator не итерируется), playwrightsolutions.com (clipboard: grantPermissions(['clipboard-read','clipboard-write']) + navigator.clipboard.readText()), benbjohnson/litestream (14.2k★, checkpoint+replay для эфемерного диска — паттерн iter-19, кандидат на full-data снапшот), Telegram-Mini-Apps/tma.js (startapp-глубокие ссылки).
- Ограничение честно: headless-геолокация = Playwright grant_permissions + set_geolocation (Kraków), НЕ реальное устройство; place_name на карточке существа (📍 Краков, Польша) ДОКАЗАН через share-карточку в клипборде, но полный flow «device geolocation → карточка» ждёт проверки на реальном устройстве; M6-проба в раундовом цикле может не сработать (все 12 архетипов засеяны → dedup), пост-цикловая проба срабатывает гарантированно.
