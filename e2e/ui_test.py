"""Browser end-to-end journey (Playwright, headless Chromium). Both servers must be running:  python e2e/ui_test.py
Uses LIVE providers for Paris (results are cached, so repeat runs cost no SerpApi quota). Exits non-zero on any failed check."""
import os, sys, time
from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://localhost:5173")
SHOTS = os.path.join(os.path.dirname(__file__), "shots"); os.makedirs(SHOTS, exist_ok=True)
EMAIL = f"e2e{int(time.time())}@example.com"
results, issues = [], []

def check(name, ok, detail=""):
    results.append((name, ok, detail)); print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))

def run():
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"])
        page = b.new_context(viewport={"width": 1366, "height": 900}).new_page()
        page.on("console", lambda m: issues.append(("console", m.text[:200], page.url)) if m.type == "error" else None)
        page.on("pageerror", lambda e: issues.append(("pageerror", str(e)[:200], page.url)))
        page.on("response", lambda r: issues.append((f"http{r.status}", r.url[:110], page.url)) if r.status >= 500 or (r.status >= 400 and "/api/" in r.url and r.status not in (401, 404, 409, 422)) else None)
        chat = "section[aria-label='TRIP assistant chat']"

        # ---- landing + trip builder
        page.goto(BASE); page.wait_for_selector("text=intelligently", timeout=15000)
        check("landing hero", "planned" in page.locator("h1").inner_text().lower())
        check("brand Plarno.ai, no old name", "Plarno" in page.locator("header a").first.inner_text() and "TripPilot" not in page.content())
        check("3D bot canvas rendered", page.locator("canvas").count() >= 1)
        page.screenshot(path=f"{SHOTS}/01_landing.png")
        page.click("button:has-text('Plan my trip')"); check("builder validates empty destination", page.locator("[role=alert]:has-text('where')").count() == 1)
        page.fill("#tb-dest", "Paris"); page.fill("#tb-from", "Mumbai"); page.fill("#tb-budget", "250000"); page.fill("#tb-date", "2026-12-10")
        page.click("button:has-text('Plan my trip')"); page.wait_for_url("**/auth", timeout=10000)
        page.wait_for_selector("text=request is saved", timeout=10000); check("builder saves request and asks to sign in", True)
        page.click("text=Create an account"); page.fill("#au-name", "E2E"); page.fill("#au-email", EMAIL); page.fill("#au-pw", "password123"); page.click("button:has-text('Sign up')")
        page.wait_for_url("**/workspace", timeout=15000)
        page.wait_for_selector("text=Estimated total", timeout=180000)
        check("pending request resumed after sign-up -> Paris plan", "Paris" in page.inner_text("main"))
        check("4 day cards", page.locator("article").count() >= 4, str(page.locator("article").count()))
        check("real photos on stops", page.locator("article img[src^='http']").count() >= 3)
        page.screenshot(path=f"{SHOTS}/02_itinerary.png")

        for tab in ["map", "hotels", "areas", "budget", "safety", "bookings", "agents"]:
            page.click(f"[role=tab]:has-text('{tab}')"); page.wait_for_timeout(900)
            check(f"tab {tab} renders", len(page.locator("main").inner_text()) > 200 and "Something went wrong" not in page.content())
        page.click("[role=tab]:has-text('map')"); page.wait_for_timeout(5000)
        check("map shows numbered pins + route", page.locator(".maplibregl-marker").count() >= 3, str(page.locator(".maplibregl-marker").count()))
        page.screenshot(path=f"{SHOTS}/03_map.png")
        page.click("[role=tab]:has-text('hotels')"); page.wait_for_timeout(600)
        check("hotel cards have booking links", page.locator("a:has-text('View & book')").count() >= 2)
        before = page.inner_text("main"); page.locator("button:has-text('Choose')").last.click(); page.wait_for_timeout(3000)
        check("hotel change recalculates plan", page.inner_text("main") != before)
        page.click("[role=tab]:has-text('safety')"); page.wait_for_timeout(600)
        check("safety: live/cached weather+AQI badge + emergency numbers", page.locator(".badge:has-text('live'), .badge:has-text('cached')").count() > 0 and "112" in page.inner_text("main"))
        page.click("[role=tab]:has-text('bookings')"); page.wait_for_timeout(600)
        check("bookings: external links, no fake confirmation", page.locator("a:has-text('Book')").count() >= 1 and "provider's website" in page.inner_text("main"))
        page.click("[role=tab]:has-text('itinerary')"); page.wait_for_timeout(500)
        rm = page.locator("button[aria-label^='Remove']"); c0 = rm.count()
        rm.first.click(); page.wait_for_timeout(3500)
        check("remove attraction updates itinerary", page.locator("button[aria-label^='Remove']").count() == c0 - 1)

        # ---- TRIP assistant
        page.click("button[aria-label='Open TRIP assistant']"); page.wait_for_selector(chat)
        def ask(q, expect, timeout=90000):
            sel = "section[aria-label='TRIP assistant chat']"
            js = "(e)=>{const t=document.querySelector(\"section[aria-label='TRIP assistant chat']\").innerText;return e.split('|').reduce((n,x)=>n+t.split(x).length-1,0)}"
            before = page.evaluate(js, expect)  # a reply counts only if it ADDS occurrences of the expected text
            page.fill(sel + " input", q); page.click(sel + " button:has-text('Send')")
            try:
                page.wait_for_function("([e,n,js])=>eval('('+js+')')(e)>n", arg=[expect, before, js], timeout=timeout); return True
            except Exception:
                return False
        check("TRIP: hotels under ₹30,000 (real tool)", ask("Find hotels under ₹30,000", "at or under|No hotel found"))
        check("TRIP: historical places nearby (real data)", ask("Show historical places nearby", "Google Maps data"))
        check("TRIP: restaurants around my hotel", ask("Find good restaurants around my hotel", "Restaurants near"))
        check("TRIP: weather & pollution", ask("Explain today's weather and pollution", "Air quality|Weather:|unavailable"))
        check("TRIP: best route", ask("Show the best route for these attractions", "Best visiting order"))
        check("TRIP: make it cheaper", ask("Make my trip cheaper without compromising the important parts", "Estimated cost"))
        page.screenshot(path=f"{SHOTS}/04_trip_chat.png")
        page.click("button[aria-label='Collapse']")

        # ---- persistence
        page.goto(BASE + "/workspace?tab=hotels"); page.wait_for_selector("text=Your trip to Paris", timeout=20000)
        check("reload keeps the open trip", True)
        page.goto(BASE + "/trips"); page.wait_for_selector("text=-day Paris", timeout=15000)
        check("trip listed in My trips", True)

        # ---- discover + flights
        page.goto(BASE + "/discover?city=Paris&tab=attractions"); page.wait_for_selector("article", timeout=90000)
        check("discover: real Paris attractions with photos", page.locator("article img[src^='http']").count() >= 3)
        page.select_option("[aria-label='Sort results']", "rating"); page.wait_for_timeout(300)
        check("discover: sort works", page.locator("article").count() >= 3)
        page.click("button[aria-pressed]:has-text('Map')"); page.wait_for_timeout(3500)
        check("discover: map view pins", page.locator(".maplibregl-marker").count() >= 3)
        page.screenshot(path=f"{SHOTS}/05_discover.png")
        page.goto(BASE + "/transport"); page.wait_for_selector("text=Ways to travel")
        page.fill("#tr-from", "Mumbai"); page.keyboard.press("Escape"); page.fill("#tr-to", "Paris"); page.keyboard.press("Escape")
        page.click("button:has-text('Compare ways')"); page.wait_for_selector("article h3", timeout=90000)
        page.wait_for_selector(".badge:has-text('live')", timeout=5000)
        check("ways to travel: live flight fares + cab transfers", "Cab + Flight" in " ".join(page.locator("article h3").all_inner_texts()))

        # ---- mobile
        m = b.new_context(viewport={"width": 390, "height": 800}, is_mobile=True); mp = m.new_page()
        mp.on("pageerror", lambda e: issues.append(("pageerror(mobile)", str(e)[:200], mp.url)))
        for path in ["/", "/auth", "/discover", "/transport"]:
            mp.goto(BASE + path); mp.wait_for_timeout(1500)
            sw, cw = mp.evaluate("document.documentElement.scrollWidth"), mp.evaluate("document.documentElement.clientWidth")
            check(f"mobile no horizontal overflow {path}", sw <= cw + 1, f"scroll {sw} > client {cw}")
            mp.screenshot(path=f"{SHOTS}/06_mobile{path.replace('/', '_') or '_home'}.png")
        b.close()

run()
bad = [r for r in results if not r[1]]
print(f"\n{len(results) - len(bad)}/{len(results)} checks passed")
ign = [i for i in issues if "tile" not in i[1] and "favicon" not in i[1] and "googleusercontent" not in i[1]]
print("console/network issues:", len(ign))
for i in ign[:15]: print("  ", i)
sys.exit(1 if bad else 0)
