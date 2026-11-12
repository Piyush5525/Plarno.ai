-- Production schema sketch (PostgreSQL + PostGIS + pgvector). NOT yet exercised: the dev app runs on SQLite (backend/app/db.py).
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE users(id BIGSERIAL PRIMARY KEY, email CITEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, name TEXT,
  role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user','admin')), preferences JSONB NOT NULL DEFAULT '{}', created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE trips(id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE, title TEXT,
  context JSONB NOT NULL, plan JSONB, created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now());
CREATE INDEX ON trips(user_id);
CREATE TABLE travellers(id BIGSERIAL PRIMARY KEY, trip_id BIGINT REFERENCES trips(id) ON DELETE CASCADE, name TEXT, age_band TEXT, needs JSONB);

CREATE TABLE neighbourhoods(id TEXT PRIMARY KEY, city TEXT, name TEXT, geom geography(Point,4326), boundary geography(Polygon,4326));
CREATE TABLE attractions(id TEXT PRIMARY KEY, name TEXT, category TEXT, geom geography(Point,4326) NOT NULL, neighbourhood_id TEXT REFERENCES neighbourhoods(id),
  visit_minutes INT, fee_inr NUMERIC, opening_hours JSONB, source TEXT NOT NULL, fetched_at TIMESTAMPTZ NOT NULL);
CREATE INDEX ON attractions USING gist(geom);
CREATE TABLE restaurants(id TEXT PRIMARY KEY, name TEXT, cuisine TEXT, geom geography(Point,4326), price_for_two NUMERIC, veg BOOL, vegan BOOL, source TEXT, fetched_at TIMESTAMPTZ);

CREATE TABLE suppliers(id BIGSERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL, reliability REAL, payment_terms TEXT, cancellation_terms TEXT);
CREATE TABLE raw_supplier_listings(id BIGSERIAL PRIMARY KEY, supplier_id BIGINT REFERENCES suppliers(id), external_id TEXT NOT NULL, payload JSONB NOT NULL,
  geom geography(Point,4326), name_embedding vector(384), image_embedding vector(512), ingested_at TIMESTAMPTZ DEFAULT now(), UNIQUE(supplier_id, external_id)); -- immutable originals
CREATE TABLE canonical_properties(id BIGSERIAL PRIMARY KEY, name TEXT, geom geography(Point,4326), created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE property_matches(id BIGSERIAL PRIMARY KEY, canonical_id BIGINT REFERENCES canonical_properties(id), raw_listing_id BIGINT REFERENCES raw_supplier_listings(id),
  score REAL, evidence JSONB, status TEXT CHECK (status IN ('auto','approved','rejected','review')), decided_by BIGINT REFERENCES users(id), decided_at TIMESTAMPTZ);
CREATE TABLE supplier_offers(id BIGSERIAL PRIMARY KEY, canonical_id BIGINT, raw_listing_id BIGINT, room_signature TEXT, price NUMERIC, currency TEXT DEFAULT 'INR',
  meal_plan TEXT, cancellation JSONB, valid_for DATERANGE, fetched_at TIMESTAMPTZ, data_kind TEXT CHECK (data_kind IN ('live','cached','estimated','simulated')));

CREATE TABLE environmental_observations(id BIGSERIAL PRIMARY KEY, neighbourhood_id TEXT, metric TEXT, value REAL, source TEXT NOT NULL, data_kind TEXT NOT NULL, observed_at TIMESTAMPTZ);
CREATE TABLE safety_advisories(id BIGSERIAL PRIMARY KEY, region TEXT, text TEXT, source_url TEXT NOT NULL, published_at TIMESTAMPTZ, fetched_at TIMESTAMPTZ NOT NULL);

CREATE TABLE itinerary_days(id BIGSERIAL PRIMARY KEY, trip_id BIGINT REFERENCES trips(id) ON DELETE CASCADE, day_no INT, date DATE, UNIQUE(trip_id, day_no));
CREATE TABLE itinerary_activities(id BIGSERIAL PRIMARY KEY, day_id BIGINT REFERENCES itinerary_days(id) ON DELETE CASCADE, seq INT, kind TEXT, ref_id TEXT, starts TIME, ends TIME, cost NUMERIC, status TEXT);

CREATE TABLE approvals(id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id), trip_id BIGINT REFERENCES trips(id), kind TEXT NOT NULL,
  payload JSONB NOT NULL, status TEXT NOT NULL DEFAULT 'pending', idempotency_key TEXT UNIQUE, created_at TIMESTAMPTZ DEFAULT now(), decided_at TIMESTAMPTZ);
CREATE TABLE bookings(id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id), trip_id BIGINT REFERENCES trips(id), approval_id BIGINT UNIQUE REFERENCES approvals(id),
  category TEXT, supplier TEXT, item TEXT, amount NUMERIC, currency TEXT DEFAULT 'INR', status TEXT, simulated BOOL NOT NULL DEFAULT true, reference TEXT,
  cancellation_policy TEXT, details JSONB, created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE vouchers(id BIGSERIAL PRIMARY KEY, booking_id BIGINT REFERENCES bookings(id), file_ref TEXT);   -- store object-storage reference only
CREATE TABLE payment_references(id BIGSERIAL PRIMARY KEY, booking_id BIGINT REFERENCES bookings(id), gateway TEXT, gateway_ref TEXT);  -- never card numbers
CREATE TABLE expenses(id BIGSERIAL PRIMARY KEY, trip_id BIGINT REFERENCES trips(id) ON DELETE CASCADE, category TEXT, amount NUMERIC CHECK (amount > 0), paid_by TEXT, note TEXT, created_at TIMESTAMPTZ DEFAULT now());

CREATE TABLE conversations(id BIGSERIAL PRIMARY KEY, trip_id BIGINT REFERENCES trips(id) ON DELETE CASCADE, user_id BIGINT REFERENCES users(id), role TEXT, content TEXT, created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE agent_logs(id BIGSERIAL PRIMARY KEY, workflow_id TEXT, agent TEXT, state TEXT, attempts INT, duration_ms INT, summary TEXT, error TEXT, created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE notifications(id BIGSERIAL PRIMARY KEY, user_id BIGINT REFERENCES users(id), kind TEXT, body TEXT, read_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE audit(id BIGSERIAL PRIMARY KEY, user_id BIGINT, action TEXT, detail JSONB, created_at TIMESTAMPTZ DEFAULT now());
