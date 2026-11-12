"""Click-everything crawler + accessibility audit. For desktop and mobile: signs up, loads a (cached) Paris trip, then on every page clicks each
visible, safe control, and records console errors, uncaught exceptions, failed requests, blank pages and horizontal overflow.
Also audits: images without alt, buttons/links/inputs without an accessible name, duplicate ids, missing <h1>, tiny tap targets (mobile).
Skips: sign-out, delete, external links, destructive/consequential buttons.   Run: python e2e/crawl.py"""
import os, sys, time, json
from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://localhost:5173")
SKIP = ("sign out", "delete", "request cancellation", "approve", "reject", "book ↗", "view & book", "open in", "stop", "add expense", "send", "plan my trip", "search", "compare", "upload", "save")
issues, clicks, audits = [], 0, []

AUDIT_JS = """() => {
  const out = [];
  const name = el => (el.getAttribute('aria-label') || el.getAttribute('title') || el.innerText || el.getAttribute('alt') || (el.labels && el.labels[0] && el.labels[0].innerText) || el.getAttribute('placeholder') || '').trim();
  document.querySelectorAll('img').forEach(i => { if (!i.hasAttribute('alt')) out.push('img without alt: ' + (i.src||'').slice(0,60)); });
  document.querySelectorAll('button, a[href], [role=tab], input:not([type=hidden]), select, textarea').forEach(e => {
    const r = e.getBoundingClientRect(); if (r.width === 0 || r.height === 0 || getComputedStyle(e).visibility === 'hidden') return;
    if (!name(e)) out.push('no accessible name: <' + e.tagName.toLowerCase() + '> ' + (e.className||'').toString().slice(0,50));
  });
  const ids = {}; document.querySelectorAll('[id]').forEach(e => { ids[e.id] = (ids[e.id]||0)+1; }); Object.entries(ids).forEach(([k,v]) => { if (v>1) out.push('duplicate id: '+k); });
  if (!document.querySelector('h1')) out.push('page has no <h1>');
  return out;
}"""

def audit(page, label, mobile=False):
    for a in page.evaluate(AUDIT_JS): audits.append((label, a))
    if mobile:
        small = page.evaluate("""() => [...document.querySelectorAll('button, a[href], input, select')].filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && (r.height < 30 || r.width < 30) && getComputedStyle(e).visibility !== 'hidden' && !e.closest('.maplibregl-ctrl, .maplibregl-map, [class*=sr-only]'); }).map(e => (e.innerText || e.getAttribute('aria-label') || e.tagName).slice(0, 30) + ' ' + Math.round(e.getBoundingClientRect().width) + 'x' + Math.round(e.getBoundingClientRect().height))""")
        for s in small[:6]: audits.append((label, 'tap target <30px: ' + s))

def crawl_page(page, path, label, mobile=False):
    global clicks
    page.goto(BASE + path); page.wait_for_timeout(1800)
    body = page.inner_text("body")
    if len(body.strip()) < 40: issues.append((label, "BLANK PAGE", path))
    sw, cw = page.evaluate("document.documentElement.scrollWidth"), page.evaluate("document.documentElement.clientWidth")
    if sw > cw + 1: issues.append((label, f"horizontal overflow {sw}>{cw}", path))
    audit(page, label, mobile)
    # one pass in the page: indexes of visible, enabled, safe controls (avoids slow per-element round trips)
    sel = "main button, main [role=tab], main input[type=checkbox], main summary, header button"
    items = page.evaluate("""([sel, skip]) => [...document.querySelectorAll(sel)].map((e, i) => ({ i, t: ((e.innerText || e.getAttribute('aria-label') || '').trim().toLowerCase()), ok: (() => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && !e.disabled; })() }))
        .filter(x => x.ok && !skip.some(s => x.t.includes(s)))""", [sel, list(SKIP)])
    for it in items[:25]:
        try:
            h = page.locator(sel).nth(it["i"])
            h.click(timeout=1200, no_wait_after=True); clicks += 1
            page.wait_for_timeout(120)
            if page.url.split("?")[0].rstrip("/") != (BASE + path).split("?")[0].rstrip("/"):
                page.goto(BASE + path); page.wait_for_timeout(500)
        except Exception:
            pass  # control re-rendered/detached after an earlier click: normal. Real failures surface as page errors / failed requests
    if len(page.inner_text("body").strip()) < 40: issues.append((label, "BLANK AFTER CLICKS", path))

with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"])
    for label, vp, mobile in (("desktop", {"width": 1366, "height": 900}, False), ("mobile", {"width": 390, "height": 800}, True)):
        ctx = b.new_context(viewport=vp, is_mobile=mobile); page = ctx.new_page()
        page.on("console", lambda m, l=label: issues.append((l, "console.error", m.text[:160])) if m.type == "error" and "tile" not in m.text and "googleusercontent" not in m.text and "favicon" not in m.text and "Failed to load resource" not in m.text else None)
        page.on("pageerror", lambda e, l=label: issues.append((l, "pageerror", str(e)[:160])))
        page.on("response", lambda r, l=label: issues.append((l, f"HTTP {r.status}", r.url[:100])) if r.status >= 500 or (r.status >= 400 and "/api/" in r.url and r.status not in (401, 404, 409, 422)) else None)
        page.goto(BASE + "/auth"); page.click("text=Create an account"); page.fill("#au-name", "Crawler"); page.fill("#au-email", f"crawl{label}{int(time.time())}@example.com"); page.fill("#au-pw", "password123"); page.click("button:has-text('Sign up')")
        page.wait_for_url("**/workspace", timeout=15000)
        page.fill("input[aria-label='Describe your trip']", "Plan a 4 day trip to Paris for two people from Mumbai, start 2026-12-10, budget ₹250,000. Historical places, museums and good food.")
        page.click("button:has-text('Send')"); page.wait_for_selector("text=Estimated total", timeout=180000)
        for path in ["/", "/auth", "/workspace?tab=itinerary", "/workspace?tab=map", "/workspace?tab=hotels", "/workspace?tab=areas", "/workspace?tab=budget", "/workspace?tab=safety", "/workspace?tab=bookings", "/workspace?tab=agents",
                     "/discover", "/discover?city=Paris&tab=attractions", "/discover?city=Paris&tab=restaurants", "/transport", "/trips", "/profile"]:
            crawl_page(page, path, f"{label}:{path}", mobile)
        # TRIP assistant controls
        page.goto(BASE + "/"); page.click("button[aria-label='Open TRIP assistant']"); page.wait_for_timeout(500)
        for sel in ["button[aria-label='Voice settings']", "button[aria-label^='Turn spoken replies']", "button[aria-label='Voice settings']"]:
            try: page.click(sel, timeout=2000); clicks += 1
            except Exception: issues.append((label, "assistant control missing", sel))
        audit(page, f"{label}:assistant-open", mobile)
        sw, cw = page.evaluate("document.documentElement.scrollWidth"), page.evaluate("document.documentElement.clientWidth")
        if sw > cw + 1: issues.append((label, "assistant causes overflow", f"{sw}>{cw}"))
        page.screenshot(path=os.path.join(os.path.dirname(__file__), "shots", f"crawl_{label}_assistant.png"))
    b.close()

print(f"clicked {clicks} controls")
print(f"\nISSUES ({len(issues)}):"); [print("  ", i) for i in issues[:40]]
seen = {}
for l, a in audits: seen.setdefault(a, []).append(l.split(":")[0] + ":" + (l.split(":", 1)[1] if ":" in l else ""))
print(f"\nACCESSIBILITY ({len(seen)} distinct):"); [print("  ", a, "<-", sorted(set(v))[:3]) for a, v in list(seen.items())[:40]]
sys.exit(1 if issues else 0)
