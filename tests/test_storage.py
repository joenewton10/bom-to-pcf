import json
import sqlite3
from contextlib import closing

import pytest
from test_replacement import accept, film

from bom_to_pcf.models import ProjectState, ReviewItem
from bom_to_pcf.primary_data.replacement import record_submission, revert
from bom_to_pcf.storage.base import (
    SESSION,
    SQLITE,
    HistoryConflictError,
    choose_backend,
    export_state,
    import_state,
)
from bom_to_pcf.storage.session_store import SessionStore
from bom_to_pcf.storage.sqlite_store import SQLiteStore


def worked_state() -> ProjectState:
    state = ProjectState(
        review_items=[ReviewItem(material_number="1", description="d", uom="KG", suggestions=[])]
    )
    record_submission(state, film(1.0), accept(1.0), "A", "First")
    record_submission(state, film(1.8), accept(1.8), "A")
    revert(state, "1", "V0001", "A", "Typo")
    return state


@pytest.fixture(params=["sqlite", "session"])
def store(request, tmp_path):
    if request.param == "sqlite":
        return SQLiteStore(tmp_path / "test.db")
    return SessionStore({})


def test_new_store_is_empty(store) -> None:
    assert store.load() == ProjectState()


def test_save_and_load_round_trip(store) -> None:
    state = worked_state()
    store.save(state)
    assert store.load() == state


def test_later_saves_add_to_history(store) -> None:
    state = worked_state()
    store.save(state)
    record_submission(state, film(1.2), accept(1.2), "B")
    store.save(state)
    assert store.load() == state


def test_store_refuses_to_rewrite_history(store) -> None:
    state = worked_state()
    store.save(state)
    with pytest.raises(HistoryConflictError, match="never overwritten"):
        store.save(ProjectState())
    tampered = state.model_copy(deep=True)
    tampered.audit[0].new_value = "changed"
    with pytest.raises(HistoryConflictError):
        store.save(tampered)
    assert store.load() == state


def test_sqlite_survives_a_new_connection(tmp_path) -> None:
    state = worked_state()
    SQLiteStore(tmp_path / "test.db").save(state)
    assert SQLiteStore(tmp_path / "test.db").load() == state


@pytest.mark.parametrize("statement", ["UPDATE audit SET payload = 'x'", "DELETE FROM versions"])
def test_sqlite_database_itself_blocks_changes_to_history(tmp_path, statement: str) -> None:
    path = tmp_path / "test.db"
    SQLiteStore(path).save(worked_state())
    with closing(sqlite3.connect(path)) as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute(statement)


def test_export_then_import_restores_the_same_state() -> None:
    state = worked_state()
    assert import_state(export_state(state)) == state


def test_session_export_and_re_upload_restores_into_a_new_session() -> None:
    state = worked_state()
    new_session = SessionStore({})
    new_session.save(import_state(export_state(state)))
    assert new_session.load() == state


@pytest.mark.parametrize(
    "raw",
    [
        b"not json",
        b"\xff\xfe",
        b"[]",
        b'{"format":"other"}',
        b'{"format":"bom-to-pcf-state","version":99,"state":{}}',
        b'{"format":"bom-to-pcf-state","version":1}',
        b'{"format":"bom-to-pcf-state","version":1,"state":{"versions":"x"}}',
        b'{"format":"bom-to-pcf-state","version":1,"state":{"active":{"1":"V9"}}}',
    ],
)
def test_bad_import_files_are_refused(raw: bytes) -> None:
    with pytest.raises(ValueError):
        import_state(raw)


def test_export_is_readable_json() -> None:
    payload = json.loads(export_state(worked_state()))
    assert payload["state"]["active"] == {"1": "V0001"}


@pytest.mark.parametrize(
    ("override", "host", "expected"),
    [
        (None, "localhost:8501", SQLITE),
        (None, "127.0.0.1:8501", SQLITE),
        (None, "[::1]:8501", SQLITE),
        (None, "my-app.streamlit.app", SESSION),
        (None, None, SESSION),
        (SESSION, "localhost:8501", SESSION),
        (SQLITE, "my-app.streamlit.app", SQLITE),
    ],
)
def test_backend_choice(override, host, expected) -> None:
    assert choose_backend(override, host) == expected


def test_unknown_backend_is_refused() -> None:
    with pytest.raises(ValueError):
        choose_backend("postgres", None)
