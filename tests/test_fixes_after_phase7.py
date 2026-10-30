"""Primary share weighting, starting fresh, and keeping browser tabs in step."""

import pytest
import state
from engine_helpers import load_case
from streamlit.testing.v1 import AppTest
from test_app_smoke import HOME, TIMEOUT, try_demo
from test_engine import run
from test_primary_page import PAGE, add_example, button, open_page
from test_primary_share import supplier_pcf
from test_replacement import accept, film
from test_storage import worked_state

from bom_to_pcf.models import ProjectState
from bom_to_pcf.primary_data.replacement import record_submission
from bom_to_pcf.storage.session_store import SessionStore
from bom_to_pcf.storage.sqlite_store import SQLiteStore


def with_supplier(share: float | None):
    case = load_case()
    case.bundle.supplier_pcfs = [supplier_pcf(primary_data_share=share)]
    return run(case)


def test_supplier_share_weights_the_primary_share_by_hand() -> None:
    # Film 1.25 kg x 1.0 = 1.25. Total 1.25 + 0.05 + 0.13 + 0.06 = 1.49 (road T2 cut off).
    # Only the film's factor is primary, so 0.4 x 1.25 = 0.5 counts. Site energy does not.
    assert with_supplier(0.4).primary_data_share == pytest.approx(0.5 / 1.49, rel=0.001)


def test_full_share_counts_in_full_and_zero_not_at_all() -> None:
    assert with_supplier(1.0).primary_data_share == pytest.approx(1.25 / 1.49, rel=0.001)
    assert with_supplier(0.0).primary_data_share == 0


def test_site_quantities_with_a_database_factor_are_not_primary() -> None:
    assert run(load_case()).primary_data_share == 0


def test_site_quantities_with_a_primary_factor_count_by_its_share() -> None:
    case = load_case()
    case.factors = [
        f.model_copy(update={"data_type": "primary", "primary_data_share": 1.0})
        if f.factor_id == "ELEC"
        else f
        for f in case.factors
    ]
    assert run(case).primary_data_share == pytest.approx(0.13 / 2.74, rel=0.001)


def test_no_stated_share_scores_zero_and_is_reported_as_unknown() -> None:
    result = with_supplier(None)
    assert result.primary_data_share == 0
    assert result.primary_share_unknown == pytest.approx(1.25 / 1.49, rel=0.001)
    assert with_supplier(0.4).primary_share_unknown == 0


def test_unknown_supplier_dqr_takes_the_worst_score() -> None:
    case = load_case()
    case.bundle.supplier_pcfs = [supplier_pcf(dqr=None)]
    known = run(case)
    case.bundle.supplier_pcfs = [supplier_pcf(dqr=1.0)]
    assert known.dqr.technological > run(case).dqr.technological
    film_line = next(line for line in known.lines if line.stage == "materials")
    assert film_line.factor_id == "SUPPLIER_S_1"


def test_share_is_used_through_a_stored_version() -> None:
    from bom_to_pcf.primary_data.replacement import apply_primary

    project = ProjectState()
    record_submission(project, film(1.0), accept(1.0), "A")
    case = load_case()
    case.bundle = apply_primary(case.bundle, project)
    assert run(case).primary_data_share == pytest.approx(0.5 * 1.25 / 1.49, rel=0.001)


def test_substitution_credit_keeps_the_result_in_draft() -> None:
    case = load_case()
    case.method.allocation.scrap_recycling = "substitution"
    assert any("PACT" in reason for reason in run(case).draft_reasons)


def test_page_example_states_a_labelled_share() -> None:
    at = add_example(open_page())
    assert at.session_state["project_state"].versions[0].submission.primary_data_share == 0.5


def test_sqlite_start_fresh_archives_instead_of_deleting(tmp_path) -> None:
    path = tmp_path / "app.db"
    store = SQLiteStore(path)
    saved = worked_state()
    store.save(saved)
    store.start_fresh()
    assert store.load() == ProjectState()
    archives = list(tmp_path.glob("app-archive-*.db"))
    assert len(archives) == 1
    assert SQLiteStore(archives[0]).load() == saved


def test_session_start_fresh_clears_the_session() -> None:
    store = SessionStore({})
    store.save(worked_state())
    store.start_fresh()
    assert store.load() == ProjectState()
    store.start_fresh()


def test_start_fresh_button_needs_confirming_and_clears_everything() -> None:
    at = add_example(open_page())
    assert button(at, "Start fresh").disabled
    at.checkbox(key="confirm_fresh").check()
    at.run()
    button(at, "Start fresh").click()
    at.run()
    assert not at.exception
    assert at.title[0].value == "From bill of materials to product carbon footprint"
    assert "bundle" not in at.session_state
    at.switch_page(PAGE)
    at.run()
    assert any("No data loaded" in i.value for i in at.info)


def test_every_run_of_home_forgets_the_working_copy() -> None:
    # AppTest skips Home.py after a page switch, so the first load is what can be tested here.
    at = AppTest.from_file(HOME, default_timeout=TIMEOUT)
    at.session_state["project_state"] = ProjectState()
    at.run()
    assert not at.exception
    assert "project_state" not in at.session_state


def test_colliding_save_is_refused_with_a_clear_message(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOM_TO_PCF_STORAGE", "sqlite")
    monkeypatch.setattr(state, "SQLITE_PATH", tmp_path / "app.db")
    # Opened directly, this tab does not refresh, like a tab caught mid-save.
    stale = open_page()
    add_example(open_page())
    add_example(stale, "Other Reviewer")
    assert not stale.exception
    assert any("refresh this page" in e.value for e in stale.error)
    assert SQLiteStore(tmp_path / "app.db").load().versions[0].user == "Test Reviewer"
    assert len(SQLiteStore(tmp_path / "app.db").load().versions) == 1


def test_demo_in_a_stale_tab_does_not_fail(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOM_TO_PCF_STORAGE", "sqlite")
    monkeypatch.setattr(state, "SQLITE_PATH", tmp_path / "app.db")
    stale = AppTest.from_file(HOME, default_timeout=TIMEOUT).run()
    add_example(open_page())
    assert not try_demo(stale).exception


def test_review_is_rebuilt_when_another_tab_started_fresh() -> None:
    at = open_page()
    at.session_state["project_state"] = ProjectState()
    at.session_state["saved_project_state"] = ProjectState().model_dump_json()
    at.run()
    assert not at.exception
    assert len(at.session_state["project_state"].review_items) == 6
