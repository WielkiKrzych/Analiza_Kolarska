"""Autosave keys sessions by file content hash, not by (date, filename)."""

import json
import sqlite3

from modules.db.session_store import SessionRecord, SessionStore

LEGACY_SCHEMA = """
CREATE TABLE sessions (
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
    extra_metrics TEXT DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, filename)
)
"""


def _legacy_db(tmp_path):
    db_path = tmp_path / "sessions.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(LEGACY_SCHEMA)
        conn.execute(
            "INSERT INTO sessions (date, filename, avg_watts) VALUES (?, ?, ?)",
            ("2026-11-22", "ride.csv", 200.0),
        )
        conn.commit()
    return db_path


def test_same_name_different_hash_is_not_overwritten(tmp_path):
    store = SessionStore(_legacy_db(tmp_path))

    first = store.add_session(
        SessionRecord(date="2026-11-22", filename="ride.csv", avg_watts=250.0, file_hash="aaa")
    )
    second = store.add_session(
        SessionRecord(date="2026-11-22", filename="ride.csv", avg_watts=300.0, file_hash="bbb")
    )

    assert first != second
    assert store.get_session_count() == 2
    by_hash = {s.file_hash: s for s in store.get_sessions(days=3650)}
    assert by_hash["aaa"].avg_watts == 250.0
    assert by_hash["bbb"].avg_watts == 300.0


def test_same_hash_updates_its_own_row(tmp_path):
    store = SessionStore(_legacy_db(tmp_path))
    store.add_session(
        SessionRecord(date="2026-11-22", filename="ride.csv", avg_watts=250.0, file_hash="aaa")
    )

    store.add_session(
        SessionRecord(date="2026-11-22", filename="ride.csv", avg_watts=310.0, file_hash="aaa")
    )

    assert store.get_session_count() == 1
    sessions = store.get_sessions(days=3650)
    assert sessions[0].file_hash == "aaa"
    assert sessions[0].avg_watts == 310.0


def test_legacy_empty_hash_row_is_adopted_by_first_hashed_save(tmp_path):
    store = SessionStore(_legacy_db(tmp_path))

    store.add_session(
        SessionRecord(date="2026-11-22", filename="ride.csv", avg_watts=260.0, file_hash="aaa")
    )

    assert store.get_session_count() == 1
    session = store.get_sessions(days=3650)[0]
    assert session.file_hash == "aaa"
    assert session.avg_watts == 260.0


def test_same_hash_with_other_import_date_does_not_duplicate(tmp_path):
    store = SessionStore(_legacy_db(tmp_path))
    store.add_session(
        SessionRecord(date="2026-11-22", filename="ride.csv", avg_watts=250.0, file_hash="aaa")
    )

    store.add_session(
        SessionRecord(date="2026-11-23", filename="renamed.csv", avg_watts=270.0, file_hash="aaa")
    )

    assert store.get_session_count() == 1
    session = store.get_sessions(days=3650)[0]
    assert session.date == "2026-11-22"  # ride date stays put
    assert session.filename == "renamed.csv"
    assert session.avg_watts == 270.0


def test_hashless_legacy_call_still_upserts_by_name(tmp_path):
    store = SessionStore(_legacy_db(tmp_path))

    store.add_session(SessionRecord(date="2026-11-22", filename="ride.csv", avg_watts=260.0))

    assert store.get_session_count() == 1
    assert store.get_sessions(days=3650)[0].avg_watts == 260.0


def test_autosave_merges_extra_metrics(tmp_path):
    store = SessionStore(_legacy_db(tmp_path))
    store.add_session(
        SessionRecord(
            date="2026-11-22",
            filename="ride.csv",
            file_hash="aaa",
            extra_metrics=json.dumps({"tte": {"90": 600}, "note": 1}),
        )
    )

    store.add_session(
        SessionRecord(
            date="2026-11-22",
            filename="ride.csv",
            file_hash="aaa",
            avg_watts=250.0,
            extra_metrics="{}",
        )
    )
    store.add_session(
        SessionRecord(
            date="2026-11-22",
            filename="ride.csv",
            file_hash="aaa",
            extra_metrics=json.dumps({"new": 2}),
        )
    )

    merged = json.loads(store.get_sessions(days=3650)[0].extra_metrics)
    assert merged["tte"] == {"90": 600}
    assert merged["note"] == 1
    assert merged["new"] == 2
