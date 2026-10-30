from pathlib import Path

import pytest
from engine_helpers import bom_line, factor, load_case
from typer.testing import CliRunner

from bom_to_pcf.cli import app
from bom_to_pcf.engine.python_engine import LABEL_DRAFT, LABEL_FINAL, LABEL_PLACEHOLDERS, run_pcf
from bom_to_pcf.io.factor_store import load_factors, read_mappings
from bom_to_pcf.io.inputs import load_inputs
from bom_to_pcf.models import Issue, Mapping, MethodConfig, ProductConfig, Severity

ROOT = Path(__file__).resolve().parents[1]
WITHIN_TOLERANCE = 0.001


def run(case):
    return run_pcf(case.bundle, case.config, case.method, case.factors, case.mappings)


def test_reference_case_matches_hand_calculation() -> None:
    case = load_case()
    result = run(case)
    expected = case.expected
    assert result.kg_co2e_per_kg == pytest.approx(expected["kg_co2e_per_kg"], rel=WITHIN_TOLERANCE)
    assert result.kg_co2e_per_1000_pieces == pytest.approx(
        expected["kg_co2e_per_1000_pieces"], rel=WITHIN_TOLERANCE
    )
    assert result.primary_data_share == pytest.approx(expected["primary_data_share"], abs=1e-9)
    assert result.dqr.technological == pytest.approx(
        expected["dqr_technological"], rel=WITHIN_TOLERANCE
    )
    assert result.by_stage == pytest.approx(expected["by_stage"], rel=WITHIN_TOLERANCE, abs=1e-9)


def test_reference_case_is_final_and_complete() -> None:
    result = run(load_case())
    assert not result.is_draft
    assert not result.is_partial
    assert result.status_label == LABEL_FINAL
    assert result.mass_balance.passed


def test_cut_off_exclusions_are_reported() -> None:
    assert {line.item for line in run(load_case()).excluded} == {"T2"}


def test_every_line_traces_to_a_factor() -> None:
    case = load_case()
    known = {f.factor_id for f in case.factors}
    for line in run(case).lines:
        assert line.factor_id is None or line.factor_id in known


def test_placeholder_makes_result_draft_and_partial() -> None:
    case = load_case()
    case.factors = [f for f in case.factors if f.factor_id != "FILM"]
    case.factors.append(factor("FILM", None, "kg CO2e/kg", None))
    result = run(case)
    assert result.is_draft
    assert result.is_partial
    assert result.status_label.startswith(LABEL_PLACEHOLDERS)
    assert "true footprint is higher" in result.status_label
    assert "FILM" in result.missing[0]
    assert result.kg_co2e_per_kg < 1


def test_unmapped_material_is_reported() -> None:
    case = load_case()
    case.mappings = [m for m in case.mappings if m.material_number != "2"]
    result = run(case)
    assert result.is_partial
    assert any("Box" in text for text in result.missing)


def test_mapping_to_unknown_factor_is_reported() -> None:
    case = load_case()
    case.mappings[1] = Mapping(material_number="2", factor_id="NOPE", review_status="approved")
    assert any("not in the factor table" in text for text in run(case).missing)


def test_unreviewed_mapping_is_draft_but_not_partial() -> None:
    case = load_case()
    case.mappings[0] = Mapping(material_number="1", factor_id="FILM", review_status="unreviewed")
    result = run(case)
    assert result.is_draft
    assert not result.is_partial
    assert any("unreviewed" in reason for reason in result.draft_reasons)


def test_broken_mass_balance_makes_result_draft() -> None:
    case = load_case()
    case.bundle.bom[0] = bom_line("1", "Film", 4.0)
    result = run(case)
    assert result.is_draft
    assert any("mass balance" in reason for reason in result.draft_reasons)


def test_piece_factor_uses_piece_quantity() -> None:
    case = load_case()
    line = bom_line("2", "Pallet", 0.1)
    case.bundle.bom[1] = line.model_copy(update={"component_qty": 0.01, "uom": "ST"})
    case.factors.append(factor("PIECE", 10.0, "kg CO2e/piece"))
    case.mappings[1] = Mapping(material_number="2", factor_id="PIECE", review_status="approved")
    # 0.01 pieces per 2 kg base = 0.005 pieces per kg, at 10 per piece.
    assert run(case).by_stage["packaging"] == pytest.approx(0.05)


def test_piece_factor_with_mass_bom_unit_is_a_gap() -> None:
    case = load_case()
    case.factors.append(factor("PIECE", 10.0, "kg CO2e/piece"))
    case.mappings[1] = Mapping(material_number="2", factor_id="PIECE", review_status="approved")
    assert any("per piece" in text for text in run(case).missing)


def test_unsupported_factor_unit_is_a_gap() -> None:
    case = load_case()
    case.factors.append(factor("ODD", 1.0, "kg CO2e/litre"))
    case.mappings[1] = Mapping(material_number="2", factor_id="ODD", review_status="approved")
    assert any("unsupported unit" in text for text in run(case).missing)


def test_unknown_transport_mode_is_a_gap() -> None:
    case = load_case()
    case.bundle.transport[0].mode = "rail"
    assert any("rail" in text for text in run(case).missing)


def test_scrap_destination_without_factor_is_a_gap() -> None:
    case = load_case()
    case.bundle.routing[0].scrap_destination = "landfill"
    assert any("landfill" in text for text in run(case).missing)


def test_missing_overhead_step_is_a_gap() -> None:
    case = load_case()
    case.bundle.routing = case.bundle.routing[:2]
    assert any("overhead" in text for text in run(case).missing)


def test_input_errors_make_result_draft() -> None:
    case = load_case()
    case.bundle.issues = [
        Issue(severity=Severity.ERROR, code="invalid_row", source="bom", message="Bad row.")
    ]
    result = run(case)
    assert result.is_draft
    assert result.status_label == LABEL_DRAFT


def test_transport_leg_for_unknown_material_is_ignored() -> None:
    case = load_case()
    before = run(case).kg_co2e_per_kg
    case.bundle.transport[0].material_number = "not in the BOM"
    assert run(case).kg_co2e_per_kg < before


def test_excluded_share_is_reported_and_within_limit() -> None:
    result = run(load_case())
    assert result.excluded_share == pytest.approx(0.0012 / 2.7412, rel=WITHIN_TOLERANCE)


def test_unreviewed_item_left_out_by_cut_off_still_counts_as_unreviewed() -> None:
    case = load_case()
    case.method.cut_off.flow_share = 0.5
    case.mappings[1] = Mapping(material_number="2", factor_id="BOX", review_status="unreviewed")
    assert any("unreviewed" in reason for reason in run(case).draft_reasons)


def test_read_mappings_reports_bad_rows() -> None:
    header = b"material_number,factor_id,review_status\n"
    assert read_mappings(b"material_number\n1\n")[1][0].code == "missing_columns"
    mappings, issues = read_mappings(header + b"1,F,maybe\n")
    assert mappings == []
    assert issues[0].code == "invalid_mapping"


def test_demo_data_is_draft_until_matches_are_reviewed(config: ProductConfig, monkeypatch) -> None:
    monkeypatch.chdir(ROOT)
    bundle = load_inputs(config)
    method = MethodConfig.from_yaml(config.method_file)
    factors, _ = load_factors(config.factors_file, config.sources_file)
    mappings, _ = read_mappings(config.mappings_file)
    result = run_pcf(bundle, config, method, factors, mappings)
    assert result.is_draft
    assert not result.is_partial
    assert result.status_label == LABEL_DRAFT
    assert any("unreviewed" in reason for reason in result.draft_reasons)
    assert result.mass_balance.passed
    assert result.excluded == []
    assert result.primary_data_share == 0
    assert any("stretching" in text for text in result.known_omissions)


def test_cli_run_shows_status_and_reasons(monkeypatch) -> None:
    monkeypatch.chdir(ROOT)
    result = CliRunner().invoke(app, ["run", "--product", "config/product_pet_diecut.yaml"])
    assert result.exit_code == 0
    assert "DRAFT" in result.stdout
    assert "unreviewed" in result.stdout
