"""Keeps state in a local SQLite file. The database itself refuses changes to history."""

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from bom_to_pcf.models import ProjectState
from bom_to_pcf.storage.base import StorageBackend

HISTORY_TABLES = ("audit", "versions", "rejections", "review_log")
CURRENT_FIELDS = ("active", "review_items")


class SQLiteStore(StorageBackend):
    def __init__(self, path: Path | str) -> None:
        self._path = str(path)
        self._create_tables()

    def _create_tables(self) -> None:
        with closing(self._connect()) as connection, connection:
            for table in HISTORY_TABLES:
                connection.execute(
                    f"CREATE TABLE IF NOT EXISTS {table} (seq INTEGER PRIMARY KEY, payload TEXT)"
                )
                for action in ("UPDATE", "DELETE"):
                    connection.execute(
                        f"CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()} "
                        f"BEFORE {action} ON {table} BEGIN "
                        f"SELECT RAISE(ABORT, '{table} history cannot be changed'); END"
                    )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS current (name TEXT PRIMARY KEY, payload TEXT)"
            )

    def start_fresh(self) -> None:
        """Move the database aside, so nothing is lost, and begin a new one."""
        path = Path(self._path)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
        path.rename(path.with_name(f"{path.stem}-archive-{stamp}{path.suffix}"))
        self._create_tables()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def load(self) -> ProjectState:
        data: dict = {}
        with closing(self._connect()) as connection:
            for table in HISTORY_TABLES:
                rows = connection.execute(f"SELECT payload FROM {table} ORDER BY seq").fetchall()
                data[table] = [json.loads(payload) for (payload,) in rows]
            for name, payload in connection.execute("SELECT name, payload FROM current"):
                data[name] = json.loads(payload)
        return ProjectState.model_validate(data)

    def _write(self, state: ProjectState) -> None:
        dumped = state.model_dump(mode="json")
        with closing(self._connect()) as connection, connection:
            for table in HISTORY_TABLES:
                (count,) = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                connection.executemany(
                    f"INSERT INTO {table} (payload) VALUES (?)",
                    [(json.dumps(item),) for item in dumped[table][count:]],
                )
            connection.executemany(
                "INSERT OR REPLACE INTO current (name, payload) VALUES (?, ?)",
                [(name, json.dumps(dumped[name])) for name in CURRENT_FIELDS],
            )
