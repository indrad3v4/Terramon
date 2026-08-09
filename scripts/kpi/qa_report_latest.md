# Terramon — North Star Gap Report (v2) · 2026-08-09 (iter-10)

Fingerprint: `bc1d70864bdddf9e` (pre-deploy) → после деплоя `e1ebaf1` · Playwright/Chromium headless · Target: https://terramon-tma-production.up.railway.app · Тесты: 398 passed / 0 failed · reflex export: OK

---

## 0. ВЕРДИКТ ДНЯ (TL;DR)

- **North Star Score: 75/100** (без изменений vs вчера, но вскрыт структурный корень блокера M7)
- Топ-3 блокера: **1) M7 Mint-loop = 0/25 (нет игроков + Alby-конфиг неизвестен) 2) M6 Share — измерение только что включено 3) M8 D7 — нет данных (нет верификации игроков)**
- Kill-condition монитор: share — нет данных (0 игроков) · mint 0 · дней с mint=0: с момента запуска → **не применимо, пока нет игроков** (share% не определён)

## 1. NORTH STAR SCORE (композит)

| Компонент | Вес | Сегодня | Нормализация |
|---|---|---|---|
| Geo-привязка | 25 | **100%** | 1/1 раундов geo_ok (доказательство: static-map URL с координатами 50.06,19.94; body-координат нет) |
| Vision-lore («Open your eyes») | 25 | **1** | кнопка в DOM (1 шт. на main-card), лор-блок рендерится |
| Win-path (достижимость) | 25 | **12/12** | 12 уникальных архетипов за прогон (16 карт, дублей нет) |
| Mint-loop | 25 | **0** | mint_count=0 на проде; loop теперь достижим кодом (см. §3) |
| **ИТОГО** | 100 | **75/100** | |

Боевая формула (включается при реальных игроках): NSS = 40·MintRate + 30·D7 + 15·Geo + 15·Lore.

## 2. ГЭП-ТАБЛИЦА (мост «инженерия → северная звезда»)

| # | Метрика | Сегодня | Цель | Гэп | Блокирует | Измерение |
|---|---|---|---|---|---|---|
| M1 | Geo% | 100% (симуляция, Kraków) | 100% реальных | 🟡 ждёт device-тест | идентичность карточки | AUTO (headless) |
| M2 | Vision-lore | 1 | 1 | 🟢 ок | эмоцию/арт | AUTO |
| M3 | Win-path | 12/12 | 12/12 | 🟢 ок | контент → D7 | AUTO |
| M4 | Дубликаты | 12/12 уникальных | 1.0 | 🟢 ок (dedup работает) | экономику минта | AUTO |
| M5 | Фрикция гейта | F3-гейт мёртв by design (см. §3) | 0 блоков | 🟢 для игрока (но LN-путь был недостижим — починено) | онбординг | AUTO |
| M6 | Share-funnel | share_count в /health после деплоя; проба = 1 тап | ≥2% | 🔴 нет данных | kill-condition | AUTO (server-side) |
| M7 | Mint rate | mint_count=0; LN-инвойс-путь теперь достижим | ≥1 минт | 🔴 структурный → починен кодом; ждёт Alby + игроков | северную звезду | AUTO |
| M8 | D7 retention | нет данных (player_count=0) | кохорты | 🔴 нет данных | 2-ю половину NSS | NEEDS-ENV |

Регрессионные guard: 398 тестов зелёные · py_compile OK · reflex export OK.

## 3. ТОП-3 БЛОКЕРА (ранжировано) + ЧТО СДЕЛАНО

1. **M7 Mint-loop (0/25).** Вскрыт структурный корень: `hydrate_from_memory()` считает состояние из ВСЕХ сидов глобально (на проде уже 15), `load_terra` ставит `unlocked=True` каждому посетителю → F3-гейт (`summon_count>0 & ~unlocked`) **никогда не рендерится ни для кого**, а старый KPI-проба ждала именно его (и плодила мусорные сиды «KPI GATE PROBE» — 12→15). Настоящий mint-loop — это MINT-зона карточки существа. **Сделано в iter-10:** новая кнопка **«⚡ Mint via Lightning»** на карточке (Alby Hub BOLT11 на price_sats, mint записывается ТОЛЬКО по settle через verify_lightning; общая `_lightning_invoice_panel()` для гейта и карточки; фикс verify по фактической сумме `lightning_price`). Осталось: Alby-конфиг на проде + реальные игроки.
2. **M6 Share-funnel (нет данных).** Измерение включено: share-реестр (shares.jsonl) + `share_count`/`shares_7d` в /health (доехало в этом деплое), проба кликает «📤 Share» 1 раз за прогон. Реальный % ждёт игроков.
3. **M8 D7 (нет данных).** На проде нет TERRAMON_BOT_TOKEN → initData не верифицируется → все анонимны → player_count=0. Нужен токен бота в Railway env.

**Честные оговорки:** геолокация — Playwright-симуляция (grant_permissions + set_geolocation), не реальное устройство; M1 подтверждается только map-URL-доказательством. Проба создаёт 1 реальный сид на проде за прогон (теперь с правдоподобной русской мыслью, не мусором). Минт-кнопки проба не кликает (политика presence-only), «✅ I've paid» не жмёт, не платит.

## 4. EVIDENCE

- KPI-сессия (этот прогон): geo_ok_rounds=[1] · OYE=1 · distinct=12/12 · mint_button_presence={1:0} (dedup-путь, can_mint=False by design) · probe_seed_created=True · gate-проба старая: gate_seen=false (ожидаемо — гейт мёртв)
- /health до деплоя: `{"status":"ok","tests":84,"mint_count":0,"seed_count":15,"player_count":0,"returning_players_7d":0}` (share_count/alby_configured появятся после деплоя e1ebaf1)
- Коммит: `e1ebaf1` (7 файлов, +1144/−146) — mint_lightning (terramon_tma.py:1627), `_lightning_invoice_panel` (3114, вызовы 2432/3192), verify fix (1785), /health tests=390 (3951), проба «мысль странника» (play_to_win.py:224), контракт-тесты (test_kpi_geo_gate.py), 8 новых тестов (test_mint_lightning.py +7, всего 398)
- Референсы (research): getAlby/hub (инвойс→settle), WebLN (browser-wallet — не для серверных инвойсов), Telegram Stars webhook-паттерн (optimistic-mint = задокументированный MVP-гэп), LNbits
