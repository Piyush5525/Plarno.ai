# Replacing mocks with real providers

Rule: a provider returns data with `provenance.kind` set honestly (`live` only for real-time responses; `cached` with the original timestamp). Do not hardcode secrets; read from environment.
Check each provider's terms, pricing and usage limits before integrating. Nothing below has been integrated or tested.

| Capability | Today | Where to plug in | Candidates (verify access/terms) |
|---|---|---|---|
| Intercity transport | `SimulatedTransportProvider` in `services/transport.py` (deterministic formulas) | implement `legs(a, b, date) -> list[leg]` with the same leg fields | Flight GDS/aggregator APIs, IRCTC-partner APIs, bus aggregator APIs, cab APIs (most require commercial agreements) |
| Hotels / supplier inventory | `data/seed.py` + upload endpoint | replace `catalog.hotels()` / `_listings()` | Supplier APIs; the matching engine already takes normalized listings |
| Routing / ETA | haversine × 1.35 (`services/geo.py`) | `geo.route()` | OSRM / Valhalla / GraphHopper / Google Directions. Do not use the public OSRM demo server in production |
| Map tiles | OSM raster tiles in `MapView` | `components/ui.tsx` style | A tile provider (MapTiler, Stadia, self-hosted); OSM's tile policy forbids heavy use |
| Air quality | simulated per neighbourhood | `services/safety.py` | CPCB, OpenAQ, IQAir |
| Weather | not connected | `safety.destination_safety()` | Open-Meteo |
| Safety advisories | static text | `data/seed.SAFETY_ADVISORY` | Government advisory feeds (e.g. MEA, travel.state.gov) |
| Nearby hospitals/police/fuel/metro | counts in seed | add Overpass lookups | OpenStreetMap Overpass API |
| Attractions/restaurants/photos | seed; photos not connected (cover placeholders say so) | `catalog.py`, `Cover` component | OSM, Wikidata/Wikimedia Commons (check each licence), Foursquare/Google Places (paid) |
| Booking | `MockBookingProvider` in `services/booking.py` (SIM- references) | implement `confirm()` / `cancel()`; keep the approval + idempotency flow | Supplier booking APIs. Payments must go through a PCI-compliant gateway; never store card data |
| LLM | rules NLU (`agents/nlu.py`) | add a provider behind `PLARNO_LLM` that fills `extract()`'s dict and rewrites `compose_reply()` text without changing numbers | Anthropic API (see claude-api docs), others |
| Voice | Browser Web Speech API (`components/voice.ts`) | implement `VoiceProvider` | Cloud STT/TTS |
