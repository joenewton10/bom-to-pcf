import io
import zipfile
from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from test_app_smoke import HOME, TIMEOUT, try_demo
from test_primary_page import add_example, button
from test_replacement import accept, film

from bom_to_pcf.io.inputs import load_inputs
from bom_to_pcf.io.supplier_reader import read_submission_file
from bom_to_pcf.models import EngagementConfig, ProjectState, RequestRules
from bom_to_pcf.primary_data.replacement import record_submission, revert
from bom_to_pcf.storage.base import export_state, import_state
from bom_to_pcf.storage.sqlite_store import SQLiteStore
from bom_to_pcf.suppliers.requests import (
    NOT_REQUESTED,
    RECEIVED,
    REJECTED,
    REQUESTED,
    VALIDATED,
    cover_message,
    mark_requested,
    on_revert,
    on_submission,
    records_csv,
    records_json,
    request_files,
    request_records,
    set_note,
    tracker_table,
    zip_requests,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "data" / "demo"
TEMPLATES = ROOT / "templates"
TODAY = date(2026, 1, 15)
RULES: RequestRules = EngagementConfig.from_yaml(
    ROOT / "config" / "supplier_engagement.yaml"
).requests


@pytest.fixture
def bundle(config):
    return load_inputs(config, DEMO)


@pytest.fixture
def film_supplier(bundle):
    return next(s for s in bundle.suppliers if s.supplier_id == "SUP-001")


def history(state: ProjectState, material: str) -> list[str]:
    return [change.status for change in state.requests[material].history]


def test_records_are_prefilled_for_this_supplier_only(bundle, config) -> None:
    records = request_records("SUP-001", bundle.bom, config, RULES)
    assert [r["material_number"] for r in records] == ["100001"]
    assert records[0]["declared_unit"] == "kg"
    assert records[0]["reference_period_end"] == "2025-12-31"
    assert records[0]["boundary"] == "cradle-to-gate"
    assert records[0]["pcf_value"] is None


def test_filled_templates_load_on_the_primary_data_page(bundle, config) -> None:
    records = request_records("SUP-001", bundle.bom, config, RULES)
    records[0]["pcf_value"] = 1.5  # A test value for the file format.
    from_json = read_submission_file(records_json(records).encode(), "a.json")[0]
    from_csv = read_submission_file(records_csv(records).encode(), "a.csv")[0]
    assert from_json.pcf_value == 1.5
    assert from_csv.pcf_value == 1.5
    assert from_csv.reference_period_end == from_json.reference_period_end


def test_cover_message_is_complete_and_private(bundle, config, film_supplier) -> None:
    records = request_records("SUP-001", bundle.bom, config, RULES)
    text = cover_message(film_supplier, records, config, RULES, TEMPLATES)
    assert "Fictional Films A GmbH" in text
    assert "PET-Folie" in text
    assert "2025-01-01 to 2025-12-31" in text
    assert RULES.requested_method in text
    assert "Fictional Adhesives" not in text
    assert "Acrylat" not in text


def test_request_has_three_files_and_zips(bundle, config, film_supplier) -> None:
    files = request_files(film_supplier, bundle.bom, config, RULES, TEMPLATES)
    assert sorted(files) == ["pcf_request_SUP-001.csv", "pcf_request_SUP-001.json",
                             "pcf_request_SUP-001.md"]  # fmt: skip
    with zipfile.ZipFile(io.BytesIO(zip_requests(files))) as archive:
        assert sorted(archive.namelist()) == sorted(files)
        assert archive.read("pcf_request_SUP-001.md").decode() == files["pcf_request_SUP-001.md"]


def test_status_starts_as_not_requested_and_moves_to_requested(bundle) -> None:
    state = ProjectState()
    table = tracker_table(state, bundle.bom, bundle.suppliers)
    assert set(table["Status"]) == {NOT_REQUESTED}
    mark_requested(state, "SUP-001", bundle.bom, TODAY)
    table = tracker_table(state, bundle.bom, bundle.suppliers).set_index("Material")
    assert table.loc["100001", "Status"] == REQUESTED
    assert table.loc["100001", "Requested on"] == TODAY
    assert table.loc["100002", "Status"] == NOT_REQUESTED


def test_status_moves_to_validated_when_primary_data_is_accepted(bundle) -> None:
    state = ProjectState()
    mark_requested(state, "SUP-002", bundle.bom, TODAY)
    pcf = film().model_copy(update={"material_number": "100002", "supplier_id": "SUP-002"})
    record_submission(state, pcf, accept(1.0), "A")
    on_submission(state, pcf, True, bundle.bom, TODAY)
    assert history(state, "100002") == [REQUESTED, RECEIVED, VALIDATED]


def test_status_moves_to_rejected_when_primary_data_is_rejected(bundle) -> None:
    state = ProjectState()
    pcf = film().model_copy(update={"material_number": "100002", "supplier_id": "SUP-002"})
    on_submission(state, pcf, False, bundle.bom, TODAY)
    assert state.requests["100002"].status == REJECTED
    assert history(state, "100002") == [RECEIVED, REJECTED]


def test_rejected_update_keeps_validated_while_earlier_data_is_in_use(bundle) -> None:
    state = ProjectState()
    pcf = film().model_copy(update={"material_number": "100002", "supplier_id": "SUP-002"})
    record_submission(state, pcf, accept(1.0), "A")
    on_submission(state, pcf, False, bundle.bom, TODAY)
    entry = state.requests["100002"]
    assert entry.status == VALIDATED
    assert "rejected" in entry.history[-1].note


def test_data_from_another_supplier_or_material_does_not_move_status(bundle) -> None:
    state = ProjectState()
    other = film().model_copy(update={"material_number": "100002", "supplier_id": "OTHER"})
    on_submission(state, other, True, bundle.bom, TODAY)
    unknown = film().model_copy(update={"material_number": "999"})
    on_submission(state, unknown, True, bundle.bom, TODAY)
    assert state.requests == {}


def test_material_without_a_bom_supplier_can_still_be_tracked(bundle) -> None:
    state = ProjectState()
    pcf = film().model_copy(update={"material_number": "100005", "supplier_id": "NEW"})
    on_submission(state, pcf, True, bundle.bom, TODAY)
    assert state.requests["100005"].status == VALIDATED


def test_requesting_again_does_not_undo_progress(bundle) -> None:
    state = ProjectState()
    pcf = film().model_copy(update={"material_number": "100002", "supplier_id": "SUP-002"})
    on_submission(state, pcf, True, bundle.bom, TODAY)
    mark_requested(state, "SUP-002", bundle.bom, TODAY)
    assert state.requests["100002"].status == VALIDATED


def test_undo_says_whether_validated_data_is_still_in_use(bundle) -> None:
    state = ProjectState()
    pcf = film(1.0).model_copy(update={"material_number": "100002", "supplier_id": "SUP-002"})
    second = film(1.8).model_copy(update={"material_number": "100002", "supplier_id": "SUP-002"})
    record_submission(state, pcf, accept(1.0), "A")
    on_submission(state, pcf, True, bundle.bom, TODAY)
    record_submission(state, second, accept(1.8), "A")
    revert(state, "100002", "V0001", "A", "Typo")
    on_revert(state, "100002", TODAY)
    assert state.requests["100002"].status == VALIDATED
    revert(state, "100002", None, "A", "Withdrawn")
    on_revert(state, "100002", TODAY)
    assert state.requests["100002"].status == RECEIVED
    on_revert(state, "100001", TODAY)
    assert "100001" not in state.requests


def test_notes_are_kept_without_changing_status(bundle) -> None:
    state = ProjectState()
    set_note(state, "100001", "SUP-001", "Chased by phone")
    mark_requested(state, "SUP-001", bundle.bom, TODAY)
    set_note(state, "100001", "SUP-001", "Reply due in June")
    table = tracker_table(state, bundle.bom, bundle.suppliers).set_index("Material")
    assert table.loc["100001", "Notes"] == "Reply due in June"
    assert table.loc["100001", "Status"] == REQUESTED


def test_tracker_handles_a_material_with_no_supplier(bundle) -> None:
    table = tracker_table(ProjectState(), bundle.bom, bundle.suppliers).set_index("Material")
    assert table.loc["100005", "Supplier"] == "Not known"


def test_tracker_is_saved_and_restored(tmp_path, bundle) -> None:
    state = ProjectState()
    mark_requested(state, "SUP-001", bundle.bom, TODAY)
    assert import_state(export_state(state)) == state
    store = SQLiteStore(tmp_path / "t.db")
    store.save(state)
    assert store.load() == state


def page(path: str) -> AppTest:
    at = try_demo(AppTest.from_file(HOME, default_timeout=TIMEOUT).run())
    at.switch_page(path)
    return at.run()


def test_requests_page_marks_requested_and_primary_data_validates_it() -> None:
    at = page("pages/5_Supplier_requests.py")
    assert not at.exception
    assert at.metric[0].value == "0%"
    button(at, "Mark these as requested").click()
    at.run()
    assert at.session_state["project_state"].requests["100001"].status == REQUESTED
    at.switch_page("pages/6_Primary_data.py")
    at.run()
    add_example(at)
    assert at.session_state["project_state"].requests["100001"].status == VALIDATED
    at.text_input(key="undo_reason").input("Test")
    at.run()
    button(at, "Undo").click()
    at.run()
    assert not at.exception
    assert at.session_state["project_state"].requests["100001"].status == RECEIVED


def test_requests_page_coverage_rises_with_validated_data() -> None:
    at = page("pages/6_Primary_data.py")
    add_example(at)
    at.switch_page("pages/5_Supplier_requests.py")
    at.run()
    assert not at.exception
    assert at.metric[0].value != "0%"


def test_requests_page_saves_notes_and_prompts_without_data() -> None:
    at = page("pages/5_Supplier_requests.py")
    button(at, "Save notes").click()
    at.run()
    assert not at.exception
    fresh = AppTest.from_file(HOME, default_timeout=TIMEOUT).run()
    fresh.switch_page("pages/5_Supplier_requests.py")
    fresh.run()
    assert any("No data loaded" in i.value for i in fresh.info)
