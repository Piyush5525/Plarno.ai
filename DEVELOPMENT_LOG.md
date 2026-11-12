# Development log

## Cycle 1 — foundation (backend + frontend)
Built: FastAPI backend, 14-agent architecture, deterministic services, SQLite persistence, React/R3F/MapLibre frontend.
Tested: 21→25 pytest tests; HTTP smoke test of the 3 demo scenarios.
Bugs found → fixed: "make it cheaper" chose a pricier hotel (selection ignored a strict ceiling); cab fares multiplied per traveller (now per vehicle); budget conflict downgraded the stay before relaxing transport (now transport first, with an explicit note); rejecting a supplier match did not split transitive clusters (now cannot-link constraints); delay reported for a mode not in the trip (now asks which journey).

## Cycle 2 — rename + live data
Renamed TripPilot → Plarno.ai everywhere (env vars now `PLARNO_*`, DB `plarno.db`, UI, docs). Live AQICN + OpenWeather + Mapbox integrated with caching and labelled fallbacks.

## Cycle 3 — provider layer + browser testing
Built: persistent cache (stale-if-error), rate limiter, daily quota guard, circuit breaker; Overpass, SerpApi flights, StayingAPI (sandbox-aware), Gemini providers; TRIP tool intents; `/api/providers/health`.
Tested: 37 pytest tests (12 new, provider layer with injected payloads/monkeypatched outages); Playwright suite `e2e/ui_test.py`: 33 checks incl. register → plan → tabs → hotel change → itinerary edit → TRIP tool prompts → booking approval → reload/reopen → live flights → mobile overflow; 0 console/network errors.
Bugs found by running it → root cause → fix:
1. Reloading the page lost the open trip (state only in memory; and my "save trip id" effect wiped the stored id on mount before restore read it) → persist id, restore after login, never clear on mount.
2. TRIP's client-side nav shortcuts hijacked "Find restaurants around my hotel" / "Show the best route…" so the real tools never ran → shortcuts restricted to bare "open X" commands; regex escaping bug (`\s` lost in a JS string) found by testing the actual pattern.
3. First restaurant lookup stalled ~25 s when Overpass was down (2 mirrors × 12 s) → 6 s timeouts + circuit breaker (instant afterwards).
4. Visual: cover label overlapped the title on every day card; landing header muddy gray; tiny orb eyes; fictional demo restaurants not flagged → fixed; meals now say "DEMO venue".
5. Gemini 404 (`gemini-2.5-flash` retired for new users) → configurable alias model.
6. Staying key is sandbox fixtures (Croatia apartment for a Delhi query) → quarantined.
Test-quality fixes: assertions that matched earlier chat text (false positives), races on async renders, case-sensitive CSS-transformed labels.

## Remaining limitations / next priorities
1. Overpass unreachable here: need a working mirror/self-hosted instance, then wire OSM restaurants/attractions/hotels into itinerary + neighbourhood scoring (real hospitals/transit counts).
2. Real hotel inventory: needs a `stay_live_` Staying key (or another provider). Hotels remain simulated demo data.
3. Qrail and RapidAPI need docs/host names. Trains/buses remain simulated.
4. Gemini currently used for understanding and (not yet wired into UI) grounded Q&A; replies are deterministic text.
5. Itinerary timing uses haversine×1.35; Mapbox directions endpoint exists but is not yet used for day timing.
6. Voice (mic/TTS) not exercised in automated tests (headless browser has no mic); 3D orb only visually checked in screenshots.
7. Only Delhi has curated data; other cities only in the transport graph.
8. Postgres/PostGIS/pgvector/Redis not used (SQLite + in-process cache).

## Cycle 4 — worldwide + redesign (this cycle)
Built: worldwide planning (Nominatim geocoding → SerpApi Google Maps/Hotels/Flights → scoring → itinerary → budget → safety), airport table (116 cities), free-text place extraction + Gemini fill, weekday opening-hours parser (itinerary waits for opening / moves closed-day sights / flags), search-only booking links for world trips, `/api/world/discover`, Mapbox road routes in the Map tab with numbered pins, new design system, new cute 3D bot (8 animation states), trip-builder form, greeting bubble, richer chat panel with voice controls, Discover (worldwide, filters/sort/compare/map), Flights page for any city pair.
Tested: 48 pytest tests (new: world planning from real response shapes, hours parser/schedule, tools on provider data, unknown places); browser E2E 37/37 (journey: builder → sign-up → resumed planning → tabs → hotel change → itinerary edit → 6 TRIP tool prompts → persistence → Discover → live flights → mobile); crawler over every page/control on desktop+mobile (see below).
Bugs found by looking at the product → root cause → fix:
1. Real-data quality: Tokyo "temples" query returned mosques (ambiguous query) → "religious landmarks and places of worship"; Paris day 4 chose statues (score over-weighted keyword matches vs popularity) → capped match bonus, popularity weighted, penalties for low-review/statue-type.
2. Vite kept an old Tailwind config → whole app blank (500 on CSS): restart needed after tailwind.config changes (documented).
3. Itinerary showed "Closed · Opens 10 AM" for a stop scheduled at 09:18 (the Google "open now" snapshot is not a weekday schedule) → parse real weekday hours; wait for opening; move closed-day sights; flag conflicts.
4. Greeting bubble covered the "Plan my trip" button → auto-dismiss (11 s), on scroll/keypress/click.
5. Flag emoji render as "FR/JP" on Windows → removed. Logo "Plarno .ai" gap (flex gap between text nodes) → fixed.
6. Floating assistant button moved continuously (hard to click; flaky automation) → stationary button, bot animates inside.
7. e2e helper false negatives (text inserted before chips; async lazy routes) fixed in tests.

### Cycle 4 verification results
- Backend: **50 pytest tests pass** (offline; provider payloads injected in real response shapes).
- Browser journey `e2e/ui_test.py`: **37/37**, 0 console/network errors.
- Crawler `e2e/crawl.py` (every control on 16 pages x desktop+mobile, 369 clicks): **0 issues** after fixes. No unnamed controls, alt-less images, duplicate ids or missing h1.
- Found by the crawler and fixed: (1) screen-reader-only text inside tab buttons stretched mobile pages to 758px (parent not `relative`); (2) Discover cards 412px in a 390px column (implicit grid column sized to content; added `grid-cols-1` + `min-w-0`); (3) many sub-30px tap targets (reorder arrows, links, chips, close buttons) enlarged.
- Found by reading the UI: Profile preferences were saved but never used -> now seed every new trip (tested); provider health said "ready" for an unreachable provider -> now reports real last outcome; "two of us" / "we are three" / bare "2" were not understood as party size -> fixed (tested).
- Not verifiable here: microphone/speech (headless browser has no mic), actual audio output, real GPU rendering of the 3D bot (verified via software-GL screenshots).

## Cycle 5 — door-to-door travel options, small towns, autocomplete, details
Built: route-options engine (`services/routes.py`): live Google Flights between the NEAREST airports of any two places + cab transfers at both ends, direct cab, bus, train; labels (cheapest / fastest / most comfortable / best value / most convenient), travel allowance = 45% of the budget, "within budget" vs "stretch (+₹X, saves Yh)" tiers; nearest-airport lookup (116 airports geocoded). "I live here" day-trips mode (home base, no hotel/travel, radius widens 60→120→200 km for small towns, lunch+dinner every day). Travel tab, Ways-to-travel page, `/api/routes/options`, `/api/trips/{id}/journey`. TRIP answers fare / cab / "ways to travel" questions from the actual options and can switch the plan to the cheapest/fastest/most comfortable. Mapbox-backed place autocomplete + resolver, place detail dialog (photos, weekday hours, address/phone, map, directions, add-to-trip / choose hotel), cab fare per stop and per day.
Tests: 67 pytest, e2e/ui_test.py 37/37, e2e/ui_features.py 33/33, crawler 363 clicks 0 issues.
Bugs found (root cause → fix):
1. "Madhya Pradesh" for a small town: Nominatim returns a park/station first for "Kishangarh" and my filter skipped to a state boundary; fallback also used the state name with the village's coordinates → Mapbox geocoder primary, Nominatim fallback fixed (and regions flagged `broad`, planner asks for a town).
2. The language model "corrected" the user's typed town to a bigger nearby city → typed places always beat the model; the model only fills gaps.
3. "…in Kishangarh. Plan a trip" captured "Kishangarh." (period) → sentence-boundary aware.
4. "4 day trip" matched my home-town detector → narrowed to genuinely home-specific phrases.
5. Explicit "switch to the fastest option" was overridden by the budget fallback → explicit choices are never auto-relaxed; instructions vs questions distinguished.
6. Suggestion dropdown re-opened late over other fields → open only while focused.
7. Quota cap shown as "provider unavailable" and tripped the outage breaker → own error, doesn't open the breaker; default cap 100/day (SerpApi plan has 181 + 1000 extra credits).
8. Patch-script escape corruption (`\b` became a backspace char, `\n` literal) found by tests/scan; scanned all sources for control chars.
Limitations: bus/train/cab figures are distance-based ESTIMATES (no live inventory; flagged "estimated" everywhere); Qrail/RapidAPI still not integrated; ticket prices not provided by Google Maps; voice not testable headless.

## Cycle 6 — redesign, live guide, interactive TRIP (2026-11-12)
Built: new design system (Bricolage Grotesque / Plus Jakarta Sans / Instrument Serif, lucide icons instead of emoji, refined palette, motion throughout: page and tab transitions, scroll reveals, count-up numbers, sliding tab pills, animated bars); new landing page with live city readings; **Live guide** tab (`services/guide.py`, `/api/trips/{id}/guide`, `/api/live`): weather, AQI, local clock, daylight, 5-day forecast matched to trip days, day map, smart tips with one-click fixes, ranked recommendations with reasons, Gemini briefing phrased from those facts; maps with highlightable pins linked to the stop list, a dot travelling the day's route, locate-me and scale controls; TRIP bot: follows the cursor across the page, click tricks (jump, spin, wink, dance, hearts, nod, peek), drag to turn (backpack on the back), naps when idle, scarf, orbiting paper plane; chat with formatted replies, quick actions, per-page hints, new-trip button; deterministic packing advice from the forecast; Discover with live conditions and map/list linking; redesigned Auth, Trips, Preferences, Ways to travel; 404 page.
Tests: 75 pytest (8 new in `tests/test_guide.py`), `e2e/site_check.py` 47/47 twice, crawler 293 clicks on desktop + mobile with no console errors, exceptions, blank pages or overflow.
Bugs found (root cause → fix):
1. Trip tabs froze after toggling the map's List/Map view: `AnimatePresence mode="wait"` never finished the exit of a panel containing a shared-layout element → panels now use an enter-only transition.
2. Hotels tab called `useState` after an early return (hook-order error when switching between a home-base and a hotel trip) → hooks moved above the return.
3. "Choose this" on the Delhi demo's travel options always failed with 422 (the endpoint only knows world route options) → the button is shown only where it works.
4. Place details opened inside an animated container would be positioned against it, not the screen → rendered through a portal; focus is trapped in the dialog.
5. Cancelling a demo booking used a blocking browser `confirm()` and left the approval pending if dismissed → inline confirm with an explicit "Keep booking".
6. Every map fetched `/api/config`, and place inputs looked up suggestions when the app (not the user) set their value → config fetched once, lookups only while typing. Default rate limit raised 120 → 300/min.
7. "What should I pack?" answered "I don't have that data" → answered from the forecast, AQI and the plan's stops.
8. The whole layout was replaced by "Loading…" while a page chunk loaded, and the 3D engine was in the first download → per-page suspense, bot loaded on demand, vendor chunks split.
Not verifiable here: microphone/speech and audio output (headless browser), real-GPU rendering of the bot (checked through software-GL screenshots).
### Cycle 6 follow-up — searching for colleges
Reported: searching for a college (e.g. "manipal") returned look-alike villages (Mahipal, Fanipal, Manupal). Root cause: suggestions asked Mapbox for towns/regions only; Manipal is not in its town index and it fuzzy-matches similar names, and colleges are points of interest that were excluded by design.
Fix: Photon (OpenStreetMap) added beside Mapbox for suggestions and for the planner's own place lookup (`providers/photon.py`, `providers/suggest.py`, `providers/geocode.py`). Towns first, then colleges/stations/airports tagged in the dropdown; abbreviations work ("iit bombay", "mit manipal"); hospitals are hidden unless asked for; Mapbox's non-matching guesses are dropped. A picked college resolves to its own coordinates, but the planning name is the town around it, so sights and hotels are searched in the right area.
Found while checking: "Goa" resolved to Goathland, UK (Mapbox lists the state first, the code skipped to the first town) → an exactly-typed region is kept; the planner then asks for a town in Goa, as designed. The nearest-airport table had no airport for most of India (Manipal → Goa, 234 km) → 37 Indian cities added (Manipal → Mangaluru, 49 km).
Tests: 84 pytest (9 new in `tests/test_places.py`); `e2e/site_check.py` 47/47.
Limits: the Photon demo server has no SLA (Mapbox still works if it is down); the airport table uses city-centre coordinates, so the distance shown is to the airport's city, not the terminal.