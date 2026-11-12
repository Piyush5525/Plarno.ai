"""End-to-end functional check of the whole site: every page and the main action on each one, as a real user would do them.
Signs up through the trip form, plans a (cached) Paris trip, then exercises the live guide, itinerary edits, map, travel, hotels, budget,
bookings, the TRIP chat, Discover, Ways to travel, My trips, Preferences, the 404 page, sign-out and the mobile menu.
Fails on any console error, uncaught exception or 5xx.   Run (both servers up):  python e2e/site_check.py     [BASE=http://localhost:5173]"""
import os, re, sys, time
from playwright.sync_api import sync_playwright, expect

BASE = os.environ.get("BASE", "http://localhost:5173")
SHOTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots")
os.makedirs(SHOTS, exist_ok=True)
results, problems = [], []


def check(name, fn):
    t = time.time()
    try:
        fn(); results.append((True, name, time.time() - t)); print(f"  ok   {name}")
    except Exception as e:  # noqa: BLE001
        results.append((False, name, time.time() - t)); print(f"  FAIL {name}: {str(e).splitlines()[0][:200]}")


def watch(page, label):
    noise = ("tile", "googleusercontent", "favicon", "Failed to load resource", "ERR_")
    page.on("console", lambda m: problems.append((label, "console", m.text[:200])) if m.type == "error" and not any(n in m.text for n in noise) else None)
    page.on("pageerror", lambda e: problems.append((label, "pageerror", str(e)[:200])))
    page.on("response", lambda r: problems.append((label, f"HTTP {r.status}", r.url[:120])) if r.status >= 500 or (r.status == 429) else None)


def idle(page, ms=400):
    page.wait_for_timeout(ms)


with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    ctx = b.new_context(viewport={"width": 1366, "height": 900})
    page = ctx.new_page(); watch(page, "desktop")
    page.set_default_timeout(15000)
    tab = lambda k: page.locator(f"#tab-{k}")  # noqa: E731
    not_busy = lambda: expect(page.get_by_text("Updating…")).to_have_count(0, timeout=60000)  # noqa: E731

    print("Landing")
    page.goto(BASE + "/")
    check("hero headline renders", lambda: expect(page.get_by_role("heading", level=1)).to_contain_text("planned"))
    check("live city cards load real readings", lambda: expect(page.locator("a[href^='/discover?city=Paris']").filter(has_text="local time")).to_contain_text("°", timeout=20000))
    def bot_trick():
        page.get_by_role("button", name=re.compile("TRIP the travel bot")).first.click(force=True)  # the bot floats continuously, so skip the "element is still" wait
        expect(page.get_by_text(re.compile("Boing!|Wheee!|Gotcha|Holiday mode!|Aww, thanks!|Yes, let's go!|Peekaboo!")).first).to_be_visible(timeout=4000)
    check("clicking the bot plays a trick", bot_trick)
    def builder_validation():
        page.locator("form[aria-label='Plan a trip'] button:has-text('Plan my trip')").click()
        expect(page.get_by_role("alert").filter(has_text="where you would like to go")).to_be_visible()
    check("trip form validates an empty destination", builder_validation)
    def builder_submit():
        page.fill("#tb-dest", "Paris"); page.keyboard.press("Escape")
        page.fill("#tb-from", "Mumbai"); page.keyboard.press("Escape")
        page.fill("#tb-budget", "250000"); page.fill("#tb-date", "2026-12-10")
        page.get_by_role("button", name="More days").click(); page.get_by_role("button", name="Fewer days").click()
        page.locator("form[aria-label='Plan a trip'] button:has-text('Plan my trip')").click()
        page.wait_for_url("**/auth")
        expect(page.get_by_text("Your trip request is saved")).to_be_visible()
    check("trip form keeps the request and sends a visitor to sign-up", builder_submit)

    print("Auth")
    def bad_login():
        page.fill("#au-email", "nobody@example.com"); page.fill("#au-pw", "wrongpassword"); page.get_by_role("button", name="Sign in", exact=True).last.click()
        expect(page.get_by_role("alert")).to_contain_text("do not match")
    check("wrong password shows a clear message", bad_login)
    email = f"check{int(time.time())}@example.com"
    def signup():
        page.get_by_role("button", name="Create account", exact=True).click()
        page.fill("#au-name", "Site Check"); page.fill("#au-email", email); page.fill("#au-pw", "password123")
        page.get_by_role("button", name="Show password").click(); page.get_by_role("button", name="Sign up").click()
        page.wait_for_url("**/workspace**")
    check("sign-up works", signup)
    check("saved request is planned automatically after sign-up", lambda: expect(page.get_by_text("Estimated total").first).to_be_visible(timeout=200000))

    print("Workspace: live guide")
    check("live guide is the first tab", lambda: expect(tab("guide")).to_have_attribute("aria-selected", "true"))
    check("briefing and live tiles load", lambda: (expect(page.get_by_text("What TRIP noticed")).to_be_visible(), expect(page.get_by_text("Weather now")).to_be_visible(timeout=30000), expect(page.get_by_text("Local time in")).to_be_visible()))
    check("smart tips are listed", lambda: expect(page.locator("section[aria-label='Smart tips'] li").first).to_be_visible(timeout=30000))
    check("day map renders with the route list", lambda: (expect(page.locator("section[aria-label='Day route'] .maplibregl-canvas")).to_be_visible(timeout=20000), expect(page.locator("section[aria-label='Day route'] ol li").first).to_be_visible()))
    def switch_day():
        page.locator("section[aria-label='Day route']").get_by_role("button", name=re.compile("^Day 2")).click()
        expect(page.locator("section[aria-label='Day route'] h2")).to_contain_text("Day 2")
    check("day switcher changes the map day", switch_day)
    added = {}
    def add_rec():
        card = page.locator("section[aria-label='Recommended places'] article").first
        card.scroll_into_view_if_needed(); added["name"] = card.locator("h3").inner_text()
        card.get_by_role("button", name="Add to trip").click()
        expect(page.locator("section[aria-label='Recommended places']")).not_to_contain_text(added["name"], timeout=90000)
    check("a recommendation can be added to the trip", add_rec)
    def rec_details():
        page.locator("section[aria-label='Recommended places'] article").first.get_by_role("button", name="Details", exact=True).click()
        expect(page.get_by_role("dialog")).to_be_visible(); page.keyboard.press("Escape"); expect(page.get_by_role("dialog")).to_have_count(0)
    check("recommendation details open and close with Escape", rec_details)
    def food_details():
        page.locator("section[aria-label='Recommended restaurants'] button").first.click()
        expect(page.get_by_role("dialog")).to_be_visible(); page.get_by_role("button", name="Close details").click(); expect(page.get_by_role("dialog")).to_have_count(0)
    check("restaurant suggestion opens details", food_details)
    def refresh_guide():
        page.get_by_role("button", name="Refresh live guide").click(); expect(page.get_by_text(re.compile("^Updated "))).to_be_visible(timeout=30000)
    check("refresh button reloads live data", refresh_guide)
    page.screenshot(path=os.path.join(SHOTS, "check_guide.png"))

    print("Workspace: itinerary")
    tab("itinerary").click()
    check("added place appears in the itinerary", lambda: expect(page.locator("#tab-panel")).to_contain_text(added.get("name", "###"), timeout=15000))
    def pace():
        page.get_by_role("button", name="relaxed", exact=True).click(); not_busy()
        expect(page.locator("#tab-panel").get_by_role("button", name="relaxed", exact=True)).to_have_attribute("aria-pressed", "true")
        page.get_by_role("button", name="balanced", exact=True).click(); not_busy()
    check("pace can be changed and changed back", pace)
    def reorder():
        first = page.locator("button[aria-label^='Move '][aria-label$=' later']:not([disabled])").first
        label = first.get_attribute("aria-label"); first.click(); not_busy()
        expect(page.locator(f"button[aria-label=\"{label}\"]")).to_have_count(1)
    check("a stop can be moved later", reorder)
    def stop_details():
        page.locator("button[aria-label^='Details for ']").first.click()
        d = page.get_by_role("dialog"); expect(d).to_be_visible(); expect(d.get_by_text("Opening hours")).to_be_visible(); page.keyboard.press("Escape")
    check("stop details dialog shows hours", stop_details)
    def remove_stop():
        n = page.locator("button[aria-label^='Remove ']").count()
        page.locator("button[aria-label^='Remove ']:not([disabled])").last.click(); not_busy()
        expect(page.locator("button[aria-label^='Remove ']")).to_have_count(n - 1, timeout=20000)
    check("a stop can be removed", remove_stop)
    def add_place():
        chip = page.locator("#tab-panel .card:has-text('Add a place') button").first
        chip.click(); page.get_by_role("dialog").get_by_role("button", name="Add to my trip").click()
        expect(page.get_by_role("dialog")).to_have_count(0, timeout=60000)
    check("a place can be added from the Add a place list", add_place)
    def disruption():
        page.get_by_label("Delay in hours").fill("4"); page.get_by_role("button", name="Assess impact").click()
        expect(page.get_by_text("New arrival")).to_be_visible(timeout=20000)
        page.get_by_role("button", name="Choose", exact=True).first.click(); expect(page.get_by_text("Approval needed")).to_be_visible()
        page.get_by_role("button", name="Reject", exact=True).click(); expect(page.get_by_text("Rejected. Nothing changed.")).to_be_visible()
    check("delay assessment proposes options and can be rejected", disruption)

    print("Workspace: other tabs")
    tab("map").click()
    def map_tab():
        expect(page.locator("#tab-panel .maplibregl-canvas")).to_be_visible(timeout=20000)
        page.locator("#tab-panel").get_by_role("button", name="Day 2", exact=True).click()
        page.locator("#tab-panel ol button").first.hover(); expect(page.locator(".pl-pin.is-active")).to_have_count(1)
        page.get_by_role("button", name="List", exact=True).click(); expect(page.locator("#tab-panel ul.card li").first).to_be_visible()
        page.get_by_role("button", name="Map", exact=True).click(); expect(page.locator("#tab-panel .maplibregl-canvas")).to_be_visible(timeout=20000)
    check("map: day switch, pin highlight from the list, list/map toggle", map_tab)
    check("map loads the road route", lambda: expect(page.locator("#tab-panel").get_by_text("Road route:")).to_be_visible(timeout=20000))
    tab("travel").click()
    def travel():
        page.locator("#tab-panel").get_by_role("button", name=re.compile("route, map")).first.click()
        expect(page.locator("#tab-panel article ol li").first).to_be_visible()
        page.locator("#tab-panel").get_by_role("button", name="Fastest", exact=True).click()
        page.locator("#tab-panel").get_by_role("button", name="Choose this").first.click()
        expect(page.locator("#tab-panel").get_by_role("status").filter(has_text="Updated.")).to_be_visible(timeout=60000)
    check("travel: expand steps, sort, choose another way", travel)
    tab("hotels").click()
    def hotels():
        page.locator("#tab-panel").get_by_role("button", name="Why this score?").first.click(); expect(page.get_by_text(re.compile("weight \\d+%")).first).to_be_visible()
        page.locator("#tab-panel").get_by_role("button", name="Choose", exact=True).first.click()
        expect(page.get_by_text("Updating…")).to_have_count(0, timeout=90000); expect(page.locator("#tab-panel").get_by_text("Your stay")).to_have_count(1)
        page.locator("#tab-panel button[aria-label^='Details for ']").first.click(); expect(page.get_by_role("dialog")).to_be_visible(); page.keyboard.press("Escape")
    check("hotels: explain score, choose another hotel, open details", hotels)
    tab("areas").click()
    check("areas explains the scoring", lambda: expect(page.locator("#tab-panel").get_by_text("Data used")).to_be_visible())
    tab("budget").click()
    def budget():
        expect(page.locator("#tab-panel").get_by_text("per person")).to_be_visible(timeout=20000)
        page.get_by_label("Amount").fill("750"); page.get_by_role("button", name="Add expense").click()
        expect(page.locator("#tab-panel").get_by_text("₹750").first).to_be_visible(timeout=15000)
        expect(page.locator("#tab-panel").get_by_text("Settle up")).to_be_visible()
    check("budget: breakdown loads, expense is added and split", budget)
    tab("safety").click()
    check("safety shows emergency contacts", lambda: expect(page.locator("#tab-panel").get_by_text("Emergency contacts")).to_be_visible())
    tab("bookings").click()
    check("bookings lists provider links", lambda: expect(page.locator("#tab-panel a[target=_blank]").first).to_have_attribute("href", re.compile("^https://")))
    tab("agents").click()
    check("agents tab renders", lambda: expect(page.locator("#tab-panel")).to_contain_text(re.compile("agent", re.I)))

    print("TRIP assistant")
    def chat():
        page.get_by_role("button", name="Open TRIP assistant").click()
        panel = page.locator("section[aria-label='TRIP assistant chat']"); expect(panel).to_be_visible()
        panel.get_by_role("button", name="Voice settings").click(); expect(panel.get_by_text("Voice language")).to_be_visible(); panel.get_by_role("button", name="Voice settings").click()
        panel.get_by_label("Message TRIP").fill("open budget"); page.keyboard.press("Enter")
        page.wait_for_url("**tab=budget**")
        before = panel.locator("div.rounded-bl-md").count()
        panel.get_by_label("Message TRIP").fill("Explain today's weather and pollution"); page.keyboard.press("Enter")
        expect(panel.get_by_role("status").filter(has_text="Working")).to_have_count(0, timeout=120000)
        assert panel.locator("div.rounded-bl-md").count() > before, "no reply bubble"
        page.keyboard.press("Escape"); expect(panel).to_have_count(0)
    check("chat: settings, navigation command, a real question, Escape closes", chat)
    def cheaper():
        page.goto(BASE + "/workspace?tab=guide"); expect(page.get_by_text("Estimated total").first).to_be_visible(timeout=30000)
        with page.expect_response(lambda r: r.url.endswith("/api/chat"), timeout=180000) as resp:  # the replan can finish in well under a second
            page.get_by_role("button", name="Make it cheaper").first.click()
        assert resp.value.status == 200, f"chat returned {resp.value.status}"
        expect(page.get_by_text("TRIP's agents are on it")).to_have_count(0, timeout=30000)
        expect(page.get_by_text("Estimated total").first).to_be_visible()
    check("quick request 'Make it cheaper' replans", cheaper)

    print("Discover")
    def discover():
        page.goto(BASE + "/discover"); page.get_by_role("button", name="Paris", exact=True).click()
        expect(page.locator("article[role=button]").first).to_be_visible(timeout=60000)
        expect(page.get_by_text("Weather now")).to_be_visible(timeout=30000)
        page.locator("article[role=button]").first.click(); expect(page.get_by_role("dialog")).to_be_visible(); page.get_by_role("button", name="Close details").click()
        page.locator("article[role=button] input[type=checkbox]").nth(0).check(); page.locator("article[role=button] input[type=checkbox]").nth(1).check()
        expect(page.get_by_text("Comparison")).to_be_visible(); page.get_by_role("button", name="Clear", exact=True).click(); expect(page.get_by_text("Comparison")).to_have_count(0)
        page.get_by_label("Sort results").select_option("rating")
        page.get_by_role("button", name="Map", exact=True).click(); expect(page.locator(".maplibregl-canvas")).to_be_visible(timeout=20000)
        page.get_by_role("button", name="List", exact=True).click()
        page.get_by_role("tab", name="restaurants").click(); expect(page.locator("article[role=button]").first).to_be_visible(timeout=60000)
        page.get_by_role("tab", name="hotels").click(); expect(page.locator("article[role=button]").first).to_be_visible(timeout=60000)
        expect(page.locator("article[role=button]").first).to_contain_text("/night")
    check("discover: search, live panel, details, compare, sort, map, restaurants, hotels", discover)
    def autocomplete():
        page.goto(BASE + "/discover"); page.locator("#dc-city").click(); page.keyboard.type("Lisb", delay=60)
        expect(page.get_by_role("option").first).to_be_visible(timeout=10000); page.keyboard.press("ArrowDown"); page.keyboard.press("Enter")
        expect(page.locator("#dc-city")).to_have_value(re.compile("Lisb", re.I))
    check("place search suggests as you type", autocomplete)

    print("Ways to travel")
    def transport():
        page.goto(BASE + "/transport"); page.get_by_role("button", name="Compare", exact=True).click()
        expect(page.get_by_role("alert")).to_contain_text("Enter both")
        page.fill("#tr-from", "Delhi"); page.keyboard.press("Escape"); page.fill("#tr-to", "Jaipur"); page.keyboard.press("Escape")
        page.get_by_role("button", name="Swap from and to").click(); expect(page.locator("#tr-from")).to_have_value("Jaipur")
        page.get_by_role("button", name="Swap from and to").click()
        page.get_by_role("button", name="Compare", exact=True).click()
        expect(page.get_by_role("heading", level=2).filter(has_text="Jaipur")).to_be_visible(timeout=90000)
        page.get_by_role("button", name=re.compile("route, map")).first.click(); expect(page.locator("article ol li").first).to_be_visible()
    check("transport: validation, swap, search, expand an option", transport)

    print("My trips and preferences")
    def trips():
        page.goto(BASE + "/trips"); expect(page.get_by_role("listitem").filter(has_text="Updated").first).to_be_visible()
        page.get_by_role("button", name=re.compile("^Delete ")).first.click(); expect(page.get_by_text("Delete this trip for good?")).to_be_visible(); page.get_by_role("button", name="Keep it").click()
        page.get_by_role("button", name="New trip").click(); page.wait_for_url("**/workspace"); expect(page.get_by_role("heading", level=1)).to_have_text("Plan a trip")
        page.goto(BASE + "/trips"); page.get_by_role("button", name="Open", exact=True).first.click(); page.wait_for_url("**/workspace")
        expect(page.get_by_text("Estimated total").first).to_be_visible(timeout=30000)
    check("trips: list, cancel a delete, new trip, reopen a saved trip", trips)
    def reload_keeps():
        page.reload(); expect(page.get_by_text("Estimated total").first).to_be_visible(timeout=30000)
    check("reloading the page keeps the open trip", reload_keeps)
    def profile():
        page.goto(BASE + "/profile"); veg = page.get_by_role("checkbox", name=re.compile("^Vegetarian")); expect(veg).not_to_be_checked()
        veg.check(force=True); page.get_by_role("button", name="packed").click(); page.get_by_role("button", name="Save preferences").click()
        expect(page.get_by_role("status").filter(has_text="Saved")).to_be_visible()
        page.reload(); expect(veg).to_be_checked(timeout=10000)
        veg.uncheck(force=True); page.get_by_role("button", name="balanced").click(); page.get_by_role("button", name="Save preferences").click()
        expect(page.get_by_role("status").filter(has_text="Saved")).to_be_visible()
    check("preferences save and survive a reload", profile)
    def delete_trip():
        page.goto(BASE + "/trips"); expect(page.get_by_role("button", name=re.compile("^Delete ")).first).to_be_visible(); n = page.get_by_role("button", name=re.compile("^Delete ")).count()
        page.get_by_role("button", name=re.compile("^Delete ")).last.click(); page.get_by_role("button", name="Yes, delete").click()
        expect(page.get_by_role("button", name=re.compile("^Delete "))).to_have_count(n - 1, timeout=15000)
    check("a trip can be deleted", delete_trip)

    print("Misc")
    check("unknown address shows the not-found page", lambda: (page.goto(BASE + "/no-such-page"), expect(page.get_by_text("took a wrong turn")).to_be_visible()))
    def nav_links():
        for name, path in (("Discover", "/discover"), ("Ways to travel", "/transport"), ("My trips", "/trips"), ("Plan", "/workspace")):
            page.get_by_role("navigation", name="Main").get_by_role("link", name=name, exact=True).click(); page.wait_for_url("**" + path + "**")
        page.get_by_role("link", name="Plarno.ai home").first.click(); expect(page).to_have_url(re.compile("/$"))
    check("header navigation and logo link", nav_links)
    def signout():
        page.get_by_role("button", name="Sign out").click(); expect(page.get_by_role("link", name="Get started", exact=True)).to_be_visible()
        page.goto(BASE + "/trips"); page.wait_for_url("**/auth")
    check("sign out, and protected pages then ask to sign in", signout)
    def signin():
        page.fill("#au-email", email); page.fill("#au-pw", "password123"); page.get_by_role("button", name="Sign in", exact=True).last.click(); page.wait_for_url("**/workspace")
    check("sign back in", signin)
    ctx.close()

    print("Mobile")
    m = b.new_context(viewport={"width": 390, "height": 800}, is_mobile=True, has_touch=True)
    mp = m.new_page(); watch(mp, "mobile"); mp.set_default_timeout(15000)
    def mobile():
        mp.goto(BASE + "/"); mp.get_by_role("button", name="Open menu").click()
        expect(mp.get_by_role("navigation", name="Mobile").get_by_role("link", name="Discover")).to_be_visible()
        mp.get_by_role("navigation", name="Mobile").get_by_role("link", name="Discover").click(); mp.wait_for_url("**/discover")
        expect(mp.get_by_role("navigation", name="Mobile")).to_have_count(0)
        for path in ("/", "/discover?city=Paris", "/transport", "/auth"):
            mp.goto(BASE + path); mp.wait_for_timeout(1500)
            sw, cw = mp.evaluate("document.documentElement.scrollWidth"), mp.evaluate("document.documentElement.clientWidth")
            assert sw <= cw + 1, f"horizontal overflow on {path}: {sw}>{cw}"
        mp.get_by_role("button", name="Open TRIP assistant").click(); expect(mp.locator("section[aria-label='TRIP assistant chat']")).to_be_in_viewport()
    check("mobile: menu opens and closes on navigation, no sideways scroll, chat fits", mobile)
    mp.screenshot(path=os.path.join(SHOTS, "check_mobile_chat.png"))
    b.close()

ok = sum(1 for r in results if r[0])
print(f"\n{ok}/{len(results)} checks passed")
uniq = list(dict.fromkeys(problems))
print(f"browser problems: {len(uniq)}"); [print("  ", u) for u in uniq[:30]]
sys.exit(0 if ok == len(results) and not uniq else 1)
