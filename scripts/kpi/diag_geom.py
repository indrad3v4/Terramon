#!/usr/bin/env python3
"""iter-14 geometry dump: boxes of card / zone1 / input / geo-status / mint buttons."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tma_env  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

URL = "https://terramon-tma-production.up.railway.app"
GEO_LAT, GEO_LON = 50.0619, 19.9368
THOUGHT = f"Mystery and transformation — turning lead into gold, reading the unseen, secrets of the universe, wonder. {int(time.time()*1000)}"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 414, "height": 896})
        ctx.grant_permissions(["geolocation"])
        ctx.set_geolocation({"latitude": GEO_LAT, "longitude": GEO_LON})
        page = ctx.new_page()
        tma_env.setup_tma_env(page, user_id=709999997, first_name="KpiGeom",
                              username="kpi_geom", auto_location=(GEO_LAT, GEO_LON))
        page.goto(URL, timeout=60000)
        page.wait_for_timeout(6000)
        gotit = page.locator("button:has-text('Got it!')").first
        if gotit.count() > 0 and gotit.is_visible():
            gotit.click(timeout=5000)
            page.wait_for_timeout(1500)
        try:
            b = page.locator("button:has-text('⟳')").first
            if b.count() > 0 and b.is_visible():
                b.click(timeout=3000)
                page.wait_for_timeout(2000)
        except Exception as e:
            print(f"[geom] geo btn: {str(e)[:80]}")
        inp = page.locator("input").first
        inp.wait_for(state="visible", timeout=30000)
        inp.fill(THOUGHT)
        page.wait_for_timeout(400)
        page.locator("button:has-text('SUMMON')").first.click(timeout=15000)
        for i in range(40):
            page.wait_for_timeout(2000)
            if "A new presence stirs" in page.locator("body").inner_text():
                break
        page.wait_for_timeout(2500)
        try:
            tab = page.locator("button:has-text('Care')").first
            if tab.count() > 0 and tab.is_visible():
                tab.click(timeout=4000)
                page.wait_for_timeout(1200)
        except Exception:
            pass

        def box(sel):
            try:
                el = page.locator(sel).first
                if el.count() == 0:
                    return f"{sel}: <none>"
                return f"{sel}: vis={el.is_visible()} box={el.bounding_box()}"
            except Exception as e:
                return f"{sel}: ERR {str(e)[:60]}"

        print(box("button:has-text('⚡ Mint via Lightning')"))
        print(box("input"))
        print("[geom] input rect via JS:", page.evaluate(
            "() => { const el = document.querySelector('input'); if (!el) return null;"
            " const r = el.getBoundingClientRect(); return {y: Math.round(r.y), h: Math.round(r.height)}; }"))
        print("[geom] geo status line rect:", page.evaluate(
            "() => { const els = [...document.querySelectorAll('p,span')];"
            " const t = els.find(e => (e.textContent||'').trim() === 'Краков, Польша');"
            " if (!t) return null; const r = t.getBoundingClientRect();"
            " return {text: t.textContent.trim().slice(0,30), y: Math.round(r.y), h: Math.round(r.height)}; }"))
        # ancestry of the home-card lightning button
        print("[geom] btn[0] ancestry:", page.evaluate(
            "() => { const el = document.querySelectorAll('button');"
            " let b = [...el].find(e => (e.textContent||'').includes('⚡ Mint via Lightning'));"
            " if (!b) return null; const out = []; let n = b, depth = 0;"
            " while (n && depth < 8) { const r = n.getBoundingClientRect();"
            " const cs = getComputedStyle(n);"
            " out.push({tag: n.tagName, cls: (n.className||'').toString().slice(0,40),"
            " y: Math.round(r.y), h: Math.round(r.height),"
            " overflowY: cs.overflowY, maxH: cs.maxHeight}); n = n.parentElement; depth++; }"
            " return out; }"))
        # scrollable ancestor scroll position
        print("[geom] scroll info:", page.evaluate(
            "() => { const sc = document.scrollingElement;"
            " return {scrollY: sc ? sc.scrollTop : null, bodyH: document.body ? document.body.scrollHeight : null," 
            " vh: window.innerHeight}; }"))
        browser.close()


if __name__ == "__main__":
    main()
