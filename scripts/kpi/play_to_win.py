from playwright.sync_api import sync_playwright
import argparse, os, re, json, time, urllib.request, urllib.parse

try:
    from scripts.kpi import tma_env
except ImportError:  # run as plain script: python scripts/kpi/play_to_win.py
    import tma_env

# TMA environment: by default the app runs as a Telegram Mini App via the
# injected resilient window.Telegram.WebApp mock (headless Chromium has no
# Telegram runtime). --tma-studio / TMA_STUDIO_URL attempts the TMA-Studio
# web demo first and falls back to the mock honestly (see probe below).
# Depth-win release probe (Lens #97 reframe): after the mint probes,
# run_depth_release_probe() performs ONE full release ritual on prod —
# fresh player -> summon run-unique English thought -> Care tab ->
# 2x '✦ EVOLVE' (stage 2) -> '💨 Отпустить' dialog with final words +
# real geo — proving the depth win-path is reachable. Honest note: the
# probe creates exactly ONE real released seed (status='released' +
# final_words + lat/lon) on prod per run; /health complete_releases is
# the authoritative 0->1 signal (1 complete release = 100% of the win).
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

# M1: simulated device geolocation permission (Kraków). Honest note: this is Playwright
# grant_permissions + set_geolocation, i.e. we emulate what a real device would grant —
# the app's capture_location (⟳) then resolves navigator.geolocation with these coords.
GEO_LAT, GEO_LON = 50.0619, 19.9368
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
    """M1: grant geolocation + set Kraków coords BEFORE navigation."""
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

def place_name_from_body(body):
    """M1 geo evidence: the human place name on the creature card's 📍 line.

    The app renders the geo line as the HUMAN place name ('Kraków,
    Polska' style — TerramonState.place from GeoContext), not raw
    coords, so the coords regex in collect_m2_evidence returns None
    for it (see the note in geo_ok_from_map_url). Return the text
    after the 📍 emoji on the first matching body line (falling back
    to the next non-empty line when the emoji and the name render as
    separate rx.text nodes in the hstack), else a known place-name
    pattern ('City, Country'), else None.
    """
    if not body:
        return None
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if "📍" in line:
            rest = line.split("📍", 1)[1].strip()
            if not rest and i + 1 < len(lines):
                rest = lines[i + 1].strip()
            if rest:
                return rest
    m = re.search(
        r"\b[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:[- ][A-ZĄĆĘŁŃÓŚŹŻ]?[a-ząćęłńóśźż]+)*,\s+[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+",
        body,
    )
    return m.group(0) if m else None

def collect_m2_evidence(page):
    """M2: vision-lore evidence after a successful summon -> {geo_ok, oye, map_img, place, place_name}."""
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
    return {"geo_ok": geo_ok, "oye": oye, "map_img": map_img, "place": place,
            "place_name": place_name_from_body(body)}, body

def geo_ok_from_map_url(srcs):
    """M1 geo evidence from the static-map <img> URL (authoritative): True if any
    src is a static-map URL whose lat AND lon query params are both non-zero.
    The UI shows a human place_name ('Kraków, Poland' style), so the body-text
    coords regex in collect_m2_evidence finds nothing — but the seed persisted
    REAL lat/lon, proven by static_map_url() returning '' when agent_lat/lon are
    0 and a real coords URL (lat/lon query params) otherwise."""
    for src in srcs or []:
        if not src or "static-map" not in src:
            continue
        try:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(src).query)
            lat = qs.get("lat", ["0"])[0]
            lon = qs.get("lon", ["0"])[0]
            if float(lat) != 0.0 and float(lon) != 0.0:
                return True
        except (ValueError, TypeError, IndexError):
            continue
    return False

def m7_check(page):
    """M7: mint-loop evidence (per round, presence-only).

    The creature-card MINT area ('⚡ MINT · N Stars' + '⚡ Mint via Lightning')
    renders only on a FRESH summon where price_sats > 0 AND can_mint
    (Bayesian max posterior > 0.5, computed only on a fresh summon). All 12
    THOUGHTS are already seeded on prod, so every round here hits the dedup
    guard (find_seed -> _present_existing_creature), which sets price_sats
    from the seed but NEVER can_mint — the mint button is hidden by design
    on this path ('locked · train more'). Record what the MINT area shows;
    NEVER click any mint button that creates a mint record ('⚡ MINT ·' /
    'Mint (1 Star)' — the latter is buy_stars since ae3a162 and would
    fabricate mint_count on prod), never '✅ I've paid — verify', never pay.
    The REAL mint loop is probed by the post-loop run_m7_mint_probe with a
    run-unique fresh summon (up to 3 English candidate attempts).
    """
    res = {"mint_button_presence": False, "mint_ui_state": None}
    try:
        body = page.locator("body").inner_text()
        res["mint_button_presence"] = "⚡ MINT ·" in body
        res["mint_ui_state"] = mint_ui_state_from_body(body)
        print(f"   [m7] MINT area: presence={res['mint_button_presence']}, ui_state={res['mint_ui_state']}  (presence only, never clicked)")
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

def fetch_health_full():
    """curl /health once and return the FULL parsed json dict, including the
    durability fields (data_restored_from_snapshot, restored_seed_count,
    restored_mint_count, restored_share_count, snapshot_ts). {} on failure —
    non-fatal by design; callers report exactly what /health actually says."""
    try:
        with urllib.request.urlopen(URL.rstrip("/") + "/health", timeout=20) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"   [health] /health full fetch failed (not fatal): {str(e)[:120]}")
        return {}

# M7 mint-loop probe candidates (post-loop, tried in order): the three
# THOUGHTS that rendered 'mint visible' on prod in the iter-13 run.
# ENGLISH IS REQUIRED — the game's EmbeddingClassifier
# (terramon/adapters/embedding_classifier.py) is an English-keyword TF-IDF
# model whose tokenizer regex [a-z']+ drops Cyrillic (and digits), so a
# Russian thought yields near-zero tokens -> near-zero likelihood ->
# Bayesian max posterior far below the 0.5 gate (iter-13 measured ~0.083
# for the Russian probe thought) -> can_mint=False -> mint area hidden
# ('locked · train more') -> no invoice. The Lover thought has the
# strongest likelihood margin (top_like=1.489, margin 0.349 vs under 0.04
# for all others); Magician and Caregiver also passed the gate on prod
# this run.
M7_PROBE_CANDIDATES = [
    ("Lover", "I want to be close to you — love is all that matters, I give you my whole heart, being with you is enough."),
    ("Magician", "Mystery and transformation — turning lead into gold, reading the unseen, secrets of the universe, wonder."),
    ("Caregiver", "I mend broken wings — bird rescue, hospice care, teaching patience, comfort for the lonely."),
]

def probe_thought(base_text=None):
    """Run-unique ENGLISH summon thought for the post-loop M7 mint probe.

    Defaults to the Lover thought — the one candidate with a strong
    likelihood margin (top_like=1.489, margin 0.349 vs under 0.04 for all
    others), so the first probe attempt has the best chance of passing the
    can_mint gate. A millisecond epoch timestamp suffix keeps every probe
    thought run-unique: digits are dropped by the classifier's tokenizer
    (regex [a-z']+), so the TF-IDF tokens stay identical -> same high
    likelihood, while raw_input is unique so the exact-string dedup guard
    (find_seed -> _present_existing_creature) NEVER matches -> a REAL
    fresh summon happens and can_mint (Bayesian max posterior > 0.5) is
    actually computed — the only path where the creature-card MINT area
    renders. English is REQUIRED: the classifier is English-keyword TF-IDF
    (tokenizer regex [a-z']+ drops Cyrillic), so Russian thoughts never
    reach can_mint (iter-13: 'мысль странника ...' -> near-zero likelihood
    -> max posterior ~0.083 -> mint area hidden). Honest note: up to 3
    probe seeds per run (one per candidate attempt) are created on prod
    (probe_seed_created flag stays per attempt), acceptable and expected.
    """
    if base_text is None:
        base_text = M7_PROBE_CANDIDATES[0][1]
    return f"{base_text} {int(time.time() * 1000)}"

def parse_invoice_status(body):
    """Parse the pay_lightning agent_message markers from body text.

    pay_lightning() (terramon_tma.py) sets exactly these agent_message
    markers: Alby Hub configured -> '⚡ Invoice ready', not configured ->
    '⚡ Lightning not configured yet', exception -> '⚡ Invoice failed'.
    Returns (invoice_ok, invoice_msg): True for '⚡ Invoice ready', False
    for the two failure markers, (None, None) when no marker is present.
    """
    for marker, ok in (("⚡ Invoice ready", True),
                       ("⚡ Lightning not configured yet", False),
                       ("⚡ Invoice failed", False)):
        if marker in body:
            return ok, marker
    return None, None

def mint_ui_state_from_body(body):
    """Classify the creature-card MINT area from body text.

    'mint visible' -> '⚡ MINT · N Stars' rendered (price_sats > 0 AND
        can_mint — fresh-summon path only);
    'locked · train more' -> creature present but can_mint=False (dedup
        path: _present_existing_creature sets price_sats from the seed but
        never can_mint);
    'free summon' -> no creature on the card yet (fresh visitor);
    'unknown' -> none of the above (no creature card in the body).
    """
    if "⚡ MINT ·" in body:
        return "mint visible"
    if "locked · train more" in body:
        return "locked · train more"
    if "free summon" in body:
        return "free summon"
    return "unknown"

def fetch_share_count():
    """curl /health and parse share_count (M6 server-side share counter).

    share_creature() records EVERY share attempt on the persisted share
    registry (JsonMemory.record_share) BEFORE the clipboard write, so the
    /health share_count delta is the authoritative M6 signal — clipboard
    exceptions in headless Chromium are non-fatal.
    """
    try:
        with urllib.request.urlopen(URL.rstrip("/") + "/health", timeout=20) as r:
            data = json.loads(r.read().decode())
        return data.get("share_count")
    except Exception as e:
        return f"health fetch failed: {str(e)[:120]}"

def fetch_alby_configured():
    """curl /health and parse the 'alby_configured' json field (M7: whether
    Alby Hub is configured on prod — the Lightning invoice backend of the
    mint loop; the invoice-creation probe's outcome is cross-checked against
    it)."""
    try:
        with urllib.request.urlopen(URL.rstrip("/") + "/health", timeout=20) as r:
            data = json.loads(r.read().decode())
        return data.get("alby_configured")
    except Exception as e:
        return f"health fetch failed: {str(e)[:120]}"

def _button_is_covered(page, locator):
    """True when another element paints over the button's center (hit-target).

    Mirrors Playwright's actionability hit-target check: at the button's
    bounding-box center, document.elementFromPoint must resolve to the
    button itself or one of its descendants. On prod there are TWO
    '⚡ Mint via Lightning' buttons: the home compact card's (always
    rendered, but its button is COVERED by the thought input element in the
    fixed-height no-scroll layout — elementFromPoint at its center returns
    the INPUT, which is not inside the button) and the Care-panel button
    (center resolves to the BUTTON itself). Any evaluation error -> False
    (never block the probe).
    """
    try:
        return page.evaluate(
            """(btn) => {
                const r = btn.getBoundingClientRect();
                if (!r || r.width === 0 || r.height === 0) return false;
                const el = document.elementFromPoint(
                    r.left + r.width / 2, r.top + r.height / 2);
                if (!el) return true;  // nothing at the center -> covered
                return !(el === btn || btn.contains(el));
            }""",
            locator.element_handle(),
        )
    except Exception:
        return False

# M6: once-per-session share-probe gate. The probe clicks '📤 Share'
# EXACTLY ONCE per session — whichever path fires first wins: the in-loop
# path (round with has_summoned=True) or the post-loop M7 probe path (the
# guaranteed fresh summon, when all 12 archetypes are already seeded on
# prod so the in-loop gate never fires). Module-level so both the round
# loop (module scope) and run_m7_mint_probe can read/set it.
M6_SHARE_PROBE_DONE = False

def run_share_probe(page, ctx, share_count_before, probe_label="m6-share-probe") -> dict:
    """M6 share probe: click '📤 Share' EXACTLY ONCE on the live creature
    card's Care tab and read the deep-link card back from the clipboard.

    share_creature() records EVERY share attempt on the persisted share
    registry (JsonMemory.record_share) BEFORE the clipboard write, so the
    /health share_count delta is the authoritative M6 signal — clipboard
    exceptions in headless Chromium are caught and logged (non-fatal);
    the server-side counter is what matters. Safe to call on a page whose
    Care tab is already active (the share button lives on the Care tab of
    a live creature card); never raises — always returns the share_probe
    dict.
    """
    share_probe = {"share_before": share_count_before, "share_after": None,
                   "share_delta": None, "share_clicked": False,
                   "clipboard_error": None, "clipboard_read": False,
                   "share_deep_link": False, "share_link_in_text": False,
                   "share_card_has_birthplace": False,
                   "share_card_text_snippet": ""}
    try:
        share_btn = page.locator("button:has-text('📤 Share')").first
        if share_btn.count() > 0 and share_btn.is_visible():
            # M6 clipboard permissions: the share card is written to the
            # CLIPBOARD via rx.set_clipboard (share_creature) — the deep
            # link + 📍 birthplace never enter the DOM. Grant clipboard
            # access on the context BEFORE the click so
            # navigator.clipboard.readText() works. Non-fatal: headless
            # Chromium may refuse clipboard-write; grant at least
            # clipboard-read.
            try:
                ctx.grant_permissions(
                    ["clipboard-read", "clipboard-write"],
                    origin=page.url.split("?")[0] if page.url else None,
                )
            except Exception as e:
                try:
                    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
                except Exception as e2:
                    print(f"   [{probe_label}] clipboard permission grant failed (not fatal): {str(e2)[:120]}")
            share_btn.click(timeout=4000)
            share_probe["share_clicked"] = True
            print(f"   [{probe_label}] clicked '📤 Share' once")
            page.wait_for_timeout(2500)
            # M6 deep-link evidence: the iter-18 share card renders the
            # Telegram deep link (link emoji + 'https://t.me/...' +
            # '?startapp=share_' + share_code) and a 📍 birthplace line.
            # The REAL card lives in the CLIPBOARD (share_creature ->
            # rx.set_clipboard) — read it back; on any clipboard
            # failure/empty read, fall back to the DOM scan. Reads are
            # non-fatal — on any failure the initialized defaults
            # (False/"") stay in share_probe.
            clipboard_text = None
            try:
                # headless Chromium: readText() needs the page focused +
                # the ClipboardReadWrite feature flag (added at launch).
                try:
                    page.bring_to_front()
                except Exception:
                    pass
                clipboard_text = page.evaluate("() => navigator.clipboard.readText()")
                share_probe["clipboard_read"] = True
                share_probe["clipboard_error"] = None
            except Exception as e:
                share_probe["clipboard_read"] = False
                share_probe["clipboard_error"] = str(e)[:120]
                print(f"   [{probe_label}] clipboard read failed (not fatal): {str(e)[:120]}")
            if clipboard_text:
                share_probe["share_deep_link"] = "startapp=share_" in clipboard_text
                share_probe["share_card_has_birthplace"] = "📍" in clipboard_text
                share_probe["share_card_text_snippet"] = re.sub(r"\s+", " ", clipboard_text).strip()[:200]
                print(f"   [{probe_label}] deep-link evidence read from the clipboard card")
            else:
                # Fallback: DOM scan (iter-18+ keeps the card in the
                # clipboard only, but older deploys may render it in the
                # body). locator.all() is Playwright's documented API for
                # iterating matches — Locator objects are NOT iterable.
                body_text = page.locator("body").inner_text()
                hrefs = [a.get_attribute("href") for a in page.locator("a[href*='t.me']").all()]
                share_probe["share_deep_link"] = any(h and "startapp=share_" in h for h in hrefs)
                share_probe["share_link_in_text"] = "startapp=share_" in body_text
                share_probe["share_card_has_birthplace"] = "📍" in body_text
                share_probe["share_card_text_snippet"] = re.sub(r"\s+", " ", body_text).strip()[:200]
        else:
            print(f"   [{probe_label}] no '📤 Share' button visible on Care tab")
    except Exception as e:
        share_probe["clipboard_error"] = str(e)[:120]
        print(f"   [{probe_label}] share click failed (not fatal): {str(e)[:120]}")
    share_probe["share_after"] = fetch_share_count()
    if isinstance(share_probe["share_before"], int) and isinstance(share_probe["share_after"], int):
        share_probe["share_delta"] = share_probe["share_after"] - share_probe["share_before"]
    return share_probe

def run_m7_mint_probe(browser, thought, candidate_label="probe"):
    """M7 mint-loop invoice probe: summon `thought` in a fresh context and,
    IF the creature-card MINT area renders, click '⚡ Mint via Lightning'
    EXACTLY ONCE.

    The thought is run-unique (see probe_thought), so find_seed() never
    matches -> a REAL fresh summon happens where can_mint (Bayesian max
    posterior > 0.5, computed from the GLOBAL belief prior load_belief()
    player_id='default', data/beliefs.jsonl) is actually evaluated. The
    MINT area ('⚡ MINT · N Stars' + '⚡ Mint via Lightning') renders only
    when price_sats > 0 AND can_mint, and only on the Care tab. We click
    '⚡ Mint via Lightning' EXACTLY ONCE when it is visible — invoice
    creation ONLY: mint_lightning() (terramon_tma.py) creates an Alby Hub
    invoice and sets the '⚡ Invoice ready: N sats' agent_message; NO mint
    record is created (minting happens only on settle via verify_lightning
    -> _record_mint), so this is honest invoice-creation testing. KPI
    policy: NEVER click '⚡ MINT ·'/'Mint (1 Star)' (buy_stars / optimistic
    mint that would fabricate mint_count on prod), never '✅ I've paid —
    verify', never pay. Returns the m7_probe dict.
    """
    global M6_SHARE_PROBE_DONE
    m7_probe = {"probe_thought": thought, "probe_seed_created": False,
                "mint_button_presence": False, "mint_ui_state": None,
                "mint_price_sats": None, "lightning_price_sats": None,
                "mint_clicked": False, "invoice_ok": None, "invoice_msg": None,
                "auto_verify_seen": False, "auto_verify_marker": None,
                "alby_configured": None}
    probe_ctx = None
    try:
        probe_ctx = browser.new_context(viewport={"width": 414, "height": 896})
        setup_geo(probe_ctx)
        probe_page = probe_ctx.new_page()
        # TMA env: same injected-mock pattern as the rounds (distinct
        # player identity so the probe player starts with summon_count=0).
        tma_setup = tma_env.setup_tma_env(
            probe_page,
            user_id=709999999,
            first_name="KPIMintProbe",
            username="kpi_mint_probe",
            auto_location=(GEO_LAT, GEO_LON),
        )
        print(f"[m7-probe:{candidate_label}] TMA env: {json.dumps(tma_setup, ensure_ascii=False)}")
        probe_page.goto(URL, timeout=60000)
        probe_page.wait_for_timeout(6000)
        gotit = probe_page.locator("button:has-text('Got it!')").first
        if gotit.count() > 0 and gotit.is_visible():
            gotit.click(timeout=5000)
            probe_page.wait_for_timeout(1500)
        # M1: press '⟳' BEFORE typing the thought (same as the rounds)
        capture_location(probe_page)
        inp = probe_page.locator("input").first
        inp.wait_for(state="visible", timeout=30000)
        inp.fill(thought)
        probe_page.wait_for_timeout(400)
        for kw in ['Got it!', 'Continue', '✦ Continue', 'ok', 'close']:
            try:
                b = probe_page.get_by_role("button", name=kw, exact=False).first
                if b.count() > 0 and b.is_visible():
                    b.click(timeout=1200)
                    probe_page.wait_for_timeout(300)
            except Exception:
                pass
        probe_page.locator("button:has-text('SUMMON')").first.click(timeout=15000)
        print(f"[m7-probe:{candidate_label}] probe_thought={thought!r} clicked SUMMON, waiting...")
        probe_body = wait_result(probe_page)
        probe_page.wait_for_timeout(2500)
        if "A new presence stirs" in probe_body:
            m7_probe["probe_seed_created"] = True
        # The creature-card MINT area ('⚡ MINT · N Stars' + '⚡ Mint via
        # Lightning') renders ONLY when the bottom-nav Care tab is active
        # (active_tab == 'care'); right after a fresh summon the app is on
        # the Terra tab, so click the Care tab FIRST — otherwise the body
        # read below sees 'unknown' even when the mint area is live.
        try:
            probe_care_tab = probe_page.locator("button:has-text('Care')").first
            if probe_care_tab.count() > 0 and probe_care_tab.is_visible():
                probe_care_tab.click(timeout=4000)
                probe_page.wait_for_timeout(1500)
        except Exception as e:
            print(f"   [m7-probe:{candidate_label}] Care tab click failed (not fatal): {str(e)[:120]}")
        # MINT-area evidence on the fresh-summon card: presence-only check
        # of the REAL mint loop ('⚡ MINT · N Stars' renders only when
        # price_sats > 0 AND can_mint, computed on a fresh summon). Re-read
        # the body (the card may finish rendering after wait_result).
        mint_body = probe_page.locator("body").inner_text()
        m7_probe["mint_button_presence"] = "⚡ MINT ·" in mint_body
        m7_probe["mint_ui_state"] = mint_ui_state_from_body(mint_body)
        # Mint price: the live app renders the button label '⚡ MINT · N Stars'
        # (terramon_tma.py mint area) — parse N when the MINT area is visible
        # (price_sats > 0 AND can_mint); None when not found. Honest note: the
        # unit on the '⚡ MINT ·' button is STARS (Telegram Stars rail), NOT
        # sats — the field name mint_price_sats is kept for back-compat with
        # the NSS-EVIDENCE schema, but the value is the Stars price.
        mint_price_match = re.search(r"⚡\s*MINT\s*·\s*(\d+)\s*Stars?", mint_body, re.IGNORECASE)
        m7_probe["mint_price_sats"] = int(mint_price_match.group(1)) if mint_price_match else None
        # Lightning-button price: the '⚡ Mint via Lightning' button label now
        # also carries the REAL invoice price ('⚡ Mint via Lightning · N sats',
        # floor 3000 per LIGHTNING_MIN_MINT_SATS) — the price the user
        # actually sees and pays on the button. Parsed only when the MINT area
        # is live (the Lightning button renders only on that path); None
        # otherwise.
        if m7_probe["mint_button_presence"]:
            lightning_price_match = re.search(r"⚡ Mint via Lightning · (\d+) sats", mint_body)
            m7_probe["lightning_price_sats"] = int(lightning_price_match.group(1)) if lightning_price_match else None
        print(f"   [m7-probe:{candidate_label}] MINT area: presence={m7_probe['mint_button_presence']}, ui_state={m7_probe['mint_ui_state']}, mint_price_sats={m7_probe['mint_price_sats']} (STARS), lightning_price_sats={m7_probe['lightning_price_sats']} (sats)")
        # M6: share probe on the GUARANTEED fresh summon (post-loop path).
        # The in-loop share probe (gated on has_summoned) never fires when
        # all 12 archetypes are already seeded on prod — so run the share
        # probe HERE on the fresh-summon card instead, now that the Care
        # tab is active and the card is live (share button and mint button
        # live on the same Care-tab card). The once-per-session gate
        # M6_SHARE_PROBE_DONE guarantees '📤 Share' is clicked at most
        # once across the whole run — whichever path fires first wins.
        if not M6_SHARE_PROBE_DONE:
            m7_probe["m6_share_probe_postloop"] = run_share_probe(
                probe_page, probe_ctx, share_count_before,
                probe_label="m6-share-probe-postloop",
            )
            M6_SHARE_PROBE_DONE = True
        # IF the MINT area is live: click '⚡ Mint via Lightning' EXACTLY
        # ONCE — invoice creation only, no mint record is created (minting
        # happens only on settle via verify_lightning), same honest spirit
        # as the old probe, no payment. The agent_message markers are parsed
        # by parse_invoice_status below.
        if m7_probe["mint_button_presence"]:
            try:
                # TWO '⚡ Mint via Lightning' buttons can coexist in the DOM:
                # the home compact card (always rendered; its button is
                # COVERED by the thought input element in the fixed-height
                # no-scroll layout) and the Care-panel button (fully
                # clickable). Never blind-click .first — Playwright's
                # hit-target actionability check would timeout (4000ms) on
                # the covered home-card one. Click the FIRST match that is
                # visible AND whose bounding-box center hit-target resolves
                # to the button itself (elementFromPoint check in
                # _button_is_covered) — i.e. the Care-panel button.
                mint_btns = probe_page.locator("button:has-text('⚡ Mint via Lightning')")
                for i in range(mint_btns.count()):
                    mint_lightning_btn = mint_btns.nth(i)
                    if mint_lightning_btn.is_visible() and not _button_is_covered(probe_page, mint_lightning_btn):
                        mint_lightning_btn.click(timeout=4000)
                        m7_probe["mint_clicked"] = True
                        print(f"   [m7-probe:{candidate_label}] clicked '⚡ Mint via Lightning' once (match #{i} — visible and not covered; invoice creation only, no payment attempted)")
                        probe_page.wait_for_timeout(2500)
                        # Auto-verify poller window: iter-17 prod arms a hidden
                        # rx.moment poller (LIGHTNING_VERIFY_INTERVAL_MS = 6000)
                        # that fires verify_lightning() every 6s while
                        # lightning_auto_verify is True; the invoice panel shows
                        # '⏳ Auto-checking payment… N/30'. Wait ~4.5s more
                        # (~7s total after the click, > one 6s tick) so a live
                        # deploy has ticked at least once (N >= 1) before the
                        # marker read below.
                        probe_page.wait_for_timeout(4500)
                        break
                else:
                    print(f"   [m7-probe:{candidate_label}] '⚡ Mint via Lightning' present but no visible, uncovered button found (not fatal)")
            except Exception as e:
                print(f"   [m7-probe:{candidate_label}] '⚡ Mint via Lightning' click failed (not fatal): {str(e)[:120]}")
        # M6 share probe: the in-loop round path (gated on
        # 'round_no == 1 and has_summoned') and this post-loop path share
        # the once-per-session run_share_probe() click, gated by the
        # module-level M6_SHARE_PROBE_DONE flag. This comment also marks
        # the end of the mint-probe block for the source-level guard
        # tests (tests/test_kpi_geo_gate.py Contract 2 scans from the
        # m7_probe record up to the first 'M6 share probe' marker after
        # it): the ONLY click in this block is the single '⚡ Mint via
        # Lightning' invoice-creation click above (at most once per run —
        # the post-loop caller stops at the first candidate with a live
        # MINT area).
        probe_body_after_invoice = probe_page.locator("body").inner_text()
        m7_probe["invoice_ok"], m7_probe["invoice_msg"] = parse_invoice_status(
            probe_body_after_invoice
        )
        m7_probe["alby_configured"] = fetch_alby_configured()
        # Auto-verify poller evidence (iter-17 prod deploy): while
        # lightning_auto_verify is True the invoice panel renders the marker
        # '⏳ Auto-checking payment… N/30' (N = lightning_verify_attempts,
        # 30 = LIGHTNING_VERIFY_MAX_ATTEMPTS) and the hidden rx.moment
        # poller ticks every 6s. The waits above (2500ms + 4500ms ≈ 7s after
        # the click) span at least one tick, so a live iter-17 deploy shows
        # N >= 1. Absence is recorded HONESTLY as auto_verify_seen=False
        # (older deploy without auto-verify, or the poll already gave up) —
        # never as a pass. Never fatal.
        try:
            av_match = re.search(
                r"^.*⏳ Auto-checking payment…\s*\d+/30.*$",
                probe_body_after_invoice,
                re.M,
            )
            m7_probe["auto_verify_seen"] = bool(av_match)
            m7_probe["auto_verify_marker"] = av_match.group(0).strip() if av_match else None
        except Exception as e:
            m7_probe["auto_verify_seen"] = False
            m7_probe["auto_verify_marker"] = None
            print(f"   [m7-probe:{candidate_label}] auto-verify marker parse failed (not fatal): {str(e)[:120]}")
        print(f"   [m7-probe:{candidate_label}] auto-verify poller: seen={m7_probe['auto_verify_seen']}, marker={m7_probe['auto_verify_marker']}")
        print(f"[m7-probe:{candidate_label}] {json.dumps(m7_probe, ensure_ascii=False)}")
    except Exception as e:
        print(f"[m7-probe:{candidate_label}] ERROR (not fatal): {str(e)[:200]}")
    finally:
        if probe_ctx is not None:
            try:
                probe_ctx.close()
            except Exception:
                pass
    return m7_probe

def run_depth_release_probe(browser, candidate_label="depth-release"):
    """Depth-win release probe: prove the FULL release ritual is reachable
    on prod (Lens #97 reframe — the win is DEPTH: ONE complete release
    with final words at a real place = 100%, not archetype breadth).

    Fresh context + fresh player identity (user_id=709999998) -> summon a
    run-unique ENGLISH thought (probe_thought, Lover base — same dedup
    reasoning as the mint probe) -> Care tab -> click '✦ EVOLVE' TWICE
    (evolve_agent has NO probability gate, cap 2) so agent_evolution
    reaches stage 2 -> click '💨 Отпустить' .first (the care-panel
    show_release button; the dialog confirm carries the SAME label, so
    after the dialog opens we fill the textarea and click .last = the
    dialog confirm) with final words 'Прощай, страх. Свободен.' + real
    geo (capture_location '⟳' BEFORE summon, same as the rounds).

    The authoritative signal is the /health complete_releases delta
    (0 -> 1): release_creature() persists status='released' + final_words
    via _MEMORY.update_seed, and the progress counter increments only
    when final words are non-empty AND lat/lon != 0 (record_complete_
    release). UI receipt markers ('✓ Отпущено:' / the quoted final words
    / 'отпустил свою мысль' in the body after confirm) are secondary
    evidence. KPI policy: NEVER clicks any mint button (Contract 3) —
    this probe touches only the care/release path. Honest note: creates
    exactly ONE real released seed on prod per run.
    """
    depth_probe = {"probe_thought": None, "released_clicked": False,
                   "words_entered": False, "receipt_seen": False,
                   "receipt_snippet": None, "complete_before": None,
                   "complete_after": None, "complete_delta": None,
                   "error": None}
    probe_ctx = None
    try:
        depth_probe["complete_before"] = fetch_health_full().get(
            "complete_releases")
        thought = probe_thought()  # Lover base, run-unique timestamp
        depth_probe["probe_thought"] = thought
        probe_ctx = browser.new_context(
            viewport={"width": 414, "height": 896})
        setup_geo(probe_ctx)
        probe_page = probe_ctx.new_page()
        # TMA env: same injected-mock pattern as the rounds (distinct
        # player identity so the probe player starts with summon_count=0).
        tma_setup = tma_env.setup_tma_env(
            probe_page,
            user_id=709999998,
            first_name="KPIReleaseProbe",
            username="kpi_release_probe",
            auto_location=(GEO_LAT, GEO_LON),
        )
        print(f"[depth-probe:{candidate_label}] TMA env: "
              f"{json.dumps(tma_setup, ensure_ascii=False)}")
        probe_page.goto(URL, timeout=60000)
        probe_page.wait_for_timeout(6000)
        gotit = probe_page.locator("button:has-text('Got it!')").first
        if gotit.count() > 0 and gotit.is_visible():
            gotit.click(timeout=5000)
            probe_page.wait_for_timeout(1500)
        # M1: press '⟳' BEFORE typing the thought (same as the rounds)
        capture_location(probe_page)
        inp = probe_page.locator("input").first
        inp.wait_for(state="visible", timeout=30000)
        inp.fill(thought)
        probe_page.wait_for_timeout(400)
        for kw in ['Got it!', 'Continue', '✦ Continue', 'ok', 'close']:
            try:
                b = probe_page.get_by_role(
                    "button", name=kw, exact=False).first
                if b.count() > 0 and b.is_visible():
                    b.click(timeout=1200)
                    probe_page.wait_for_timeout(300)
            except Exception:
                pass
        probe_page.locator("button:has-text('SUMMON')").first.click(
            timeout=15000)
        print(f"[depth-probe:{candidate_label}] probe_thought={thought!r} "
              "clicked SUMMON, waiting...")
        wait_result(probe_page)
        probe_page.wait_for_timeout(2500)
        # The release ritual lives on the Care tab (same as the MINT area)
        care_tab = probe_page.locator("button:has-text('Care')").first
        if care_tab.count() > 0 and care_tab.is_visible():
            care_tab.click(timeout=4000)
            probe_page.wait_for_timeout(1500)
        # '✦ EVOLVE' TWICE (evolve_agent: no probability gate, cap 2)
        # -> agent_evolution stage 2, which unlocks the release button.
        for evo in range(2):
            evolve_btn = probe_page.locator(
                "button:has-text('✦ EVOLVE')").first
            if evolve_btn.count() > 0 and evolve_btn.is_visible():
                evolve_btn.click(timeout=4000)
                print(f"[depth-probe:{candidate_label}] clicked "
                      f"'✦ EVOLVE' ({evo + 1}/2)")
                probe_page.wait_for_timeout(1200)
            else:
                print(f"[depth-probe:{candidate_label}] '✦ EVOLVE' not "
                      f"visible on attempt {evo + 1} (not fatal)")
                break
        # show_release: the care-panel '💨 Отпустить' (.first — the dialog
        # confirm renders the SAME label, so after the dialog opens we
        # click .last = the dialog confirm for the actual release).
        release_btn = probe_page.locator(
            "button:has-text('💨 Отпустить')").first
        if release_btn.count() > 0 and release_btn.is_visible():
            release_btn.click(timeout=4000)
            depth_probe["released_clicked"] = True
            print(f"[depth-probe:{candidate_label}] clicked "
                  "'💨 Отпустить' (show_release dialog opened)")
            probe_page.wait_for_timeout(1200)
        else:
            print(f"[depth-probe:{candidate_label}] '💨 Отпустить' "
                  "(show_release) not visible — evolution stage < 2? "
                  "(not fatal)")
        # Final words in the dialog textarea + confirm (.last = dialog)
        try:
            words_ta = probe_page.locator("textarea").first
            if words_ta.count() > 0 and words_ta.is_visible():
                words_ta.fill("Прощай, страх. Свободен.")
                depth_probe["words_entered"] = True
                probe_page.wait_for_timeout(1000)
                confirm_btn = probe_page.locator(
                    "button:has-text('💨 Отпустить')").last
                if confirm_btn.count() > 0 and confirm_btn.is_visible():
                    confirm_btn.click(timeout=4000)
                    print(f"[depth-probe:{candidate_label}] confirm "
                          "'💨 Отпустить' clicked (release_creature)")
                    probe_page.wait_for_timeout(2000)
        except Exception as e:
            print(f"[depth-probe:{candidate_label}] dialog fill/confirm "
                  f"failed (not fatal): {str(e)[:120]}")
        # Receipt evidence (secondary) + the authoritative /health delta.
        # The receipt markers are session-only UI: '✓ Отпущено:' + the
        # quoted final words + 'отпустил свою мысль' render ONLY right
        # after release_creature (the always-visible 'Отпущено в мир: N'
        # progress line is NOT a receipt proof — it renders on every load).
        receipt_body = probe_page.locator("body").inner_text()
        depth_probe["receipt_seen"] = (
            "✓ Отпущено" in receipt_body
            or '"Прощай, страх. Свободен."' in receipt_body
            or "отпустил свою мысль" in receipt_body
        )
        depth_probe["receipt_snippet"] = re.sub(
            r"\s+", " ", receipt_body).strip()[:300]
        depth_probe["complete_after"] = fetch_health_full().get(
            "complete_releases")
        if isinstance(depth_probe["complete_before"], int) and isinstance(
                depth_probe["complete_after"], int):
            depth_probe["complete_delta"] = (
                depth_probe["complete_after"] - depth_probe["complete_before"])
        print(f"[depth-probe:{candidate_label}] receipt_seen="
              f"{depth_probe['receipt_seen']}, complete_releases: "
              f"before={depth_probe['complete_before']} "
              f"after={depth_probe['complete_after']} "
              f"delta={depth_probe['complete_delta']}")
        print(f"[depth-probe:{candidate_label}] "
              f"{json.dumps(depth_probe, ensure_ascii=False)}")
    except Exception as e:
        depth_probe["error"] = str(e)[:200]
        print(f"[depth-probe:{candidate_label}] ERROR (not fatal): "
              f"{str(e)[:200]}")
    finally:
        if probe_ctx is not None:
            try:
                probe_ctx.close()
            except Exception:
                pass
    return depth_probe

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--enable-features=ClipboardReadWrite"])
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
    mint_ui_state_rounds = {}
    invoice_ok_rounds = []
    round_no = 0
    # M6: read the server-side share counter BEFORE the session (the
    # authoritative signal — share_creature() records on JsonMemory BEFORE
    # the clipboard write, so headless clipboard failures don't matter).
    share_count_before = fetch_share_count()
    print(f"[m6-share-probe] share_count_before: {share_count_before}  (from /health json share_count, read before the session)")
    # M6: once-per-session probe gate — module-level M6_SHARE_PROBE_DONE
    # (defined next to run_share_probe). The probe fires on the FIRST
    # round that produces a fresh summon (has_summoned=True), whichever
    # round number that is (all 12 archetypes are seeded on prod, so
    # round 1 normally hits the dedup path and has_summoned=False); if
    # the in-loop gate never fires, the post-loop M7 probe path runs the
    # share probe on its guaranteed fresh summon instead.

    for theme, thought in THOUGHTS:
        if len(collected) >= CAP:
            break
        round_no += 1
        ctx = browser.new_context(viewport={"width": 414, "height": 896})
        # M1: geolocation permission + Kraków coords BEFORE navigation
        try:
            setup_geo(ctx)
            print(f"[round {round_no}] geo granted: {GEO_LAT}, {GEO_LON} (simulated device permission via Playwright)")
        except Exception as e:
            print(f"[round {round_no}] geo setup failed: {str(e)[:120]}")
        page = ctx.new_page()
        # TMA env: inject the resilient window.Telegram.WebApp mock BEFORE
        # the app loads, so this round runs as a real TMA (platform android,
        # per-round player identity, LocationButton geo bridge auto-answered
        # with the simulated Kraków coords — M1 via the TMA path).
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
            # M6: successful summon flag (matches the app's has_summoned
            # gate on share_creature — share only counts when a real
            # creature is present).
            has_summoned = "A new presence stirs" in body
            page.wait_for_timeout(2500)
            page.screenshot(path=f"/tmp/terramon_new_win_{round_no}.png", full_page=True)

            # M2: early vision-lore snapshot right after summon (informational
            # only — the static map renders ~1.5s later, so the authoritative
            # M1/M2 NSS evidence is counted from the Care-tab re-check below).
            ev, body = collect_m2_evidence(page)
            rlog["m2"] = ev
            print(f"   [M2 evidence (early snapshot)] {json.dumps(ev, ensure_ascii=False)}")

            # M7: mint-loop evidence (presence-only — never click any mint
            # button that creates a mint record, never '✅ I've paid — verify',
            # never pay). Early snapshot is INFORMATIONAL only (right after
            # SUMMON the app is on the Terra tab, where the creature-card
            # MINT area is not rendered); the authoritative per-round mint
            # evidence comes from the m7_care read on the Care tab below.
            m7 = m7_check(page)
            rlog["m7"] = m7
            print(f"   [M7 evidence] {json.dumps(m7, ensure_ascii=False)}")

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
                geo_ok_body = bool(place_after_care) and place_after_care.replace(" ", "") not in ("0.00,0.00",)
                oye_after_care = page.locator("button:has-text('Open your eyes')").count()
                map_imgs_after_care = [
                    page.locator("img").nth(i).get_attribute("src")
                    for i in range(page.locator("img").count())
                    if "static-map" in (page.locator("img").nth(i).get_attribute("src") or "")
                    or "yandex" in (page.locator("img").nth(i).get_attribute("src") or "")
                ]
                # M1 geo evidence fix: the UI shows a human place_name ('Kraków,
                # Poland' style), so the body-text coords regex finds nothing.
                # The static-map <img> URL carries the REAL lat/lon (static_map_url
                # returns '' when agent_lat/lon are 0) — count either source.
                geo_ok_map_url = geo_ok_from_map_url(map_imgs_after_care)
                geo_ok_after_care = geo_ok_map_url or geo_ok_body
                rlog["m2_after_care"] = {
                    "oye": oye_after_care,
                    "map_imgs": map_imgs_after_care,
                    "geo_ok": geo_ok_after_care,
                    "place": place_after_care,
                    "place_name_after_care": place_name_from_body(care_body),
                    "geo_ok_body": geo_ok_body,
                    "geo_ok_map_url": geo_ok_map_url,
                }
                print(f"   -> main-card (Care tab) OYE: {oye_after_care}, map: {map_imgs_after_care}, geo_ok: {geo_ok_after_care} (body: {geo_ok_body}, map-url: {geo_ok_map_url}, place: {place_after_care}, place_name: {rlog['m2_after_care']['place_name_after_care']})")
                # NSS M1/M2 evidence from the re-check (static map visible by now)
                if geo_ok_after_care:
                    geo_ok_rounds.append(round_no)
                oye_total += oye_after_care
            except Exception as e:
                rlog["m2_after_care"] = {"oye": 0, "map_imgs": [], "geo_ok": False, "error": str(e)[:120]}
                print(f"   -> main-card (Care tab) re-check failed (not fatal): {str(e)[:120]}")

            # M7 (authoritative, Care tab): the creature-card MINT area
            # ('⚡ MINT · N Stars' + '⚡ Mint via Lightning') renders only when
            # the bottom-nav Care tab is active (active_tab == 'care'), and
            # the Care re-check above has just clicked it — so the per-round
            # NSS mint evidence is computed HERE on the Care-tab body read,
            # replacing the early Terra-tab snapshot values. Presence-only:
            # never click any mint button that creates a mint record, never
            # '✅ I've paid — verify', never pay.
            try:
                m7_care_body = page.locator("body").inner_text()
                mint_button_presence = "⚡ MINT ·" in m7_care_body
                mint_ui_state = mint_ui_state_from_body(m7_care_body)
                rlog["m7_care"] = {"mint_button_presence": mint_button_presence,
                                   "mint_ui_state": mint_ui_state}
                mint_presence[round_no] = mint_button_presence
                mint_ui_state_rounds[round_no] = mint_ui_state
                print(f"   [m7-care] MINT area: presence={mint_button_presence}, ui_state={mint_ui_state}")
            except Exception as e:
                print(f"   [m7-care] body read failed (not fatal): {str(e)[:120]}")

            # M6 share probe (first fresh summon, Care tab, after a
            # successful summon where has_summoned=True): click '📤 Share'
            # EXACTLY ONCE. share_creature() records EVERY share attempt on
            # the persisted share registry (JsonMemory.record_share) BEFORE
            # the clipboard write, so the /health share_count delta is the
            # authoritative M6 signal — clipboard exceptions in headless
            # Chromium are caught and logged (non-fatal); the server-side
            # counter is what matters.
            if not M6_SHARE_PROBE_DONE and has_summoned:
                share_probe = run_share_probe(page, ctx, share_count_before)
                rlog["m6_share_probe"] = share_probe
                M6_SHARE_PROBE_DONE = True
                print(f"[m6-share-probe] {json.dumps(share_probe, ensure_ascii=False)}")

            # M7 round-1 probe (dedup card): the 12 THOUGHTS are all seeded
            # on prod, so round 1 hits find_seed ->
            # _present_existing_creature, which sets price_sats from the seed
            # but NEVER can_mint — the creature-card MINT area ('⚡ MINT ·')
            # is hidden by design on this path ('locked · train more'), so
            # price_sats may be > 0 but can_mint=False. Record the
            # presence/UI state honestly; the REAL mint loop (can_mint
            # computed on a fresh summon) is probed by the post-loop
            # run_m7_mint_probe with run-unique English thoughts (up to 3
            # candidate attempts). Presence-only: never click any
            # mint button here, never '✅ I've paid — verify', never pay.
            if round_no == 1:
                m7_round1_probe = {"mint_button_presence": False, "mint_ui_state": None}
                try:
                    r1_body = page.locator("body").inner_text()
                    m7_round1_probe["mint_button_presence"] = "⚡ MINT ·" in r1_body
                    m7_round1_probe["mint_ui_state"] = mint_ui_state_from_body(r1_body)
                except Exception as e:
                    print(f"   [m7-probe] round-1 dedup-card MINT-area read failed (not fatal): {str(e)[:120]}")
                rlog["m7_round1_probe"] = m7_round1_probe
                print(f"[m7-probe] {json.dumps(m7_round1_probe, ensure_ascii=False)}")

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

    # ── M7 mint-loop invoice probe (POST-LOOP, up to 3 candidate thoughts) ─
    # Runs AFTER the 12 THOUGHTS rounds on purpose. can_mint uses the
    # GLOBAL belief prior (load_belief() player_id='default',
    # data/beliefs.jsonl), updated by save_belief() on every fresh summon:
    # right after a redeploy wipes data/, the prior resets to the uniform
    # default and even a perfect English thought can fail the 0.5
    # max-posterior gate; by the time this post-loop step runs, the belief
    # file carries every summon accumulated this session (and each failed
    # probe candidate below is itself a fresh summon that nudges the prior
    # via save_belief), so can_mint is much more likely True. Each candidate
    # (Lover -> Magician -> Caregiver — the three that rendered 'mint
    # visible' on prod in the iter-13 run) gets its OWN run-unique
    # timestamped ENGLISH thought in a FRESH browser context: digits are
    # dropped by the classifier tokenizer (regex [a-z']+), so the tokens
    # stay identical -> same high likelihood, while the raw_input string is
    # unique so find_seed() never matches -> REAL fresh summon where
    # can_mint is computed. Stop at the FIRST candidate whose MINT area
    # renders ('⚡ MINT ·' visible) and click '⚡ Mint via Lightning'
    # EXACTLY ONCE — invoice creation only: mint_lightning() creates an Alby
    # Hub invoice and sets the '⚡ Invoice ready: N sats' agent_message; NO
    # mint record is created (minting happens only on settle via
    # verify_lightning). KPI policy: NEVER click '⚡ MINT ·'/'Mint (1 Star)'
    # (buy_stars / optimistic mint that would fabricate mint_count on prod),
    # never '✅ I've paid — verify', never pay. Honest note: up to 3 probe
    # seeds per run (one per candidate attempt) are created on prod —
    # genuine creature births from the English probe thoughts, acceptable
    # and expected.
    m7_probe = None
    m7_probe_attempts = []
    for candidate_label, candidate_base in M7_PROBE_CANDIDATES:
        thought = probe_thought(candidate_base)
        attempt = run_m7_mint_probe(browser, thought, candidate_label=candidate_label)
        m7_probe_attempts.append({"label": candidate_label, **attempt})
        if attempt["mint_button_presence"]:
            # First live MINT area — the invoice was created (or failed)
            # already; stop here so '⚡ Mint via Lightning' is clicked at
            # most once across the whole run.
            m7_probe = attempt
            print(f"[m7-probe] stopping after candidate {candidate_label}: MINT area live, invoice probed (tried {len(m7_probe_attempts)} of {len(M7_PROBE_CANDIDATES)} candidates)")
            break
    if m7_probe is None:
        m7_probe = m7_probe_attempts[-1] if m7_probe_attempts else {
            "probe_thought": None, "probe_seed_created": False,
            "mint_button_presence": False, "mint_ui_state": None,
            "mint_price_sats": None, "lightning_price_sats": None,
            "mint_clicked": False, "invoice_ok": None, "invoice_msg": None,
            "auto_verify_seen": False, "auto_verify_marker": None,
            "alby_configured": None}
        print("[m7-probe] NO candidate rendered the MINT area (can_mint gate not passed for any of the 3 English thoughts; likely a fresh belief file right after redeploy) — invoice_ok stays None, recorded honestly")
    if m7_probe["invoice_ok"] is not None:
        invoice_ok_rounds.append(("postloop", m7_probe["invoice_msg"]))

    # ── Depth-win release probe (POST-mint, Lens #97 reframe) ──────────
    # The win-path is DEPTH: ONE full release (summon -> Care -> 2x
    # '✦ EVOLVE' stage 2 -> final words + real geo -> '💨 Отпустить')
    # = 100%, not archetype breadth. Runs AFTER the whole mint block on
    # purpose; its own fresh player identity so the released seed is
    # attributable. Honest note: creates exactly ONE real released seed
    # (status='released' + final_words + lat/lon) on prod per run.
    depth_release_probe = run_depth_release_probe(browser)
    depth_win_achieved = bool(
        isinstance(depth_release_probe.get("complete_delta"), int)
        and depth_release_probe["complete_delta"] >= 1
    )

    print("=== COLLECTED:", collected)
    print("=== DISTINCT COUNT:", len(collected))
    print()
    print("=== NSS-EVIDENCE ===")
    print("geo_sim: Playwright grant_permissions + set_geolocation (Kraków 50.0619, 19.9368) + '⟳' click —",
          "simulated device permission, NOT a real device (honest note)")
    print(f"geo_ok_rounds: {geo_ok_rounds}  (geo_ok_rounds now counts map-URL coords OR body-text coords; body coords = place contains coords != '0.00, 0.00')")
    print(f"distinct_archetypes: {len(collected)} -> {sorted(collected.keys())}")
    print(f"oye_buttons_total: {oye_total}")
    print(f"mint_button_presence: {mint_presence}  (round -> '⚡ MINT · N Stars' visible on the creature card; per-round evidence comes from the Care-tab read (rlog['m7_care']) — the MINT area renders only when the Care tab is active; never clicked — presence-only policy)")
    print(f"mint_ui_state: {mint_ui_state_rounds}  (creature-card MINT area per round, from the Care-tab read (rlog['m7_care']): 'mint visible' / 'locked · train more' / 'free summon' / 'unknown')")
    print(f"invoice_ok: {invoice_ok_rounds if invoice_ok_rounds else 'no invoice message observed (MINT area not live or no agent_message)'}  (post-loop probe: first candidate with a live fresh-summon MINT area — ONE '⚡ Mint via Lightning' invoice-creation click, creates an Alby Hub invoice only, NO mint record, NO payment; markers parsed from the agent_message)")
    m7_round1_probe = next((r.get("m7_round1_probe") for r in round_log if r.get("m7_round1_probe") is not None), None)
    print(f"m7_round1_probe (round 1): {json.dumps(m7_round1_probe, ensure_ascii=False) if m7_round1_probe else 'not probed'}  (dedup card: _present_existing_creature sets price_sats but NEVER can_mint, so the mint button is hidden by design there — 'locked · train more')")
    print(f"m7_probe_postloop: {json.dumps(m7_probe, ensure_ascii=False)}  (post-loop run-unique ENGLISH thought '{m7_probe.get('probe_thought')}' -> REAL new summon bypassing dedup -> fresh-summon MINT area + '⚡ Mint via Lightning' invoice-creation click; invoice_ok + alby_configured tell whether Alby Hub is configured on prod; probe_seed_created=True means up to 3 real seeds created on prod by this run, one per candidate attempt — honest note; the classifier is English-keyword TF-IDF (tokenizer regex [a-z']+ drops Cyrillic), so Russian thoughts never reach can_mint)")
    print(f"m7_probe_attempts: {json.dumps(m7_probe_attempts, ensure_ascii=False)}  (candidate attempts in order Lover -> Magician -> Caregiver, stopped at the first with a live MINT area; each attempt used its own run-unique timestamped English thought in a fresh context)")
    print(f"auto_verify_seen: {m7_probe.get('auto_verify_seen')}  (post-loop mint probe, ~7s after the single '⚡ Mint via Lightning' invoice-creation click: '⏳ Auto-checking payment… N/30' visible in the invoice panel = the hidden rx.moment poller (6s tick, LIGHTNING_VERIFY_INTERVAL_MS) is ARMED on the live prod deploy; False = iter-17 auto-verify absent on this deploy or the poll already gave up — recorded honestly, absence is never a pass)")
    print(f"auto_verify_marker: {m7_probe.get('auto_verify_marker')}  (the matched invoice-panel body line, e.g. '⏳ Auto-checking payment… 1/30', or None)")
    print(f"mint_price_sats: {m7_probe.get('mint_price_sats')}  (post-loop mint probe, fresh-summon creature card: price parsed from the '⚡ MINT · N Stars' button label — the unit is STARS (Telegram Stars rail), NOT sats; the field name mint_price_sats is kept for back-compat with the NSS-EVIDENCE schema; None when the MINT area is not live — the price renders only when price_sats > 0 AND can_mint)")
    print(f"lightning_price_sats: {m7_probe.get('lightning_price_sats')}  (post-loop mint probe: the REAL Lightning-invoice price shown on the '⚡ Mint via Lightning · N sats' button label — the exact price the user sees and pays, floor 3000 per LIGHTNING_MIN_MINT_SATS; parsed from the button label when the MINT area is live; None otherwise)")
    print(f"place_name_rounds: {json.dumps([r.get('m2_after_care', {}).get('place_name_after_care') for r in round_log], ensure_ascii=False)}  (M1 geo evidence: human place name from the creature card's 📍 line — the UI shows 'Kraków, Polska' style names, not raw coords; None when the card shows no place name)")
    m6_share_probe = next((r.get("m6_share_probe") for r in round_log if r.get("m6_share_probe") is not None), None)
    print(f"m6_share_probe (round 1): {json.dumps(m6_share_probe, ensure_ascii=False) if m6_share_probe else 'not probed (no round produced a fresh summon — has_summoned never True)'}  (server-side /health share_count delta; share_creature records BEFORE the clipboard write, so clipboard errors are non-fatal)")
    print(f"m6_share_probe_postloop: {json.dumps(m7_probe.get('m6_share_probe_postloop'), ensure_ascii=False) if m7_probe.get('m6_share_probe_postloop') else 'not probed (no live fresh-summon card)'}  (post-loop share probe on the guaranteed fresh summon — deep link + 📍 birthplace read from the clipboard via navigator.clipboard.readText(); share_creature writes the card to the clipboard, so clipboard evidence is the authoritative M6 deep-link signal)")
    print(f"share_count_health: before={share_count_before} after={m6_share_probe.get('share_after') if m6_share_probe else None}  (from /health json share_count, M6 server-side share counter)")
    print(f"complete_releases_before: {depth_release_probe.get('complete_before')}  (from /health json complete_releases, read before the depth release probe — seeds with status='released' + final_words + real geo)")
    print(f"complete_releases_after: {depth_release_probe.get('complete_after')}  (from /health json complete_releases, read after the full release ritual)")
    print(f"complete_releases_delta: {depth_release_probe.get('complete_delta')}  (0->1 = the depth win-path is REACHABLE on prod: ONE complete release with final words + real geo = 100% of the win, Lens #97 reframe)")
    print(f"depth_win_achieved: {depth_win_achieved}  (True = /health complete_releases incremented by this run's release — the authoritative M3 signal, NOT just UI text)")
    print(f"depth_release_probe: {json.dumps(depth_release_probe, ensure_ascii=False)}  (depth-win release ritual on prod: fresh player -> summon run-unique English Lover thought -> Care tab -> 2x '✦ EVOLVE' (stage 2, no probability gate) -> '💨 Отпустить' dialog -> final words 'Прощай, страх. Свободен.' + real geo (⟳) -> confirm; receipt_seen = '✓ Отпущено:' / quoted final words / 'отпустил свою мысль' in the body after confirm — session-only UI markers, the always-visible 'Отпущено в мир: N' progress line is NOT a receipt proof; honest note: creates exactly ONE real released seed on prod per run)")
    mc = fetch_mint_count()
    print(f"mint_count_health: {mc}  (from /health, json mint_count)")
    health_full = fetch_health_full()
    print(f"data_restored_from_snapshot: {health_full.get('data_restored_from_snapshot')}  (from /health json durability field; None when /health does not report it)")
    print(f"restored_seed_count: {health_full.get('restored_seed_count')}  (from /health json durability field; None when /health does not report it)")
    print(f"restored_mint_count: {health_full.get('restored_mint_count')}  (from /health json durability field; None when /health does not report it)")
    print(f"restored_share_count: {health_full.get('restored_share_count')}  (from /health json durability field; None when /health does not report it)")
    print(f"snapshot_ts: {health_full.get('snapshot_ts')}  (from /health json durability field; None when /health does not report it)")
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
