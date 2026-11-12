"""Browser checks for: place autocomplete, home-town (day trips) flow, place detail view, Travel tab with budget tiers, Ways-to-travel page.
Both servers must be running. Uses cached live data for Kishangarh / Panaji / Paris where possible. Run: python e2e/ui_features.py"""
import os, sys, time
from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://localhost:5173")
SHOTS = os.path.join(os.path.dirname(__file__), "shots"); os.makedirs(SHOTS, exist_ok=True)
results, issues = [], []

def check(name, ok, detail=""):
    results.append((name, ok, detail)); print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))

def run():
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"])
        page = b.new_context(viewport={"width": 1366, "height": 900}).new_page()
        page.on("console", lambda m: issues.append(("console", m.text[:160], page.url)) if m.type == "error" and "tile" not in m.text and "googleusercontent" not in m.text and "Failed to load resource" not in m.text else None)
        page.on("pageerror", lambda e: issues.append(("pageerror", str(e)[:160], page.url)))

        # ---- autocomplete in the trip builder
        page.goto(BASE); page.wait_for_selector("#tb-dest")
        page.fill("#tb-dest", "kisha"); page.wait_for_selector("[role=option]", timeout=15000)
        opts = page.locator("[role=option]").all_inner_texts()
        check("autocomplete suggests real places for 'kisha'", any("Kishangarh" in o for o in opts), str(opts[:3]))
        check("suggestions show region/country context", any("Rajasthan" in o or "India" in o for o in opts))
        page.screenshot(path=f"{SHOTS}/07_autocomplete.png")
        page.fill("#tb-dest", "kishang"); page.wait_for_function("()=>[...document.querySelectorAll('[role=option]')].some(o=>o.innerText.includes('Kishangarh'))")
        idx = next(i for i, o in enumerate(page.locator("[role=option]").all_inner_texts()) if "Kishangarh" in o and "Rajasthan" in o)
        for _ in range(idx + 1): page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        check("keyboard selection fills the field", "Kishangarh" in page.input_value("#tb-dest") and page.locator("[role=listbox]").count() == 0, page.input_value("#tb-dest"))
        page.fill("#tb-dest", "mad"); page.wait_for_selector("[role=option]")
        check("regions are flagged so users pick a town", page.locator("[role=option] .badge:has-text('region')").count() >= 1)
        page.keyboard.press("Escape")

        # ---- home-town flow
        page.fill("#tb-dest", ""); page.check("text=I live here")
        check("home mode hides 'travelling from'", page.locator("#tb-from").count() == 0 and "your town or city" in page.inner_text("form").lower())
        page.fill("#tb-dest", "Kishangarh, India"); page.wait_for_timeout(600); page.keyboard.press("Escape")
        page.fill("#tb-budget", "10000"); page.fill("#tb-date", "2026-12-12"); page.click("button:has-text('Plan my outings')")
        page.wait_for_selector("text=request is saved", timeout=10000)
        email = f"feat{int(time.time())}@example.com"
        page.click("text=Create an account"); page.fill("#au-name", "F"); page.fill("#au-email", email); page.fill("#au-pw", "password123"); page.click("button:has-text('Sign up')")
        page.wait_for_url("**/workspace", timeout=15000); page.wait_for_selector("text=Estimated total", timeout=180000)
        check("home-town plan: 'Day trips from Kishangarh'", "Day trips from Kishangarh" in page.inner_text("main"), page.inner_text("main")[:200])
        check("home base card, no hotel", "Home in Kishangarh" in page.inner_text("main"), page.inner_text("main")[:300])
        check("3 day cards with real nearby places", page.locator("article").count() >= 3)
        page.screenshot(path=f"{SHOTS}/08_home_trip.png")
        page.click("[role=tab]:has-text('hotels')"); page.wait_for_timeout(400)
        check("hotels tab explains no hotel needed", "No hotel needed" in page.inner_text("main"))
        page.click("[role=tab]:has-text('travel')"); page.wait_for_timeout(400)
        check("travel tab explains day trips", "Day trips from home" in page.inner_text("main"))
        page.click("[role=tab]:has-text('itinerary')"); page.wait_for_timeout(500)
        check("stops show cab fare estimate", "est.)" in page.inner_text("main") and "by cab" in page.inner_text("main"))
        lunch = page.locator("li:has-text('lunch')").count()
        check("days include lunch", lunch >= 2, str(lunch))

        # ---- detail view from an itinerary stop
        page.locator("button[aria-label^='Details for']").first.click(); page.wait_for_selector("[role=dialog]")
        dlg = page.inner_text("[role=dialog]")
        check("detail dialog: address, hours, directions", "Opening hours" in dlg and "Directions" in dlg and "Details" in dlg)
        check("detail dialog has a map", page.locator("[role=dialog] .maplibregl-canvas, [role=dialog] [aria-label='Interactive map']").count() >= 1)
        page.screenshot(path=f"{SHOTS}/09_detail.png")
        page.keyboard.press("Escape"); page.wait_for_timeout(300)
        check("Escape closes the dialog", page.locator("[role=dialog]").count() == 0)
        chip = page.locator("button.chip:has-text('+ ')").first
        before = page.locator("button[aria-label^='Remove']").count()
        chip.click(); page.wait_for_selector("[role=dialog]")
        page.click("[role=dialog] button:has-text('Add to my trip')"); page.wait_for_timeout(4000)
        check("'Add to my trip' from the detail view updates the plan", page.locator("button[aria-label^='Remove']").count() == before + 1 and page.locator("[role=dialog]").count() == 0)

        # ---- cross-country trip: autocomplete for origin, route options with budget tiers
        page.goto(BASE + "/workspace"); page.wait_for_timeout(1500)
        page.click("button:has-text('New trip')") if page.locator("button:has-text('New trip')").count() else None
        page.goto(BASE + "/trips"); page.click("button:has-text('New trip')"); page.wait_for_selector("#tb-dest")
        page.fill("#tb-dest", "Panaji"); page.wait_for_selector("[role=option]"); page.locator("[role=option]").first.click()
        page.fill("#tb-from", "kishang"); page.wait_for_function("()=>[...document.querySelectorAll('[role=option]')].some(o=>o.innerText.includes('Kishangarh'))")
        page.locator("[role=option]:has-text('Kishangarh'):has-text('Rajasthan')").first.click()
        check("origin autocomplete works", "Kishangarh" in page.input_value("#tb-from"), page.input_value("#tb-from"))
        page.fill("#tb-budget", "60000"); page.fill("#tb-date", "2026-12-14"); page.click("button:has-text('Plan my trip')")
        page.wait_for_selector("text=Estimated total", timeout=240000)
        check("trip planned to Panaji from Kishangarh", "Panaji" in page.inner_text("main"))
        page.click("[role=tab]:has-text('travel')"); page.wait_for_selector("text=Within your budget", timeout=10000)
        t = page.inner_text("main")
        check("travel tab: within-budget and stretch sections", "Within your budget" in t and "If you can stretch" in t)
        check("flight stretch shows extra cost + time saved", "round trip" in t and "saves about" in t)
        check("options labelled cheapest/fastest/comfortable", "Cheapest" in t and "Fastest" in t)
        check("flights live, ground estimated", page.locator(".badge:has-text('live')").count() >= 1 and page.locator(".badge:has-text('estimated')").count() >= 1)
        page.locator("button:has-text('step by step')").first.click(); page.wait_for_timeout(300)
        check("step-by-step legs with cab transfers", "cab:" in page.inner_text("main").lower() and "Nearest airport" in page.inner_text("main"))
        page.screenshot(path=f"{SHOTS}/10_travel.png", full_page=True)
        est0 = page.inner_text("main")
        page.locator("button:has-text('Choose this')").last.click(); page.wait_for_selector("[role=status]:has-text('Estimated total is now')", timeout=30000)
        check("choosing an option recalculates the budget", "Estimated total is now" in page.inner_text("main") and page.inner_text("main") != est0)
        check("Selected state shown", page.locator("button:has-text('Selected')").count() >= 1)

        # ---- TRIP answers fare questions
        page.click("button[aria-label='Open TRIP assistant']"); sel = "section[aria-label='TRIP assistant chat']"; page.wait_for_selector(sel)
        page.fill(sel + " input", "How much is the cab fare?"); page.click(sel + " button:has-text('Send')")
        page.wait_for_function("()=>document.querySelector(\"section[aria-label='TRIP assistant chat']\").innerText.includes('Cab charges')", timeout=30000)
        check("TRIP: cab fare answer from the plan", "Jaipur airport" in page.inner_text(sel), page.inner_text(sel)[-500:].replace(chr(10), " | "))
        page.fill(sel + " input", "What are my ways to travel there?"); page.click(sel + " button:has-text('Send')")
        page.wait_for_function("()=>document.querySelector(\"section[aria-label='TRIP assistant chat']\").innerText.includes('Cheapest:')", timeout=30000)
        check("TRIP: lists ways to travel with fares", True)
        page.click("button[aria-label='Collapse']")

        # ---- Discover detail
        page.goto(BASE + "/discover?city=Paris&tab=attractions"); page.wait_for_selector("article", timeout=60000)
        page.locator("article").first.click(); page.wait_for_selector("[role=dialog]")
        d = page.inner_text("[role=dialog]")
        check("discover card opens details with weekday hours", "Opening hours" in d and ("Monday" in d or "Right now" in d or "Hours not listed" in d))
        check("discover detail shows Google Maps + directions", page.locator("[role=dialog] a:has-text('Directions')").count() == 1)
        page.keyboard.press("Escape")
        page.locator("article").nth(1).focus(); page.keyboard.press("Enter"); page.wait_for_selector("[role=dialog]")
        check("cards open from the keyboard (Enter)", True)
        page.click("[aria-label='Close details']")

        # ---- Ways to travel page
        page.goto(BASE + "/transport"); page.wait_for_selector("text=Ways to travel")
        page.fill("#tr-from", "Kishangarh, India"); page.keyboard.press("Escape"); page.fill("#tr-to", "Jaipur, India"); page.keyboard.press("Escape"); page.fill("#tr-b", "6000")
        page.click("button:has-text('Compare ways')"); page.wait_for_selector("text=Within your budget", timeout=60000)
        t = page.inner_text("main")
        titles = " | ".join(page.locator("article h3").all_inner_texts())
        check("short hop: cab, bus and train offered, no flight", "Cab, door to door" in titles and "Bus" in titles and "Train" in titles and "Flight" not in titles, titles)
        check("land options marked as estimates", page.locator(".badge:has-text('estimated')").count() >= 3)
        page.screenshot(path=f"{SHOTS}/11_ways.png", full_page=True)

        # ---- mobile
        mp = b.new_context(viewport={"width": 390, "height": 800}, is_mobile=True).new_page()
        mp.goto(BASE); mp.wait_for_selector("#tb-dest"); mp.fill("#tb-dest", "kisha"); mp.wait_for_selector("[role=option]")
        sw, cw = mp.evaluate("document.documentElement.scrollWidth"), mp.evaluate("document.documentElement.clientWidth")
        check("mobile: autocomplete dropdown causes no overflow", sw <= cw + 1, f"{sw}>{cw}")
        mp.screenshot(path=f"{SHOTS}/12_mobile_autocomplete.png")
        b.close()

run()
bad = [r for r in results if not r[1]]
print(f"\n{len(results) - len(bad)}/{len(results)} checks passed; console issues: {len(issues)}")
for i in issues[:10]: print("  ", i)
sys.exit(1 if bad or issues else 0)
