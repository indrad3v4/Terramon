# Terramon — North Star Gap Report (v2) · 2026-08-12 (iter-22)

Fingerprint: `1c29305c` (прод: `tests:496*`, `data_persisted:true` ✅ — Railway volume ПРИМОНТИРОВАН (блокер iter-20 закрыт!), `data_restored_from_snapshot:true`, `restored_seed_count:40`, `restored_share_count:5`, живой `seed_count:40`, `share_count:5→6`, `mint_count:0`, `alby_configured:true`) · Playwright/Chromium headless + TMA-mock · Target: https://terramon-tma-production.up.railway.app · *496 — счётчик в /health синхронизирован этим коммитом.

---

## 0. ВЕРДИКТ ДНЯ (TL;DR)

- **North Star Score: 75/100** (плато 10-я итерация; Geo/Lore/Win-path железно; инвойс-нога M7 доказана live 8-й раз; MintLoop=0 — ждёт РЕАЛЬНОГО платежа владельца)
- Топ-3 блокера: **1) M7 settle-нога: нужен РЕАЛЬНЫЙ ПЛАТЁЖ владельца (~3000 sats) — kill-окно ~6 дней! 2) нет реальных игроков (player_count:0 → M6/M8 и боевая формула мертвы) 3) M1 ждёт device-проверки** (код 100%, симуляция)
- Kill-condition монитор: share 6 · mint 0 · дней с mint=0: **~24/30 — окно kill-condition СЖИМАЕТСЯ (~6 дней)**
- 🎯 **ГЛАВНОЕ СОБЫТИЕ iter-22 — де-риск ручного шага владельца к MintLoop=1**: (а) починен ЛОЖНЫЙ лейбл «⚡ MINT · 15 **sats**» — это Telegram **Stars**-рейл (оптимистичный openInvoice), а Lightning-инвойс 3000 sats; теперь «⚡ MINT · N Stars» + на кнопке «⚡ Mint via Lightning · **3000 sats**» честная цена (computed var, floor LIGHTNING_MIN_MINT_SATS); (б) «📋 Copy BOLT11» + «✓ Инвойс скопирован» в инвойс-панели (паттерн rx.set_clipboard из share_creature; getalby/lightning-browser-extension: пользователю — точная сумма + copy-аффорданс); (в) **M8 D7-кохорта замерена кодом**: JsonMemory.d7_cohort_stats() (eligible/retained/rate) + days_since_last_mint() → /health отдаёт d7_eligible/d7_retained/d7_retention/days_since_last_mint/kill_condition{triggered}. Всё покрыто +30 тестами (496 зелёных).

## 1. NORTH STAR SCORE (композит)

| Компонент | Вес | Сегодня | Нормализация |
|---|---|---|---|
| Geo-привязка | 25 | **100%** (12/12 раундов, map-url с реальными координатами 50.0619, 19.9368) | headless-симуляция, ждёт device-проверки |
| Vision-lore («Open your eyes») | 25 | **1** | кнопка в DOM 12/12 (oye_buttons_total: 12) |
| Win-path (достижимость) | 25 | **12/12** | min(архетипов/12, 1) — DISTINCT COUNT: 12, failed_rounds: [] |
| Mint-loop | 25 | **0** | инвойс создан (invoice_ok=true, 8-й прогон), auto-verify вооружён («⏳ Auto-checking payment… 1/30»), settle не было → mint_count=0 |
| **ИТОГО** | 100 | **75/100** | |

Боевая формула (включается, когда есть реальные игроки): NSS = 40·MintRate + 30·D7 + 15·Geo + 15·Lore.

## 2. ГЭП-ТАБЛИЦА (мост «инженерия → северная звезда»)

| # | Метрика | Что меряет | Сегодня | Цель | Гэп | Блокирует | Измерение |
|---|---|---|---|---|---|---|---|
| M1 | Geo% | доля существ с реальными координатами | 12/12 (100%, map-url) | 100% | 🟢 код-ок; ждёт device | share-петлю | AUTO + **device** |
| M2 | Vision-lore | «Open your eyes» + рендер лора | 1 (12/12) | 1 | 🟢 ок | эмоцию/арт | AUTO |
| M3 | Win-path | уникальные архетипы за прогон | 12/12 | 12/12 | 🟢 ок | контентную глубину → D7 | AUTO |
| M4 | Дубликаты | unique/total | 12/14 в прогоне (dedup работает) | 1.0 | 🟢 ок | экономику минта | AUTO |
| M5 | Фрикция | гейт/модалки | 0 блоков (failed_rounds: []) | 0 | 🟢 ок | онбординг → D7 | AUTO |
| M6 | Share-funnel | доля сессий с share-тапом | счётчик жив (5→6 в прогоне); deep-link + 📍 в клипборде доказаны live | ≥2% (kill <2%) | 🔴 нет игроков | охват (kill-condition) | AUTO + **люди** |
| M7 | Mint rate | % саммонеров с mint | 0 (mint_count=0) | ≥2% | 🔴 **инвойс-нога доказана (8-й раз); settle ждёт платёж; UX-де-риск сделан (Stars-лейбл, Copy BOLT11)** | саму северную звезду | AUTO + **платёж владельца** |
| M8 | D7 retention | возврат на 7-й день (кохорты) | **замерен кодом** (d7_eligible/retained/rate в /health; с игроками=0 → 0/0/0.0) | кохортный бенчмарк | 🔴 нет игроков | 2-ю половину NSS | AUTO + **люди** |

Регрессионные guard (инженерный health, AUTO): **496 тестов зелёные** (без регрессий) · reflex export --frontend-only --no-zip exit 0 · py_compile OK · /health tests count синхронизирован (496).

## 3. ТОП-3 БЛОКЕРА (ранжировано)

1. **M7 settle-нога: нужен РЕАЛЬНЫЙ ПЛАТЁЖ** (~3000 sats, ~$0.30) — kill-окно ~6 дней (mint=0 ~24/30). Инвойс создаётся (invoice_ok=true), auto-verify тикает («⏳ 1/30»), settle→mint-запись→счётчик юнит-доказаны (test_mint_loop), счётчик переживает редеплои, volume смонтирован, лейблы/коппинг больше не путают сумму. → **Действие владельца (2 мин)**: открыть бота @terrramonBot в Telegram → призвать свежее существо → на карточке Care нажать «⚡ Mint via Lightning · 3000 sats» → оплатить инвойс (WebLN/Alby или QR/скопированный BOLT11). После платежа mint_count станет 1 → MintLoop=1 → **NSS 100/100**.
2. **Нет реальных игроков** (player_count:0, returning_players_7d:0) — M6/M8 и боевая формула NSS мертвы без людей. Код готов: deep link (?startapp=share_), share-карточка с 📍 в клипборде, D7-кохорта замеряется автоматически. → **Действие владельца**: BotFather → /setmenubutton → WebApp URL (публикация бота) + запуск охвата.
3. **M1 ждёт device-проверки**: headless-симуляция геолокации = 100% (map-url 50.0619, 19.9368), но человеческое место («Kraków, Polska» на карточке) на реальном устройстве не подтверждено (в headless карточка показывает гейт-баннер «Закрепи свою мысль на планете»). → **Действие владельца**: открыть бота на телефоне, разрешить геолокацию, призвать существо, проверить 📍 на карточке.

## 4. EVIDENCE

- KPI-прогон iter-22: 12/12 архетипов (failed_rounds: []), geo_ok 12/12 (map-url), OYE 12/12, `invoice_ok:true` + `auto_verify_seen:true` («⏳ Auto-checking payment… 1/30») + `mint_price_sats:15 (STARS)` + новое `lightning_price_sats` (реальная цена Lightning-кнопки), share_count 5→6 live (deep link + 📍 в клипборде), mint_count 0, data_persisted:true (volume примонтирован!), restored seed=40/share=5.
- Live-доказательство M6 (повторно): `share_deep_link:true`, `share_card_has_birthplace:true` («📍 Кра…»), `clipboard_read:true`, `share_delta:1` — серверный счётчик 5→6.
- Новый код (grep-верифицирован): `'⚡ MINT · ' + ... + ' Stars'` ×2, `def lightning_button_label` (f"⚡ Mint via Lightning · {lightning_mint_price(...)} sats"), `'📋 Copy BOLT11'` + `rx.set_clipboard(TerramonState.lightning_invoice)` + `def mark_invoice_copied`, `def _d7_from_records`/`def d7_cohort_stats`/`def days_since_last_mint` (json_memory), /health: `d7_eligible/d7_retained/d7_retention/days_since_last_mint/kill_condition{triggered}` (getattr-фолбэк на None при отсутствии метода — деградация честная).
- OSS-референсы iter-22: getalby/lightning-browser-extension (585★, активен 2026-08-05 — BOLT11-ясность: точная сумма + copy; паттерн РЕПЛИЦИРОВАН), mozharov/zapgram (5★, Telegram-нативный LN-кошелёк, активен 2026-08-12 — copy-paste BOLT11 = доминантный Telegram-UX; РЕПЛИЦИРОВАНО), maladeep/cohort-retention-rate-analysis-in-python (23★ — форма eligible/retained/rate; РЕПЛИЦИРОВАНА форма, AVOID: pandas/jupyter-тяжесть), litestream/tma.js — паттерны прошлых итераций. Единицы Telegram Stars (не sats) — из докстрингов кода mint_creature/buy_stars (официальный домен core.telegram.org из этой среды недоступен — честно).
- Ограничение честно: headless-геолокация = Playwright-симуляция (Kraków), НЕ устройство; place_name на карточке в headless = гейт-баннер (не «Kraków, Polska»); mint-проба никогда не платит и не кликает Stars-минт (фейковый mint_count на проде был бы подлогом); d7-поля = 0/None при отсутствии игроков, это отсутствие данных, а не «поломка».
