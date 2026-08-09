#!/usr/bin/env python3
"""iter-14 diagnostic: why did the '⚡ Mint via Lightning' click time out?

Hypothesis: ZONE 1 compact card (always rendered, fixed-height, no scroll)
now overflows and CLIPS its mint area; locator(...).first targets the home
card button (clipped -> not actionable) instead of the Care-panel button.

Dumps, for every matching button: index, visibility, bounding box, and the
element at the box center (what would receive the click). Then clicks the
LAST (Care panel) button once and parses the agent_message for '⚡ Invoice
ready' — proving invoice creation on prod (honest M7 evidence).
"""
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tma_env  # noqa: E402

URL = "https://terramon-tma-production.up.railway.app"
GEO_LAT, GEO_LON = 50.0619, 19.9368
THOUGHT = f"I want to be close to you — love is all that matters, I give you my whole heart, being with you is enough. {int(time.time()*1000)}"

from playwright.sync_api import sync_playwright  # noqa: E402


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 414, "height": 896})
        ctx.grant_permissions(["geolocation"])
        ctx.set_geolocation({"latitude": GEO_LAT, "longitude": GEO_LON})
        page = ctx.new_page()
        tma_env.setup_tma_env(page, user_id=709999998, first_name="KpiDiag",
                              username="kpi_diag", auto_location=(GEO_LAT, GEO_LON))
        page.goto(URL, timeout=60000)
        page.wait_for_timeout(6000)
        gotit = page.locator("button:has-text('Got it!')").first
        if gotit.count() > 0 and gotit.is_visible():
            gotit.click(timeout=5000)
            page.wait_for_timeout(1500)
        # press '⟳' before typing (same as rounds)
        try:
            b = page.locator("button:has-text('⟳')").first
            if b.count() > 0 and b.is_visible():
                b.click(timeout=3000)
                page.wait_for_timeout(2000)
        except Exception as e:
            print(f"[diag] geo button: {str(e)[:100]}")
        inp = page.locator("input").first
        inp.wait_for(state="visible", timeout=30000)
        inp.fill(THOUGHT)
        page.wait_for_timeout(400)
        page.locator("button:has-text('SUMMON')").first.click(timeout=15000)
        print(f"[diag] thought={THOUGHT!r} SUMMON clicked, waiting...")
        for i in range(40):
            page.wait_for_timeout(2000)
            body = page.locator("body").inner_text()
            if "A new presence stirs" in body:
                break
        page.wait_for_timeout(2500)
        # Care tab
        try:
            tab = page.locator("button:has-text('Care')").first
            if tab.count() > 0 and tab.is_visible():
                tab.click(timeout=4000)
                page.wait_for_timeout(1500)
        except Exception as e:
            print(f"[diag] Care tab: {str(e)[:100]}")
        # dump ALL matching buttons
        btns = page.locator("button:has-text('⚡ Mint via Lightning')")
        n = btns.count()
        print(f"[diag] '⚡ Mint via Lightning' count = {n}")
        for i in range(n):
            b = btns.nth(i)
            vis = False
            box = None
            try:
                vis = b.is_visible()
            except Exception:
                pass
            try:
                box = b.bounding_box()
            except Exception:
                pass
            print(f"[diag] btn[{i}] visible={vis} box={box}")
            if vis and box:
                cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                top = page.evaluate(
                    "([x, y]) => { const el = document.elementFromPoint(x, y);"
                    " if (!el) return null; const r = el.getBoundingClientRect();"
                    " return { tag: el.tagName, cls: (el.className||'').toString().slice(0,60),"
                    " text: (el.textContent||'').trim().slice(0,40), box: [r.x, r.y, r.width, r.height].map(Math.round) }; }",
                    [cx, cy],
                )
                print(f"[diag] btn[{i}] elementFromPoint center -> {top}")
        # click the LAST (Care panel) one
        if n > 0:
            target = btns.last
            try:
                target.scroll_into_view_if_needed(timeout=3000)
                target.click(timeout=8000)
                print("[diag] clicked .last (Care panel) OK")
            except Exception as e:
                print(f"[diag] .last click failed: {str(e)[:200]}")
            page.wait_for_timeout(4000)
            body = page.locator("body").inner_text()
            m = re.search(r"⚡ Invoice[^\n]*", body)
            print(f"[diag] invoice marker: {m.group(0) if m else None}")
            m2 = re.search(r"⚡ Invoice failed[^\n]*", body)
            print(f"[diag] failure marker: {m2.group(0) if m2 else None}")
        # also dump body text around mint area
        body = page.locator("body").inner_text()
        for line in body.splitlines():
            if "Mint" in line or "sats" in line or "locked" in line or "Invoice" in line:
                print(f"[diag] body> {line.strip()[:100]}")
        browser.close()


if __name__ == "__main__":
    main()
