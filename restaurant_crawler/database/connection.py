"""SQLite connection helpers (sync + async-friendly wrappers)."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Iterable

from restaurant_crawler.database.schema import SCHEMA_SQL


class Database:
    """Thin wrapper around sqlite3 with schema initialization."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, sql: str, params: Iterable | None = None) -> sqlite3.Cursor:
        with self.connect() as conn:
            return conn.execute(sql, tuple(params or ()))

    def executemany(self, sql: str, seq: Iterable[Iterable]) -> None:
        with self.connect() as conn:
            conn.executemany(sql, list(seq))

    def fetchone(self, sql: str, params: Iterable | None = None) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(sql, tuple(params or ())).fetchone()

    def fetchall(self, sql: str, params: Iterable | None = None) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(conn.execute(sql, tuple(params or ())).fetchall())
