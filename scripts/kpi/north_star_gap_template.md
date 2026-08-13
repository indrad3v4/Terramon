# Terramon — North Star Gap Report (v3, win-centric) · {{DATE}}

Fingerprint: `{{FINGERPRINT}}` · Playwright/Chromium headless + TMA-mock · Target: {{URL}}

---

## 0. ВЕРДИКТ ДНЯ (TL;DR)

- **North Star Score: {{NSS}}/100** — формула v3: `60·min(complete_releases,1) + 25·Geo% + 15·ShareRate` (win-path = PAID complete release: final words + real geo, ритуал оплачен)
- Топ-3 блокера: **1) {{GAP1}} 2) {{GAP2}} 3) {{GAP3}}**
- Kill-condition монитор: share_rate {{SHARE_RATE}}% · mint {{MINT_TOTAL}} · days_mint_zero: {{DAYS_MINT_ZERO}}/30 → **{{KILL_STATUS}}**

## 1. NORTH STAR SCORE (v3, win-centric)

| Компонент | Вес | Сегодня | Значение |
|---|---|---|---|
| Win-path: PAID complete release (final words + real geo, ритуал оплачен) | 60 | **{{COMPLETE_RELEASES}}** | complete_releases из /health; 1 = 100% компонента |
| Geo% (якорь победы) | 25 | **{{GEO_SCORE}}** | доля существ с lat≠0 && lon≠0 (headless-сим, ждёт device) |
| ShareRate (share/seed) | 15 | **{{SHARE_SCORE}}** | share_count/seed_count |
| **ИТОГО** | 100 | **{{NSS}}/100** | |

Lore/MintLoop — ДИАГНОСТИКА (не NSS): M2 lore = {{OYE}} · M7 инвойс-нога {{INVOICE_STATUS}} · mint_count={{MINT_TOTAL}}.

## 2. ГЭП-ТАБЛИЦА (мост «инженерия → северная звезда»)

| # | Метрика | Что меряет | Сегодня | Цель | Гэп | Блокирует | Измерение |
|---|---|---|---|---|---|---|---|
| M1 | Geo% | доля существ с реальными координатами | {{GEO_PCT}}% | 100% | {{GEO_GAP}} | сам win (без якоря release не полный) | AUTO + **device** |
| M2 | Vision-lore | кнопка «Open your eyes» + рендер | {{OYE}} | 1 | {{OYE_GAP}} | эмоцию/арт | AUTO |
| M3 | Win-path (depth) | complete_releases: release с final words + real geo, ритуал ОПЛАЧЕН | {{COMPLETE_RELEASES}} | 1 (1 = 100%) | {{WIN_GAP}} | 60/100 NSS | AUTO + **платёж владельца** |
| M4 | Дубликаты | unique/total | {{UNIQ}}/{{TOTAL}} | 1.0 | {{DEDUP_GAP}} | экономику минта | AUTO |
| M5 | Фрикция | гейт/модалки | {{FRICTION}} | 0 | {{FRICTION_GAP}} | онбординг | AUTO |
| M6 | Share-funnel | share_count/seed_count | {{SHARE_RATE}}% | ≥2% (kill <2%) | {{SHARE_GAP}} | охват (kill-condition) | AUTO |
| M7 | Mint loop | mint_count / инвойс-нога | {{MINT_TOTAL}}; {{INVOICE_STATUS}} | ≥2% | {{MINT_GAP}} | метрику минта | AUTO + **платёж** |
| M8 | D7 retention | возврат на 7-й день | {{D7}} | кохортный бенчмарк | {{D7_GAP}} | 2-ю половину NSS | AUTO + **люди** |
| M9 | RitualPaid | monetised win-path: «⚡ Ритуал отпускания:» инвойс-маркер | {{RITUAL_STATUS}} | 1 | {{RITUAL_GAP}} | доказательство live-монетизации | AUTO (инвойс = доказательство; платёж — никогда) |

Регрессионные guard (AUTO): **{{TESTS}} тестов зелёные** (регрессий {{REGRESSIONS}}) · reflex export --frontend-only --no-zip {{EXPORT_STATUS}} · py_compile {{PYCOMPILE_STATUS}} · /health tests:{{HEALTH_TESTS}}.

## 3. ТОП-3 БЛОКЕРА (ранжировано)

1. **{{GAP1_DETAIL}}**
2. **{{GAP2_DETAIL}}**
3. **{{GAP3_DETAIL}}**

## 4. EVIDENCE

{{EVIDENCE}}
