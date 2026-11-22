"""TTE is written to one session row, never to every row of a filename/date pair."""

import json
import sqlite3

import modules.tte as tte
from modules.config import Config
from modules.db.session_store import SessionRecord, SessionStore


def _store(tmp_path, monkeypatch) -> SessionStore:
    db_path = tmp_path / "sessions.db"
    monkeypatch.setattr(Config, "DB_PATH", db_path)
    return SessionStore(db_path)


def test_tte_updates_only_the_row_with_given_hash(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    store.add_session(
        SessionRecord(date="2026-11-22", filename="ride.csv", file_hash="aaa")
    )
    store.add_session(
        SessionRecord(date="2026-11-22", filename="ride.csv", file_hash="bbb")
    )

    assert tte.save_tte_to_db("ride.csv", "2026-11-22", 90, 600, file_hash="bbb")

    extra = {
        s.file_hash: json.loads(s.extra_metrics)
        for s in store.get_sessions(days=3650)
    }
    assert "tte" not in extra["aaa"]
    assert extra["bbb"]["tte"] == {"90": 600}


def test_tte_without_hash_updates_only_newest_row(tmp_path, monkeypatch):
    _store(tmp_path, monkeypatch)
    with sqlite3.connect(Config.DB_PATH) as conn:
        conn.executemany(
            "INSERT INTO sessions (date, filename, extra_metrics) VALUES (?, ?, '{}')",
            [
                ("2026-11-22", "ride.csv"),
                ("2026-11-22", "ride.csv"),
            ],
        )
        conn.commit()

    assert tte.save_tte_to_db("ride.csv", "2026-11-22", 90, 600)

    with sqlite3.connect(Config.DB_PATH) as conn:
        rows = conn.execute(
            "SELECT extra_metrics FROM sessions WHERE filename = 'ride.csv' ORDER BY id"
        ).fetchall()
    assert json.loads(rows[0][0]) == {}
    assert json.loads(rows[1][0])["tte"] == {"90": 600}
