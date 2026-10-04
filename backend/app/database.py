"""SQLite setup helpers. Every connection enables foreign-key enforcement."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DEFAULT_DATABASE_URL = "sqlite:///./projectbridge.db"
MIGRATION = Path(__file__).resolve().parents[1] / "migrations" / "001_initial.sql"


def database_path(database_url: str | None = None) -> Path:
    value = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    if not value.startswith("sqlite:///"):
        raise ValueError("This prototype currently supports SQLite DATABASE_URL values only")
    raw_path = value.removeprefix("sqlite:///")
    path = Path(raw_path)
    return path if path.is_absolute() else Path.cwd() / path


def connect(database_url: str | None = None) -> sqlite3.Connection:
    path = database_path(database_url)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5.0, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def initialize_database(database_url: str | None = None) -> None:
    connection = connect(database_url)
    try:
        current_version = connection.execute("PRAGMA user_version").fetchone()[0]
        if current_version > 1:
            raise RuntimeError(f"Database schema version {current_version} is newer than this application")
        if current_version == 0:
            connection.executescript(MIGRATION.read_text(encoding="utf-8"))
    finally:
        connection.close()


@contextmanager
def transaction(database_url: str | None = None) -> Iterator[sqlite3.Connection]:
    connection = connect(database_url)
    try:
        connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
