from playwright.sync_api import sync_playwright
import re, json

URL = "https://terramon-tma-production.up.railway.app/"
ARCHETYPES = ["Hero","Rebel","Sage","Jester","Creator","Magician","Lover","Caregiver","Explorer","Innocent","Ruler","Orphan"]
DISMISS = ["continue","ok","got it","claim","let's go","awesome","nice","close","done","yay","explore","awake"]

THOUGHTS = [
    ("Explorer", "I dream of adventure — crossing oceans, climbing mountains, discovering lost cities and unknown lands..."),
    ("Rebel", "I refuse the system! Street art on concrete walls, fighting the machine, anarchy and freedom, breaking every rule tonight."),
    ("Jester", "Life is a joke and I'm laughing — pranks, puns, silly dances in the rain, making strangers giggle all day long."),
    ("Creator", "Make something beautiful that never existed — a painting, a song, a poem; art gives life its meaning, create meaning."),
    ("Hero", "Courage! I will stand between danger and the innocent, shield the weak, no matter the cost, protect everyone."),
    ("Magician", "Mystery and transformation — turning lead into gold, reading the unseen, secrets of the universe, wonder."),
    ("Caregiver", "I want to help everyone — heal the sick, comfort the lonely, protect the small, feed the hungry, gentle care."),
    ("Ruler", "Order and power — I will build a kingdom, lead my people wisely, command respect, build a lasting legacy."),
    ("Innocent", "Pure joy and simple trust — a child's wonder at the world, believing in magic, kindness without guile."),
    ("Orphan", "I stand alone against the storm, abandoned but unbroken, finding family in strangers, resilience in solitude."),
]

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
    gate_clicked = False
    for i in range(40):
        page.wait_for_timeout(2000)
        body = page.locator("body").inner_text()
        if "Summon (1 Star)" in body and not gate_clicked:
            gate = page.locator("button:has-text('Summon (1 Star)')").first
            if gate.count() > 0 and gate.is_visible():
                try:
                    gate.click(timeout=2000)
                    gate_clicked = True
                    print("   [gate clicked once]")
                except Exception:
                    pass
        d = dismiss_modal(page)
        if d:
            print("   [modal:", d, "]")
            page.wait_for_timeout(1000)
        if "A new presence stirs" in body:
            return body, gate_clicked
    return page.locator("body").inner_text(), gate_clicked

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

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    collected = {}   # archetype -> thought
    round_no = 0
    for theme, thought in THOUGHTS:
        if len(collected) >= 5:
            break
        round_no += 1
        ctx = browser.new_context(viewport={"width": 414, "height": 896})
        page = ctx.new_page()
        try:
            page.goto(URL, timeout=60000)
            page.wait_for_timeout(6000)
            gotit = page.locator("button:has-text('Got it!')").first
            if gotit.count() > 0 and gotit.is_visible():
                gotit.click(timeout=5000)
                page.wait_for_timeout(1500)
            inp = page.locator("input").first
            inp.wait_for(state="visible", timeout=30000)
            inp.fill(thought)
            page.wait_for_timeout(400)
            page.locator("button:has-text('SUMMON')").first.click(timeout=8000)
            print(f"[round {round_no}] theme={theme} clicked SUMMON, waiting...")
            body, gate_clicked = wait_result(page)
            page.wait_for_timeout(2500)
            page.screenshot(path=f"/tmp/terramon_new_win_{round_no}.png", full_page=True)

            # read Terra collection to get authoritative unique/total
            names, counts, tbody = read_terra(page)
            page.screenshot(path=f"/tmp/terramon_new_win_{round_no}_terra.png", full_page=True)

            # main card evidence (go back to Terra home view? Terra tab shows collection; card is on Terra home)
            # check for static-map imgs on collection cards
            map_imgs = [page.locator("img").nth(i).get_attribute("src") for i in range(page.locator("img").count()) if "static-map" in (page.locator("img").nth(i).get_attribute("src") or "")]
            oye_any = page.locator("button:has-text('Open your eyes')").count()
            yandex_any = any("yandex" in (page.locator("img").nth(i).get_attribute("src") or "") for i in range(page.locator("img").count()))
            print(f"   -> card names found: {names}")
            print(f"   -> counts: {counts}")
            print(f"   -> static-map imgs: {map_imgs}")
            print(f"   -> yandex imgs: {yandex_any}, Open-your-eyes buttons: {oye_any}")

            # record NEW archetype: names in collection order; the card list includes all; track which are new
            seen_before = set(collected.keys())
            for n in names:
                if n not in collected:
                    collected[n] = thought
                    print(f"   -> NEW archetype: {n}")
            # if gate was clicked, it may have created a duplicate of the same thought -> same archetype
            ctx.close()
        except Exception as e:
            print(f"[round {round_no}] ERROR: {str(e)[:200]}")
            page.screenshot(path=f"/tmp/terramon_new_win_{round_no}_ERR.png", full_page=True)
            ctx.close()
            continue

    print("=== COLLECTED:", collected)
    print("=== DISTINCT COUNT:", len(collected))
    browser.close()
