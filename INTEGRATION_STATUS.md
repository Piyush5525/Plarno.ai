# Integration status (verified 2026-11-11 from this machine)

Legend: ✅ verified with real calls · ⚠ works with limits · ❌ not working / not integrated

| Provider | Status | Evidence / limits |
|---|---|---|
| Gemini | ✅ | `gemini-flash-lite-latest` ~3 s. `gemini-2.5-flash` returns 404 ("no longer available to new users") so the alias is used. Extracts trip fields the rules miss (e.g. "couple, long weekend, ~25k, vegetarian"); output is whitelisted/validated; cached 24h. Falls back to rules on failure. |
| OpenWeather | ✅ | Live current weather in Safety tab and TRIP "weather" tool (cached 15 min). |
| AQICN | ✅ | Live AQI from nearest station (e.g. Sri Aurobindo Marg for Hauz Khas), cached 30 min. Station may be km away: labelled in UI. |
| Mapbox | ✅ | Public token: raster tiles in the map and `/api/route/directions` (cached 1h). Itinerary timing itself still uses the haversine estimate. |
| SerpApi Google Flights | ✅ ⚠ | Real fares returned (BOM→DEL IndiGo etc.). Free plan: 250 searches/month. Guarded by a persistent 6h cache + the shared daily SerpApi cap (default 40). Runs for world trips that have an origin, and on the Flights page when "live fares" is ticked. `SERP(GOOGLE FLIGHT)_API` is the same key as `SERP_API`. Search only; booking link goes to Google Flights. |
| SerpApi Google Maps (places) | ✅ | Real attractions/restaurants anywhere (Paris, Tokyo verified): coordinates, rating, review count, weekday opening hours, photos, website, price level. Cached 30 days; shares the daily SerpApi cap (`PLARNO_SERP_DAILY_CAP`, default 40). Ticket prices are NOT provided: shown as unverified. |
| SerpApi Google Hotels | ✅ | Real hotels with nightly rate for the searched dates (in INR), rating, photos, amenities, booking link, nearby transit. Cached 12 h. Search-only: booking happens on the provider site. |
| Mapbox Geocoding | ✅ | Primary place resolver and as-you-type suggestions (accurate for small towns, e.g. Kishangarh, Rajasthan). Results kept only in a short in-memory cache (temporary-geocoding terms). |
| Photon (OpenStreetMap) | ✅ | As-you-type search for towns **and colleges, universities, stations, airports** (Mapbox's town index has no "Manipal" and fuzzy-matches to look-alikes such as Mahipal). Merged with Mapbox results; irrelevant fuzzy matches are dropped. Public demo server (`photon.komoot.io`): fair use only, so results are cached 10 min and throttled; set `PHOTON_URL` to a self-hosted instance for heavy use. Data © OpenStreetMap contributors (ODbL). |
| Nominatim geocoding | ✅ fallback | Used when Mapbox is unavailable; weak for small towns, so not primary. Cached 90 days. |
| StayingAPI | ⚠ sandbox | Key is `stay_test_…` (Free/Sandbox, 300 credits, 30 req/min). It returns **fixed fixtures regardless of the query** (a Croatian apartment for "New Delhi"). The adapter flags these as simulated and they are excluded from recommendations. Needs a `stay_live_` key for real hotel data. |
| OpenStreetMap Overpass | ❌ currently unreachable | Both public mirrors time out from this network, even their `/status` pages (checked repeatedly). Adapter, normalisation, 7-day cache, circuit breaker and fallback are implemented and unit-tested with injected payloads, but **no live Overpass response has been received**. The app falls back to labelled demo data. |
| Qrail | ❌ not integrated | No public API named "Qrail" found; host/auth/endpoints unknown. Need docs URL. |
| RapidAPI | ❌ not integrated | The key does not reveal which API hosts are subscribed. Need the host names (e.g. `xxx.p.rapidapi.com`). |
| OSRM / openrouteservice / GTFS | ❌ not integrated | Mapbox covers road routing for now. |

Secrets: read from `.env` server-side only (`.gitignore` excludes it); `/api/providers/health` and `/api/config` are tested not to leak key values.

## Quota note
SerpApi free plan = 250 searches/month. A new city costs ~4-5 searches (attractions, interest queries, restaurants, hotels, + 1 flight search if an origin is given); repeat requests are served from the persistent cache. The shared daily cap prevents runaway usage; when it trips, features say so and fall back (no fabricated data).
