> Superseded by [INTEGRATION_STATUS.md](../INTEGRATION_STATUS.md) and [DEVELOPMENT_LOG.md](../DEVELOPMENT_LOG.md) (current). Kept for the requirement-coverage notes below.

# Status (honest)

## Verified
- Backend: 25 pytest tests pass (auth/RBAC, slot-filling, the 3 demo scenarios, budget conflict resolution, approval/idempotency/cancel, supplier matching + admin review, uploads, validation). Providers run offline in tests.
- Frontend: `tsc` + production build pass. Backend + Vite proxy driven end-to-end over HTTP.
- Live providers verified with real calls: AQICN (air quality), OpenWeather (weather), Mapbox Directions (key accepted).
- Supplier matching on 14 labelled synthetic listings: precision 1.0, recall 1.0, false-merge 0 (tiny set; demonstrates the method only).

## NOT verified
- The UI has not been viewed in a browser by me: 3D TRIP character look/animation, voice (mic/TTS), MapLibre rendering with Mapbox tiles, mobile layout. Treat as untested until you open it.
- No frontend automated tests (voice, 3D, responsiveness).

## Live vs simulated
| Live | Simulated / estimated |
|---|---|
| Air quality (AQICN nearest station), weather (OpenWeather), Mapbox tiles/directions endpoint | Fares, schedules, hotels, rates, restaurants, attractions' fees/hours, noise, safety index, hospitals count, advisories, bookings (SIM-) |

## Not implemented yet
Gemini LLM provider (key present, `rules` NLU is used), SerpAPI Google Flights adapter (key present), Mapbox routing inside itinerary timing (itinerary uses haversine×1.35; `/api/route/directions` is available), photos, Hindi, Postgres/PostGIS/pgvector/Redis (schema in `schema.sql` only), sentence-transformer/image embeddings, drag-and-drop (up/down buttons instead), itinerary export/share, SOS/trusted-contact sharing, reminders/notifications, cities other than Delhi, per-request rate limiting is in-memory.
