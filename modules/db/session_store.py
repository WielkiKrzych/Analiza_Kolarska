"""
Database module for storing training sessions.
SQLite-based persistent storage for historical data.
"""

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from modules.config import Config

# Columns shared by every INSERT/UPDATE statement.
_METRIC_COLUMNS = (
    "duration_sec", "tss", "np", "if_factor", "avg_watts", "avg_hr", "max_hr",
    "work_kj", "avg_cadence", "mmp_5s", "mmp_1m", "mmp_5m", "mmp_20m",
    "avg_rmssd", "alerts_count", "extra_metrics",
)

_SESSION_COLUMNS = (
    "id", "date", "filename", *_METRIC_COLUMNS, "created_at", "file_hash",
)

_UPDATE_METRICS = ", ".join(f"{c} = ?" for c in _METRIC_COLUMNS)
_INSERT_COLUMNS = ", ".join(("date", "filename", *_METRIC_COLUMNS, "file_hash"))
_INSERT_PLACEHOLDERS = ", ".join("?" for _ in range(len(_METRIC_COLUMNS) + 3))


def _merge_extra_metrics(old_json: Optional[str], new_json: Optional[str]) -> str:
    """Merge JSON blobs so autosave does not drop keys it does not compute."""
    def _load(raw: Optional[str]) -> dict:
        try:
            value = json.loads(raw or "{}")
        except (TypeError, ValueError):
            return {}
        return value if isinstance(value, dict) else {}

    return json.dumps({**_load(old_json), **_load(new_json)})


def _metric_values(record: "SessionRecord", extra_metrics: Optional[str] = None) -> tuple:
    return tuple(
        extra_metrics if column == "extra_metrics" and extra_metrics is not None
        else getattr(record, column)
        for column in _METRIC_COLUMNS
    )


@dataclass
class SessionRecord:
    """Represents a single training session record."""

    id: Optional[int] = None
    date: str = ""
    filename: str = ""
    duration_sec: int = 0
    tss: float = 0.0
    np: float = 0.0
    if_factor: float = 0.0
    avg_watts: float = 0.0
    avg_hr: float = 0.0
    max_hr: float = 0.0
    work_kj: float = 0.0
    avg_cadence: float = 0.0
    # MMP values
    mmp_5s: Optional[float] = None
    mmp_1m: Optional[float] = None
    mmp_5m: Optional[float] = None
    mmp_20m: Optional[float] = None
    # HRV
    avg_rmssd: Optional[float] = None
    # Alerts count
    alerts_count: int = 0
    # JSON for additional metrics
    extra_metrics: str = "{}"
    # Content hash of the uploaded file (empty for legacy/history-imported rows)
    file_hash: str = ""


class SessionStore:
    """SQLite-based session storage with CRUD operations."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Config.DB_PATH
        # Ensure directory exists
        if self.db_path and not self.db_path.parent.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _init_db(self) -> None:
        """Initialize or migrate the database schema in one transaction."""
        conn = sqlite3.connect(self.db_path)
        # Manage transactions explicitly: Python sqlite3 does not wrap DDL.
        conn.isolation_level = None
        try:
            conn.execute("BEGIN IMMEDIATE")
            self._resume_interrupted_migration(conn)
            self._create_table(conn)

            columns = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
            if "file_hash" not in columns:
                # Existing databases: additive migration, old rows get ''.
                conn.execute("ALTER TABLE sessions ADD COLUMN file_hash TEXT DEFAULT ''")

            if self._has_unique_date_filename(conn):
                # Legacy constraint overwrote a different file with the same name.
                # Rebuild the table so (date, file_hash) becomes the identity.
                self._drop_unique_date_filename(conn)

            self._create_indexes(conn)
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            conn.close()

    @staticmethod
    def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
        ).fetchone() is not None

    def _resume_interrupted_migration(self, conn: sqlite3.Connection) -> None:
        """Finish a rebuild that crashed after RENAME (legacy table left behind).

        The destination may be missing (crash between RENAME and CREATE) or
        partially filled, so create it and copy only rows that are not there yet.
        """
        if not self._table_exists(conn, "sessions_legacy"):
            return

        self._create_table(conn)
        legacy_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(sessions_legacy)")
        }
        dest_columns = [
            c for c in _SESSION_COLUMNS if c in legacy_columns or c == "file_hash"
        ]

        def _select(column: str) -> str:
            if column in legacy_columns:
                return f"COALESCE({column}, '')" if column == "file_hash" else column
            return "''" if column == "file_hash" else "NULL"

        conn.execute(
            f"INSERT OR IGNORE INTO sessions ({', '.join(dest_columns)}) "
            f"SELECT {', '.join(_select(c) for c in dest_columns)} FROM sessions_legacy"
        )
        conn.execute("DROP TABLE sessions_legacy")

    @staticmethod
    def _create_table(conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
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
                file_hash TEXT DEFAULT ''
            )
        """)

    @staticmethod
    def _has_unique_date_filename(conn: sqlite3.Connection) -> bool:
        for row in conn.execute("PRAGMA index_list(sessions)").fetchall():
            # row: (seq, name, unique, origin, partial)
            if not row[2]:
                continue
            cols = [info[2] for info in conn.execute(f'PRAGMA index_info("{row[1]}")')]
            if cols == ["date", "filename"]:
                return True
        return False

    @staticmethod
    def _drop_unique_date_filename(conn: sqlite3.Connection) -> None:
        """Rebuild the table without UNIQUE(date, filename), preserving rows."""
        old_columns = [row[1] for row in conn.execute("PRAGMA table_info(sessions)")]
        copy_columns = [c for c in old_columns if c != "created_at"]
        select_columns = [
            f"COALESCE({c}, '')" if c == "file_hash" else c for c in copy_columns
        ]
        conn.execute("ALTER TABLE sessions RENAME TO sessions_legacy")
        SessionStore._create_table(conn)
        conn.execute(
            f"INSERT INTO sessions ({', '.join(copy_columns)}, created_at) "
            f"SELECT {', '.join(select_columns)}, created_at FROM sessions_legacy"
        )
        conn.execute("DROP TABLE sessions_legacy")

    @staticmethod
    def _create_indexes(conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_date
            ON sessions(date DESC)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_date_filename
            ON sessions(date, filename)
        """)
        # Partial index: legacy rows have '' and must not collide with each other.
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_date_file_hash
            ON sessions(date, file_hash) WHERE file_hash != ''
        """)

    @staticmethod
    def _find_row(
        conn: sqlite3.Connection, where: str, params: tuple
    ) -> Tuple[Optional[int], Optional[str]]:
        """Newest row matching the condition, as (id, extra_metrics)."""
        row = conn.execute(
            f"SELECT id, extra_metrics FROM sessions WHERE {where} "
            "ORDER BY id DESC LIMIT 1",
            params,
        ).fetchone()
        if row is None:
            return None, None
        return int(row[0]), row[1]

    def add_session(self, record: SessionRecord) -> int:
        """Add or update a session record. Returns session ID.

        Identity is the file content hash. A row imported before hashes existed
        (same date + filename, empty hash) is adopted by the first hashed save,
        and an existing hash is updated even if the import date differs, so a
        re-upload never creates a second row for the same ride.
        """
        insert_values = (
            record.date,
            record.filename,
            *_metric_values(record),
            record.file_hash,
        )

        with sqlite3.connect(self.db_path) as conn:
            session_id: Optional[int] = None

            if record.file_hash:
                session_id, old_extra = self._find_row(
                    conn, "file_hash = ?", (record.file_hash,)
                )
                if session_id is not None:
                    merged = _merge_extra_metrics(old_extra, record.extra_metrics)
                    conn.execute(
                        f"UPDATE sessions SET filename = ?, {_UPDATE_METRICS} "
                        "WHERE id = ?",
                        (record.filename, *_metric_values(record, merged), session_id),
                    )
                else:
                    # Adopt a legacy row for the same date + filename.
                    session_id, old_extra = self._find_row(
                        conn,
                        "date = ? AND filename = ? AND COALESCE(file_hash, '') = ''",
                        (record.date, record.filename),
                    )
                    if session_id is not None:
                        merged = _merge_extra_metrics(old_extra, record.extra_metrics)
                        conn.execute(
                            f"UPDATE sessions SET file_hash = ?, {_UPDATE_METRICS} "
                            "WHERE id = ?",
                            (record.file_hash, *_metric_values(record, merged), session_id),
                        )
            else:
                session_id, old_extra = self._find_row(
                    conn,
                    "date = ? AND filename = ? AND COALESCE(file_hash, '') = ''",
                    (record.date, record.filename),
                )
                if session_id is not None:
                    merged = _merge_extra_metrics(old_extra, record.extra_metrics)
                    conn.execute(
                        f"UPDATE sessions SET {_UPDATE_METRICS} WHERE id = ?",
                        (*_metric_values(record, merged), session_id),
                    )

            if session_id is None:
                cursor = conn.execute(
                    f"INSERT INTO sessions ({_INSERT_COLUMNS}) "
                    f"VALUES ({_INSERT_PLACEHOLDERS})",
                    insert_values,
                )
                session_id = int(cursor.lastrowid or 0)

            conn.commit()
            return session_id

    def get_sessions(self, days: int = 90) -> List[SessionRecord]:
        """Get sessions from the last N days using optimized batch fetch."""
        with sqlite3.connect(self.db_path) as conn:
            # Use custom row factory for direct SessionRecord creation
            def session_record_factory(cursor, row):
                # Map row directly to SessionRecord - O(1) per row
                return SessionRecord(
                    id=row[0],
                    date=row[1],
                    filename=row[2],
                    duration_sec=row[3],
                    tss=row[4],
                    np=row[5],
                    if_factor=row[6],
                    avg_watts=row[7],
                    avg_hr=row[8],
                    max_hr=row[9],
                    work_kj=row[10],
                    avg_cadence=row[11],
                    mmp_5s=row[12],
                    mmp_1m=row[13],
                    mmp_5m=row[14],
                    mmp_20m=row[15],
                    avg_rmssd=row[16],
                    alerts_count=row[17],
                    extra_metrics=row[18],
                    file_hash=row[19] or "",
                )

            conn.row_factory = session_record_factory
            cursor = conn.execute(
                """
                SELECT id, date, filename, duration_sec, tss, np, if_factor,
                       avg_watts, avg_hr, max_hr, work_kj, avg_cadence,
                       mmp_5s, mmp_1m, mmp_5m, mmp_20m, avg_rmssd,
                       alerts_count, extra_metrics, file_hash
                FROM sessions
                WHERE date >= date('now', ?)
                ORDER BY date DESC
            """,
                (f"-{days} days",),
            )

            # Single batch fetch - O(n) total
            return cursor.fetchall()

    def get_all_tss(self, days: int = 90) -> List[tuple]:
        """Get (date, tss) tuples for training load calculation."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT date, SUM(tss) as daily_tss
                FROM sessions
                WHERE date >= date('now', ?)
                GROUP BY date
                ORDER BY date ASC
            """,
                (f"-{days} days",),
            )
            return cursor.fetchall()

    def get_session_count(self) -> int:
        """Get total number of stored sessions."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM sessions")
            return cursor.fetchone()[0]

    def delete_session(self, session_id: int) -> bool:
        """Delete a session by ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount > 0
