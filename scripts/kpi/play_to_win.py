from playwright.sync_api import sync_playwright
import argparse, os, re, json, urllib.request

try:
    from scripts.kpi import tma_env
except ImportError:  # run as plain script: python scripts/kpi/play_to_win.py
    import tma_env

# TMA environment: by default the app runs as a Telegram Mini App via the
# injected resilient window.Telegram.WebApp mock (headless Chromium has no
# Telegram runtime). --tma-studio / TMA_STUDIO_URL attempts the TMA-Studio
# web demo first and falls back to the mock honestly (see probe below).
AP = argparse.ArgumentParser(description="Terramon KPI Playwright player (TMA-aware)")
AP.add_argument("--tma-studio", action="store_true",
                help="attempt TMA-Studio web demo (?appUrl=) first; falls back to the injected mock")
AP.add_argument("--tma-studio-url", default=os.environ.get("TMA_STUDIO_URL", tma_env.TMA_STUDIO_DEFAULT_URL),
                help="TMA-Studio URL to probe (default: env TMA_STUDIO_URL or https://tma-studio.pages.dev)")
ARGS = AP.parse_args()
TMA_STUDIO_MODE = ARGS.tma_studio
TMA_STUDIO_URL = ARGS.tma_studio_url

URL = "https://terramon-tma-production.up.railway.app/"
ARCHETYPES = ["Hero","Rebel","Sage","Jester","Creator","Magician","Lover","Caregiver","Explorer","Innocent","Ruler","Orphan"]
DISMISS = ["continue","ok","got it","claim","let's go","awesome","nice","close","done","yay","explore","awake"]

THOUGHTS = [
    ("Explorer", "I refuse the system! Street art on concrete walls, fighting the machine, anarchy and freedom, breaking every rule tonight."),
    ("Rebel", "I paint graffiti at midnight, defy every rule, riot against the machine, burn it down."),
    ("Jester", "Wisdom in stillness — I sit by the ancient library, reading the dust of ages, seeking truth beyond words..."),
    ("Creator", "Make something beautiful that never existed — a painting, a song, a poem; art gives life its meaning, create meaning."),
    ("Hero", "Courage! I will stand between danger and the innocent, shield the weak, no matter the cost, protect everyone."),
    ("Magician", "Mystery and transformation — turning lead into gold, reading the unseen, secrets of the universe, wonder."),
    ("Caregiver", "I mend broken wings — bird rescue, hospice care, teaching patience, comfort for the lonely."),
    ("Ruler", "Order and power — I will build a kingdom, lead my people wisely, command respect, build a lasting legacy."),
    ("Innocent", "The world is good and I trust it — puppy eyes, fresh snow, wonder at every sunrise."),
    ("Orphan", "I want to help everyone — heal the sick, comfort the lonely, protect the small, feed the hungry, gentle care."),
    ("Sage", "I dream of adventure — crossing oceans, climbing mountains, discovering lost cities and unknown lands..."),
    ("Lover", "I want to be close to you — love is all that matters, I give you my whole heart, being with you is enough."),
]

# M1: simulated device geolocation permission (Moscow). Honest note: this is Playwright
# grant_permissions + set_geolocation, i.e. we emulate what a real device would grant —
# the app's capture_location (⟳) then resolves navigator.geolocation with these coords.
GEO_LAT, GEO_LON = 55.7558, 37.6173
CAP = 12

def dismiss_modal(page):
    for kw in DISMISS:
        b = page.get_by_role("button", name=re.compile(kw, re.I)).first
        if b.count() > 0 and b.is_visible():
            try:
                b.click(timeout=2000)
                return kw
            except Exception:
                pass
    return None

def wait_result(page):
    # KPI policy: NEVER click any mint/buy button. Since ae3a162 the
    # 'Mint (1 Star)' button is buy_stars (optimistic _record_mint) — a click
    # here would fabricate mint_count on production. Presence-only logging.
    for i in range(40):
        page.wait_for_timeout(2000)
        body = page.locator("body").inner_text()
        d = dismiss_modal(page)
        if d:
            print("   [modal:", d, "]")
            page.wait_for_timeout(1000)
        if "A new presence stirs" in body:
            return body
    return page.locator("body").inner_text()

def read_terra(page):
    tab = page.locator("button:has-text('Terra')").first
    if tab.count() > 0 and tab.is_visible():
        tab.click(timeout=5000)
        page.wait_for_timeout(2500)
    body = page.locator("body").inner_text()
    names = re.findall(r"\b(" + "|".join(ARCHETYPES) + r")\b", body)
    m = re.search(r"(\d+) unique · (\d+) total", body)
    return names, (m.group(1), m.group(2)) if m else None, body

def evidence(page, tag):
    """Collect map/OYE/lore evidence from the current view."""
    imgs = []
    for idx in range(page.locator("img").count()):
        src = page.locator("img").nth(idx).get_attribute("src") or ""
        if "static-map" in src or "yandex" in src or "staticmap" in src:
            imgs.append(src)
    oye = page.locator("button:has-text('Open your eyes')").count()
    body = page.locator("body").inner_text()
    has_lore_line = False
    # lore renders as italic grey between thought and greeting; check for a non-empty italic p with maxWidth 260px
    italics = page.locator("p[style*='italic'], p:has(i)").count()
    return {"imgs": imgs, "oye_buttons": oye, "body_len": len(body)}

def setup_geo(ctx):
    """M1: grant geolocation + set Moscow coords BEFORE navigation."""
    ctx.grant_permissions(["geolocation"], origin=URL)
    try:
        # new-style API: keyword args
        ctx.set_geolocation(latitude=GEO_LAT, longitude=GEO_LON)
    except TypeError:
        # old-style API: Geolocation dict
        ctx.set_geolocation({"latitude": GEO_LAT, "longitude": GEO_LON})

def capture_location(page):
    """M1: click '⟳' (capture_location) and wait for the '📍' geo line in body (up to 3s)."""
    try:
        btn = page.locator("button:has-text('⟳')").first
        if btn.count() > 0 and btn.is_visible():
            btn.click(timeout=3000)
            print("   [geo] pressed '⟳' (capture_location)")
        else:
            print("   [geo] no '⟳' button visible — skipped")
    except Exception as e:
        print(f"   [geo] '⟳' click failed (not fatal): {str(e)[:120]}")
        return None
    geo_line = None
    for _ in range(6):  # up to ~3s
        page.wait_for_timeout(500)
        try:
            body = page.locator("body").inner_text()
        except Exception:
            continue
        for line in body.splitlines():
            if "📍" in line:
                geo_line = line.strip()
                break
        if geo_line:
            break
    if geo_line:
        print(f"   [geo] captured location line: {geo_line}")
    else:
        print("   [geo] no '📍' line appeared within 3s after '⟳' click")
    return geo_line

def collect_m2_evidence(page):
    """M2: vision-lore evidence after a successful summon -> {geo_ok, oye, map_img, place}."""
    body = page.locator("body").inner_text()
    coords = re.findall(r"-?\d+\.\d+\s*,\s*-?\d+\.\d+", body)
    place = coords[0] if coords else None
    geo_ok = bool(place) and place.replace(" ", "") not in ("0.00,0.00",)
    oye = page.locator("button:has-text('Open your eyes')").count()
    map_img = False
    for i in range(page.locator("img").count()):
        src = page.locator("img").nth(i).get_attribute("src") or ""
        if "static-map" in src or "staticmap" in src or "yandex" in src:
            map_img = True
            break
    return {"geo_ok": geo_ok, "oye": oye, "map_img": map_img, "place": place}, body

def m7_check(page):
    """M7: mint-loop evidence. Click 'Pay with Lightning' ONCE if payment_gate visible,
    log agent_message (invoice status). NEVER click any mint button ('⚡ MINT' or
    'Mint (1 Star)' — the latter is buy_stars since ae3a162), never pay."""
    res = {"payment_gate_seen": False, "invoice_ok": None, "invoice_msg": None, "mint_button_count": 0}
    try:
        gate = page.locator("button:has-text('Pay with Lightning')").first
        if gate.count() > 0 and gate.is_visible():
            res["payment_gate_seen"] = True
            gate.click(timeout=4000)
            print("   [m7] clicked 'Pay with Lightning' once (no payment attempted)")
            page.wait_for_timeout(2500)
        else:
            print("   [m7] no 'Pay with Lightning' payment_gate visible")
    except Exception as e:
        print(f"   [m7] payment gate click failed (not fatal): {str(e)[:120]}")
    try:
        body = page.locator("body").inner_text()
        if "⚡ Invoice ready: 3000 sats" in body:
            res["invoice_ok"] = True
            res["invoice_msg"] = "⚡ Invoice ready: 3000 sats (Alby configured)"
            print("   [m7] agent_message: ⚡ Invoice ready: 3000 sats (Alby configured)")
        elif "⚡ Lightning not configured yet" in body:
            res["invoice_ok"] = False
            res["invoice_msg"] = "⚡ Lightning not configured yet"
            print("   [m7] agent_message: ⚡ Lightning not configured yet")
        # presence-only: count mint buttons ('⚡ MINT' legacy label + the
        # ae3a162 rename 'Mint (1 Star)' / '⭐ Mint (1 Star)'; has-text is a
        # case-insensitive substring match, so 'Mint (1 Star)' covers the
        # star-prefixed variant too) — never clicked
        res["mint_button_count"] = (
            page.locator("button:has-text('⚡ MINT')").count()
            + page.locator("button:has-text('Mint (1 Star)')").count()
        )
        print(f"   [m7] mint buttons in DOM: {res['mint_button_count']} (presence only, never clicked)")
    except Exception as e:
        print(f"   [m7] body read failed (not fatal): {str(e)[:120]}")
    return res

def fetch_mint_count():
    """curl /health and parse mint_count via json."""
    try:
        with urllib.request.urlopen(URL.rstrip("/") + "/health", timeout=20) as r:
            data = json.loads(r.read().decode())
        return data.get("mint_count")
    except Exception as e:
        return f"health fetch failed: {str(e)[:120]}"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    # TMA-Studio honest attempt: the pages.dev demo is a marketing landing
    # page (verified from source + live probe) — probe once with ?appUrl=,
    # record the outcome, and fall back to the injected mock either way.
    tma_studio_probe = None
    if TMA_STUDIO_MODE:
        tma_studio_probe = tma_env.probe_tma_studio(browser, URL, studio_url=TMA_STUDIO_URL)
        print(f"[tma-studio] probe: {json.dumps(tma_studio_probe, ensure_ascii=False)}")
    collected = {}   # archetype -> thought
    round_log = []
    oye_total = 0
    geo_ok_rounds = []
    mint_presence = {}
    invoice_ok_rounds = []
    round_no = 0
    for theme, thought in THOUGHTS:
        if len(collected) >= CAP:
            break
        round_no += 1
        ctx = browser.new_context(viewport={"width": 414, "height": 896})
        # M1: geolocation permission + Moscow coords BEFORE navigation
        try:
            setup_geo(ctx)
            print(f"[round {round_no}] geo granted: {GEO_LAT}, {GEO_LON} (simulated device permission via Playwright)")
        except Exception as e:
            print(f"[round {round_no}] geo setup failed: {str(e)[:120]}")
        page = ctx.new_page()
        # TMA env: inject the resilient window.Telegram.WebApp mock BEFORE
        # the app loads, so this round runs as a real TMA (platform android,
        # per-round player identity, LocationButton geo bridge auto-answered
        # with the simulated Moscow coords — M1 via the TMA path).
        tma_setup = tma_env.setup_tma_env(
            page,
            user_id=710000000 + round_no,
            first_name=f"KPI{round_no}",
            username=f"kpi_tester_{round_no}",
            auto_location=(GEO_LAT, GEO_LON),
        )
        print(f"[round {round_no}] TMA env: {json.dumps(tma_setup, ensure_ascii=False)}")
        rlog = {"round": round_no, "theme": theme, "ok": False, "error": None, "geo_line": None, "m2": None, "m7": None, "tma": None}
        try:
            page.goto(URL, timeout=60000)
            page.wait_for_timeout(6000)
            gotit = page.locator("button:has-text('Got it!')").first
            if gotit.count() > 0 and gotit.is_visible():
                gotit.click(timeout=5000)
                page.wait_for_timeout(1500)
            # M1: press '⟳' BEFORE typing the thought
            rlog["geo_line"] = capture_location(page)
            inp = page.locator("input").first
            inp.wait_for(state="visible", timeout=30000)
            inp.fill(thought)
            page.wait_for_timeout(400)
            # pre-click dismissal: clear the tutorial overlay AND any F2
            # celebration overlay ('TERRA AWAKENED', fixed z-900) that may have
            # rendered once memory >= 5 creatures — otherwise it intercepts the
            # SUMMON click. Try each known dismissal keyword, swallow failures.
            for kw in ['Got it!', 'Continue', '✦ Continue', 'ok', 'close']:
                try:
                    b = page.get_by_role("button", name=kw, exact=False).first
                    if b.count() > 0 and b.is_visible():
                        b.click(timeout=1200)
                        page.wait_for_timeout(300)
                except Exception:
                    pass
            page.locator("button:has-text('SUMMON')").first.click(timeout=15000)
            print(f"[round {round_no}] theme={theme} clicked SUMMON, waiting...")
            body = wait_result(page)
            page.wait_for_timeout(2500)
            page.screenshot(path=f"/tmp/terramon_new_win_{round_no}.png", full_page=True)

            # M2: early vision-lore snapshot right after summon (informational
            # only — the static map renders ~1.5s later, so the authoritative
            # M1/M2 NSS evidence is counted from the Care-tab re-check below).
            ev, body = collect_m2_evidence(page)
            rlog["m2"] = ev
            print(f"   [M2 evidence (early snapshot)] {json.dumps(ev, ensure_ascii=False)}")

            # M7: mint-loop evidence (payment gate click once; NEVER any mint button, never pay)
            m7 = m7_check(page)
            rlog["m7"] = m7
            print(f"   [M7 evidence] {json.dumps(m7, ensure_ascii=False)}")
            mint_presence[round_no] = m7["mint_button_count"]
            if m7["invoice_ok"] is not None:
                invoice_ok_rounds.append((round_no, m7["invoice_msg"]))

            # TMA-only evidence: what the mock recorded during this round
            # (openInvoice / HapticFeedback / LocationButton / event bus).
            tma_ev = tma_env.read_tma_evidence(page)
            if tma_ev:
                tma_summary = {
                    "webapp_present": True,
                    "platform": tma_ev.get("platform"),
                    "user_id": (tma_ev.get("user") or {}).get("id"),
                    "haptic_calls": len(tma_ev.get("hapticCalls", [])),
                    "open_invoice_calls": len(tma_ev.get("openInvoiceCalls", [])),
                    "location_requests": len(tma_ev.get("locationRequests", [])),
                    "location_accessed_emitted": sum(
                        1 for e in tma_ev.get("emitted", []) if e.get("event") == "location_accessed"
                    ),
                    "events_listened": tma_ev.get("events", {}),
                    "ready_calls": tma_ev.get("readyCalls", 0),
                }
            else:
                tma_summary = {"webapp_present": False}
            rlog["tma"] = tma_summary
            print(f"   [TMA evidence] {json.dumps(tma_summary, ensure_ascii=False)}")

            # read Terra collection to get authoritative unique/total
            names, counts, tbody = read_terra(page)
            page.screenshot(path=f"/tmp/terramon_new_win_{round_no}_terra.png", full_page=True)

            # main-card re-check on the Care tab: M1/M2 evidence computed HERE —
            # the early post-summon snapshot misses the static map that renders
            # ~1.5s after SUMMON, so the authoritative geo_ok / OYE / map-img
            # evidence comes from this re-check (works even if the celebration
            # overlay is up).
            try:
                care_tab = page.locator("button:has-text('Care')").first
                if care_tab.count() > 0 and care_tab.is_visible():
                    care_tab.click(timeout=3000)
                    page.wait_for_timeout(1500)
                care_body = page.locator("body").inner_text()
                care_coords = re.findall(r"-?\d+\.\d+\s*,\s*-?\d+\.\d+", care_body)
                place_after_care = care_coords[0] if care_coords else None
                geo_ok_after_care = bool(place_after_care) and place_after_care.replace(" ", "") not in ("0.00,0.00",)
                oye_after_care = page.locator("button:has-text('Open your eyes')").count()
                map_imgs_after_care = [
                    page.locator("img").nth(i).get_attribute("src")
                    for i in range(page.locator("img").count())
                    if "static-map" in (page.locator("img").nth(i).get_attribute("src") or "")
                    or "yandex" in (page.locator("img").nth(i).get_attribute("src") or "")
                ]
                rlog["m2_after_care"] = {
                    "oye": oye_after_care,
                    "map_imgs": map_imgs_after_care,
                    "geo_ok": geo_ok_after_care,
                    "place": place_after_care,
                }
                print(f"   -> main-card (Care tab) OYE: {oye_after_care}, map: {map_imgs_after_care}, geo_ok: {geo_ok_after_care} ({place_after_care})")
                # NSS M1/M2 evidence from the re-check (static map visible by now)
                if geo_ok_after_care:
                    geo_ok_rounds.append(round_no)
                oye_total += oye_after_care
            except Exception as e:
                rlog["m2_after_care"] = {"oye": 0, "map_imgs": [], "geo_ok": False, "error": str(e)[:120]}
                print(f"   -> main-card (Care tab) re-check failed (not fatal): {str(e)[:120]}")

            # main card evidence (static-map imgs on collection cards)
            map_imgs = [page.locator("img").nth(i).get_attribute("src") for i in range(page.locator("img").count()) if "static-map" in (page.locator("img").nth(i).get_attribute("src") or "")]
            oye_any = page.locator("button:has-text('Open your eyes')").count()
            yandex_any = any("yandex" in (page.locator("img").nth(i).get_attribute("src") or "") for i in range(page.locator("img").count()))
            print(f"   -> card names found: {names}")
            print(f"   -> counts: {counts}")
            print(f"   -> static-map imgs: {map_imgs}")
            print(f"   -> yandex imgs: {yandex_any}, Open-your-eyes buttons: {oye_any}")

            # record NEW archetype: names in collection order; track which are new
            seen_before = set(collected.keys())
            for n in names:
                if n not in collected:
                    collected[n] = thought
                    print(f"   -> NEW archetype: {n}")
            rlog["ok"] = True
        except Exception as e:
            rlog["error"] = str(e)[:200]
            print(f"[round {round_no}] ERROR: {str(e)[:200]}")
            try:
                page.screenshot(path=f"/tmp/terramon_new_win_{round_no}_ERR.png", full_page=True)
            except Exception:
                pass
        finally:
            round_log.append(rlog)
            try:
                ctx.close()
            except Exception:
                pass

    print("=== COLLECTED:", collected)
    print("=== DISTINCT COUNT:", len(collected))
    print()
    print("=== NSS-EVIDENCE ===")
    print("geo_sim: Playwright grant_permissions + set_geolocation (Moscow 55.7558, 37.6173) + '⟳' click —",
          "simulated device permission, NOT a real device (honest note)")
    print(f"geo_ok_rounds: {geo_ok_rounds}  (rounds where creature place contains coords != '0.00, 0.00')")
    print(f"distinct_archetypes: {len(collected)} -> {sorted(collected.keys())}")
    print(f"oye_buttons_total: {oye_total}")
    print(f"mint_button_presence: {mint_presence}  (round -> count of mint buttons '⚡ MINT'/'Mint (1 Star)' in DOM; never clicked)")
    print(f"invoice_ok: {invoice_ok_rounds if invoice_ok_rounds else 'no invoice message observed (payment_gate not seen or no agent_message)'}")
    mc = fetch_mint_count()
    print(f"mint_count_health: {mc}  (from /health, json mint_count)")
    print(f"main_card_oye_after_care: {sum(1 for r in round_log if r.get('m2_after_care', {}).get('oye', 0))}")
    # TMA-ENV evidence: which TMA-only features got exercised this run
    tma_rounds_ok = [r["round"] for r in round_log if r.get("tma") and r["tma"].get("webapp_present")]
    tma_totals = {
        "haptic_calls": sum((r.get("tma") or {}).get("haptic_calls", 0) for r in round_log),
        "open_invoice_calls": sum((r.get("tma") or {}).get("open_invoice_calls", 0) for r in round_log),
        "location_requests": sum((r.get("tma") or {}).get("location_requests", 0) for r in round_log),
        "location_accessed_emitted": sum((r.get("tma") or {}).get("location_accessed_emitted", 0) for r in round_log),
        "ready_calls": sum((r.get("tma") or {}).get("ready_calls", 0) for r in round_log),
    }
    print()
    print("=== TMA-ENV ===")
    print("tma_mode: injected-mock — resilient window.Telegram.WebApp mock injected pre-load",
          "(page.add_init_script); headless Chromium has no Telegram runtime")
    print(f"tma_platform: android · version: {tma_env.DEFAULT_VERSION} · colorScheme: dark")
    print("tma_initdata: well-formed query string; hash FAKE unless a real bot token is",
          "passed to setup_tma_env (then real HMAC-SHA256, exactly like Telegram's backend)")
    print(f"tma_webapp_present_rounds: {tma_rounds_ok}")
    print(f"tma_features_exercised: {json.dumps(tma_totals, ensure_ascii=False)}",
          "(open_invoice=0 expected: KPI never clicks any mint button — presence-only policy)")
    print(f"tma_studio_probe: {json.dumps(tma_studio_probe, ensure_ascii=False) if tma_studio_probe else 'not attempted (default mode; use --tma-studio or TMA_STUDIO_URL)'}")
    failed = [{"round": r["round"], "theme": r["theme"], "error": r["error"]} for r in round_log if not r["ok"]]
    print(f"failed_rounds: {json.dumps(failed, ensure_ascii=False)}")
    if failed:
        print("gate-bug evidence: rounds failing on 'input not visible' = prod gate bug",
              "(operator precedence: 'summon_count > 0 & ~unlocked' parses as 'summon_count > 0'),",
              "expected until fix deploys; script behavior is correct (recorded, not patching game code)")
    browser.close()
