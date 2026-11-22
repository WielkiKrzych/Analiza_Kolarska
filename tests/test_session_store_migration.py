"""A rebuild interrupted between RENAME and DROP is resumed on the next start."""

import sqlite3

from modules.db.session_store import SessionStore

LEGACY_TABLE = """
CREATE TABLE {table} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    filename TEXT NOT NULL,
    duration_sec INTEGER DEFAULT 0,
    tss REAL DEFAULT 0,
    np REAL DEFAULT 0,
    if_factor REAL DEFAULT 0,
    avg_watts REAL DEFAULT 0,
    avg_hr REAL DEFAULT 0,
    max_hr REAL DEFAULT 0,
    work_kj REAL DEFAULT 0,
    avg_cadence REAL DEFAULT 0,
    mmp_5s REAL,
    mmp_1m REAL,
    mmp_5m REAL,
    mmp_20m REAL,
    avg_rmssd REAL,
    alerts_count INTEGER DEFAULT 0,
    extra_metrics TEXT DEFAULT '{{}}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, filename)
)
"""


def _seed_legacy(conn):
    conn.execute(LEGACY_TABLE.format(table="sessions_legacy"))
    conn.executemany(
        "INSERT INTO sessions_legacy (date, filename, avg_watts) VALUES (?, ?, ?)",
        [
            ("2026-11-20", "first.csv", 210.0),
            ("2026-11-21", "second.csv", 220.0),
        ],
    )


def test_resume_after_rename_with_empty_destination(tmp_path):
    db_path = tmp_path / "sessions.db"
    with sqlite3.connect(db_path) as conn:
        _seed_legacy(conn)
        SessionStore._create_table(conn)  # crash left an empty destination
        conn.commit()

    store = SessionStore(db_path)

    assert store.get_session_count() == 2
    sessions = {s.filename: s.avg_watts for s in store.get_sessions(days=3650)}
    assert sessions == {"first.csv": 210.0, "second.csv": 220.0}
    with sqlite3.connect(db_path) as conn:
        legacy = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name = 'sessions_legacy'"
        ).fetchone()[0]
    assert legacy == 0


def test_resume_after_rename_without_destination(tmp_path):
    db_path = tmp_path / "sessions.db"
    with sqlite3.connect(db_path) as conn:
        _seed_legacy(conn)  # crash before CREATE sessions
        conn.commit()

    store = SessionStore(db_path)

    assert store.get_session_count() == 2
