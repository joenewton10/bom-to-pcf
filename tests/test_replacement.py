from datetime import date

import pytest
from engine_helpers import bom_line, load_case
from test_engine import run

from bom_to_pcf.io.supplier_reader import read_submission_file
from bom_to_pcf.models import PrimaryDataRules, ProjectState, SupplierPcf
from bom_to_pcf.primary_data.replacement import (
    AUDIT_COLUMNS,
    already_seen,
    apply_primary,
    audit_table,
    compare_results,
    record_submission,
    rejections_table,
    revert,
    versions_table,
)
from bom_to_pcf.primary_data.validation import SubmissionCheck

RULES = PrimaryDataRules(
    plausibility_low=0.2,
    plausibility_high=5.0,
    allowed_boundaries=["cradle-to-gate"],
    example_ratio=0.8,
)
ACCEPT = SubmissionCheck(accepted=True, reasons=[], value_per_kg=1.0, secondary_per_kg=2.0)
REJECT = SubmissionCheck(accepted=False, reasons=["Too old."])


def line():
    built = bom_line("100002", "Adhesive", 1.0)
    return built.model_copy(update={"supplier_id": "SUP-002"})


def submission(**overrides: object) -> SupplierPcf:
    # Test values for the workflow, not emission data.
    fields = {
        "supplier_id": "SUP-002",
        "material_number": "100002",
        "pcf_value": 1.5,
        "declared_unit": "kg",
        "reference_period_start": date(2025, 1, 1),
        "reference_period_end": date(2025, 12, 31),
        "method": "ISO 14067",
        "boundary": "cradle-to-gate",
        "dqr": 1.5,
    }
    return SupplierPcf(**(fields | overrides))


def film(value: float = 1.0) -> SupplierPcf:
    return submission(supplier_id="S", material_number="1", pcf_value=value)


def calculate(case, state: ProjectState):
    case.bundle = apply_primary(case.bundle, state)
    return run(case)


def accept(value: float) -> SubmissionCheck:
    return ACCEPT.model_copy(update={"value_per_kg": value})


def test_valid_pcf_changes_the_result_and_primary_share() -> None:
    state = ProjectState()
    before = calculate(load_case(), state)
    record_submission(state, film(), accept(1.0), "A")
    after = calculate(load_case(), state)
    # Film 1.25 kg x 1.0 instead of x 2.0.
    assert after.by_stage["materials"] == pytest.approx(1.25)
    assert after.kg_co2e_per_kg < before.kg_co2e_per_kg
    assert after.primary_data_share > before.primary_data_share


def test_revert_restores_previous_values_exactly() -> None:
    state = ProjectState()
    before = calculate(load_case(), state)
    record_submission(state, film(), accept(1.0), "A")
    revert(state, "1", None, "A", "Wrong file")
    assert calculate(load_case(), state).model_dump() == before.model_dump()


def test_revert_to_an_earlier_version_restores_it_exactly() -> None:
    state = ProjectState()
    record_submission(state, film(1.0), accept(1.0), "A")
    first = calculate(load_case(), state)
    record_submission(state, film(1.8), accept(1.8), "A")
    assert calculate(load_case(), state).kg_co2e_per_kg != first.kg_co2e_per_kg
    revert(state, "1", "V0001", "A", "Second value was a typo")
    assert calculate(load_case(), state).model_dump() == first.model_dump()


def test_rejected_submission_keeps_the_value_in_use_and_records_why() -> None:
    state = ProjectState()
    before = calculate(load_case(), state)
    assert record_submission(state, film(), REJECT, "A") is None
    assert state.active == {}
    assert calculate(load_case(), state).kg_co2e_per_kg == before.kg_co2e_per_kg
    assert "Too old." in rejections_table(state).loc[0, "Why it was rejected"]
    assert state.audit[0].field == "submission"
    assert "Too old." in state.audit[0].reason


def test_primary_lines_trace_to_their_version() -> None:
    state = ProjectState()
    record_submission(state, film(), accept(1.0), "A")
    lines = calculate(load_case(), state).lines
    assert next(x for x in lines if x.stage == "materials").source_id == "supplier_pcf:V0001"


def test_file_records_do_not_reach_the_engine_without_validation() -> None:
    case = load_case()
    before = run(case)
    case.bundle.supplier_pcfs = [film()]
    assert calculate(case, ProjectState()).kg_co2e_per_kg == before.kg_co2e_per_kg


def test_converted_value_is_what_the_engine_uses() -> None:
    state = ProjectState()
    record_submission(
        state, film(1000.0).model_copy(update={"declared_unit": "t"}), accept(1.0), "A"
    )
    assert calculate(load_case(), state).by_stage["materials"] == pytest.approx(1.25)


def test_audit_has_the_planned_columns_and_is_only_added_to() -> None:
    state = ProjectState()
    record_submission(state, film(1.0), accept(1.0), "A", "First")
    first = list(state.audit)
    record_submission(state, film(1.8), accept(1.8), "B")
    revert(state, "1", "V0001", "C", "Undo")
    assert state.audit[: len(first)] == first
    assert list(audit_table(state).columns) == AUDIT_COLUMNS
    assert {"timestamp", "user", "material", "supplier", "field", "old_value", "new_value",
            "reason", "version_id"} == set(AUDIT_COLUMNS)  # fmt: skip
    assert state.audit[-1].field == "active_version"
    assert state.audit[-1].old_value == "V0002"
    assert state.audit[-1].new_value == "V0001"


def test_first_version_logs_the_secondary_value_it_replaces() -> None:
    state = ProjectState()
    record_submission(state, film(), accept(1.0), "A")
    entry = next(e for e in state.audit if e.field == "pcf_value")
    assert entry.old_value == "secondary: 2.0 per kg"
    assert entry.new_value == "1.0"


def test_second_version_logs_only_what_changed() -> None:
    state = ProjectState()
    record_submission(state, film(1.0), accept(1.0), "A")
    count = len(state.audit)
    record_submission(state, film(1.8), accept(1.8), "A")
    assert [e.field for e in state.audit[count:]] == ["pcf_value"]


def test_versions_are_kept_and_one_is_in_use() -> None:
    state = ProjectState()
    record_submission(state, film(1.0), accept(1.0), "A")
    record_submission(state, film(1.8), accept(1.8), "A")
    table = versions_table(state)
    assert table["Version"].tolist() == ["V0001", "V0002"]
    assert table["In use"].tolist() == [False, True]


@pytest.mark.parametrize(
    ("material", "target", "user", "reason", "fragment"),
    [
        ("1", None, "", "x", "name"),
        ("1", None, "A", " ", "reason"),
        ("1", "V9999", "A", "x", "does not belong"),
        ("2", "V0001", "A", "x", "does not belong"),
        ("1", "V0001", "A", "x", "already in use"),
    ],
)
def test_bad_reverts_change_nothing(material, target, user, reason, fragment) -> None:
    state = ProjectState()
    record_submission(state, film(), accept(1.0), "A")
    audit = list(state.audit)
    with pytest.raises(ValueError, match=fragment):
        revert(state, material, target, user, reason)
    assert state.audit == audit
    assert state.active == {"1": "V0001"}


def test_submission_needs_a_user() -> None:
    with pytest.raises(ValueError, match="name"):
        record_submission(ProjectState(), film(), ACCEPT, " ")


def test_already_seen_covers_accepted_and_rejected() -> None:
    state = ProjectState()
    assert not already_seen(state, film())
    record_submission(state, film(1.0), accept(1.0), "A")
    record_submission(state, film(9.0), REJECT, "A")
    assert already_seen(state, film(1.0))
    assert already_seen(state, film(9.0))
    assert not already_seen(state, film(2.0))


def test_compare_shows_old_new_and_change() -> None:
    state = ProjectState()
    before = calculate(load_case(), state)
    record_submission(state, film(), accept(1.0), "A")
    after = calculate(load_case(), state)
    table = compare_results(before, after).set_index("Measure")
    row = table.loc["PCF, kg CO2e per kg"]
    assert row["Change"] == pytest.approx(after.kg_co2e_per_kg - before.kg_co2e_per_kg)
    assert row["Change"] < 0
    assert table.loc["Primary data share, %", "Change"] > 0


def test_read_json_and_csv_submissions() -> None:
    from_json = read_submission_file(
        b'{"records":[{"supplier_id":"S","material_number":"1","pcf_value":1.5}]}', "a.JSON"
    )
    assert from_json[0].pcf_value == 1.5
    assert (
        read_submission_file(b'[{"supplier_id":"S","material_number":"1"}]', "a.json")[
            0
        ].material_number
        == "1"
    )
    csv = b'supplier_id,material_number,pcf_value,dqr,notes\nS,1,"1,5",,hello\n'
    from_csv = read_submission_file(csv, "a.csv")[0]
    assert from_csv.pcf_value == 1.5
    assert from_csv.dqr is None
    assert from_csv.notes == "hello"


@pytest.mark.parametrize(
    ("raw", "name"),
    [(b"not json", "a.json"), (b"{}", "a.json"), (b"material_number\n1\n", "a.csv")],
)
def test_unreadable_submission_files_raise(raw: bytes, name: str) -> None:
    with pytest.raises(ValueError, match="could not be read"):
        read_submission_file(raw, name)
