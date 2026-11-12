"""SQLite persistence for development. Production schema (Postgres + PostGIS + pgvector): see docs/schema.sql."""
import json
import sqlite3
import threading

from . import config

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL, name TEXT, role TEXT NOT NULL DEFAULT 'user', preferences TEXT DEFAULT '{}',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS trips(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id),
  title TEXT, context TEXT NOT NULL, plan TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_trips_user ON trips(user_id);
CREATE TABLE IF NOT EXISTS conversations(id INTEGER PRIMARY KEY AUTOINCREMENT, trip_id INTEGER, user_id INTEGER NOT NULL,
  role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS agent_logs(id INTEGER PRIMARY KEY AUTOINCREMENT, workflow_id TEXT, agent TEXT, state TEXT,
  attempts INTEGER, duration_ms INTEGER, summary TEXT, error TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS approvals(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, trip_id INTEGER,
  kind TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', idempotency_key TEXT UNIQUE,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP, decided_at TEXT);
CREATE TABLE IF NOT EXISTS bookings(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, trip_id INTEGER,
  approval_id INTEGER UNIQUE, category TEXT, supplier TEXT, item TEXT, amount REAL, currency TEXT DEFAULT 'INR',
  status TEXT, simulated INTEGER NOT NULL DEFAULT 1, reference TEXT, cancellation_policy TEXT, details TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT, detail TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY AUTOINCREMENT, trip_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
  category TEXT, amount REAL, paid_by TEXT, note TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS supplier_uploads(id INTEGER PRIMARY KEY AUTOINCREMENT, supplier TEXT, records TEXT,
  matches TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS api_cache(key TEXT PRIMARY KEY, value TEXT NOT NULL, fetched_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS api_usage(provider TEXT, day TEXT, calls INTEGER DEFAULT 0, PRIMARY KEY(provider, day));
CREATE TABLE IF NOT EXISTS match_decisions(id INTEGER PRIMARY KEY AUTOINCREMENT, a TEXT, b TEXT, decision TEXT,
  admin_id INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""


def conn() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA foreign_keys=ON")
            _conn.executescript(SCHEMA)
            _conn.commit()
        return _conn


def reset(path: str | None = None):
    global _conn
    with _lock:
        if _conn:
            _conn.close()
        _conn = None
        if path:
            config.DB_PATH = path


def q(sql: str, params: tuple = ()) -> list[dict]:
    with _lock:
        return [dict(r) for r in conn().execute(sql, params).fetchall()]


def one(sql: str, params: tuple = ()) -> dict | None:
    rows = q(sql, params)
    return rows[0] if rows else None


def run(sql: str, params: tuple = ()) -> int:
    with _lock:
        cur = conn().execute(sql, params)
        conn().commit()
        return cur.lastrowid


def audit(user_id: int | None, action: str, detail: dict | str = ""):
    run("INSERT INTO audit(user_id,action,detail) VALUES(?,?,?)",
        (user_id, action, detail if isinstance(detail, str) else json.dumps(detail, default=str)))
