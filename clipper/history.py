"""Local history of detected addresses (sqlite)."""

import datetime
import os
import sqlite3
import sys
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    chain TEXT NOT NULL,
    kind TEXT NOT NULL,
    confidence TEXT NOT NULL,
    address TEXT NOT NULL
)
"""
_INSERT = "INSERT INTO events (ts, chain, kind, confidence, address) VALUES (?, ?, ?, ?, ?)"


def default_db_path():
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", "~/AppData/Roaming")).expanduser()
        return base / "Clipper" / "history.db"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Clipper" / "history.db"
    data_home = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(data_home) / "clipper" / "history.db"


def record(findings, db_path=None) -> None:
    path = Path(db_path) if db_path else default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now().isoformat(timespec="seconds")
    conn = sqlite3.connect(path)
    try:
        conn.execute(_SCHEMA)
        conn.executemany(
            _INSERT,
            [(now, f.chain, f.kind, f.confidence, f.address) for f in findings],
        )
        conn.commit()
    finally:
        conn.close()
    try:
        os.chmod(path, 0o600)  # clipboard history is nobody else's business
    except OSError:
        pass


def recent(limit=20, db_path=None):
    path = Path(db_path) if db_path else default_db_path()
    if not path.exists():
        return []
    conn = sqlite3.connect(path)
    try:
        conn.execute(_SCHEMA)
        return conn.execute(
            "SELECT ts, chain, kind, confidence, address "
            "FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
