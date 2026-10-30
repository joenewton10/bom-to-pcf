import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bom_to_pcf.cli import app
from bom_to_pcf.engine.python_engine import run_with_config
from bom_to_pcf.io.factor_store import load_factors
from bom_to_pcf.io.inputs import load_inputs
from bom_to_pcf.models import MethodConfig
from bom_to_pcf.outputs.dpp_sheet import render_dpp_sheet
from bom_to_pcf.outputs.examples import build_examples, write_examples
from bom_to_pcf.outputs.pact_export import (
    SPEC_VERSION,
    build_footprint,
    load_validator,
    validation_errors,
)
from bom_to_pcf.outputs.runs import config_hash, read_run, write_run

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_EXAMPLE = Path(__file__).parent / "fixtures" / "pact_official_example_1.json"
CREATED = datetime(2026, 1, 1, tzinfo=UTC)
TEMPLATES = ROOT / "templates"


@pytest.fixture
def parts(config):
    bundle = load_inputs(config, ROOT / "data" / "demo")
    result = run_with_config(config, bundle, ROOT)
    method = MethodConfig.from_yaml(ROOT / config.method_file)
    factors, _ = load_factors(ROOT / config.factors_file, ROOT / config.sources_file)
    return result, config, method, {f.factor_id: f for f in factors}, bundle


@pytest.fixture
def footprint(parts):
    result, config, method, known, _ = parts
    return build_footprint(result, config, method, known, CREATED)


def test_validator_accepts_the_official_example() -> None:
    example = json.loads(OFFICIAL_EXAMPLE.read_text(encoding="utf-8"))
    assert validation_errors(example, ROOT) == []


def test_export_passes_the_pinned_official_schema(footprint) -> None:
    assert validation_errors(footprint, ROOT) == []
    assert footprint["specVersion"] == SPEC_VERSION


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("id",), "not-a-uuid"),
        (("status",), "Draft"),
        (("companyIds",), ["no urn"]),
        (("pcf", "declaredUnitOfMeasurement"), "kg"),
        (("pcf", "pcfExcludingBiogenicUptake"), 3.16),
        (("pcf", "fossilGhgEmissions"), "-1"),
    ],
)
def test_broken_exports_fail_the_schema(footprint, path: tuple, value: object) -> None:
    broken = copy.deepcopy(footprint)
    target = broken
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    assert validation_errors(broken, ROOT)


@pytest.mark.parametrize("field", ["id", "companyName", "pcf"])
def test_missing_required_fields_fail_the_schema(footprint, field: str) -> None:
    broken = copy.deepcopy(footprint)
    del broken[field]
    assert not load_validator(ROOT).is_valid(broken)


def test_values_match_the_result(parts, footprint) -> None:
    result = parts[0]
    pcf = footprint["pcf"]
    assert float(pcf["pcfExcludingBiogenicUptake"]) == pytest.approx(result.kg_co2e_per_kg)
    assert float(pcf["primaryDataShare"]) == pytest.approx(result.primary_data_share * 100)
    assert float(pcf["dqi"]["technologicalDQR"]) == pytest.approx(result.dqr.technological)
    assert float(pcf["packagingGhgEmissions"]) == pytest.approx(result.by_stage["packaging"])
    assert pcf["declaredUnitOfMeasurement"] == "kilogram"


def test_reference_period_end_is_exclusive(footprint) -> None:
    assert footprint["pcf"]["referencePeriodStart"] == "2025-01-01T00:00:00Z"
    assert footprint["pcf"]["referencePeriodEnd"] == "2026-01-01T00:00:00Z"


def test_fossil_carbon_counts_a_material_with_two_factors_once(parts, footprint) -> None:
    result = parts[0]
    # Film 1.98075 of 2.94975 kg inputs, at 62.5% carbon.
    assert result.mass_balance.inputs_kg == pytest.approx(2.94975 / 2.5)
    assert float(footprint["pcf"]["fossilCarbonContent"]) == pytest.approx(
        1.98075 / 2.94975 * 0.625, abs=1e-5
    )


def test_export_says_it_is_illustrative_and_a_draft(footprint) -> None:
    assert "ILLUSTRATIVE" in footprint["comment"]
    assert "DRAFT" in footprint["comment"]
    assert "Fictional" in footprint["companyName"]


def test_id_repeats_for_the_same_result(parts, footprint) -> None:
    result, config, method, known, _ = parts
    assert build_footprint(result, config, method, known)["id"] == footprint["id"]


def test_secondary_sources_are_listed(footprint) -> None:
    names = {s["name"] for s in footprint["pcf"]["secondaryEmissionFactorSources"]}
    assert "UBA_CC13_2025" in names
    assert all("version" in s for s in footprint["pcf"]["secondaryEmissionFactorSources"])


def test_export_needs_pact_details(parts) -> None:
    result, config, method, known, _ = parts
    with pytest.raises(ValueError, match="PACT details"):
        build_footprint(result, config.model_copy(update={"pact": None}), method, known)


def test_dqi_is_left_out_with_no_scores(parts) -> None:
    result, config, method, known, _ = parts
    empty = result.dqr.model_copy(update={"overall": None})
    footprint = build_footprint(result.model_copy(update={"dqr": empty}), config, method, known)
    assert "dqi" not in footprint["pcf"]


def test_data_sheet_shows_status_and_is_not_called_a_passport(parts) -> None:
    result, config, *_ = parts
    html = render_dpp_sheet(result, config, TEMPLATES)
    assert "DRAFT" in html
    assert "Illustrative data" in html
    assert "not a passport" in html
    assert f"{result.kg_co2e_per_kg:.2f}" in html


def test_data_sheet_escapes_html(parts) -> None:
    result, config, *_ = parts
    html = render_dpp_sheet(result, config.model_copy(update={"name": "<b>x</b>"}), TEMPLATES)
    assert "<b>x</b>" not in html


def test_examples_are_current_and_valid() -> None:
    expected = build_examples(ROOT)
    folder = ROOT / "outputs" / "examples"
    for name, content in expected.items():
        saved = (folder / name).read_text(encoding="utf-8").replace("\r\n", "\n")
        assert saved == content.replace("\r\n", "\n"), name
    assert validation_errors(json.loads(expected["pact_footprint.json"]), ROOT) == []


def test_report_has_every_section_and_traces_lines() -> None:
    report = build_examples(ROOT)["report.md"]
    for heading in ("Goal and scope", "Why this is a draft", "By stage", "By material",
                    "Mass balance", "Not modelled", "Inventory"):  # fmt: skip
        assert heading in report
    assert "PET_RESIN_VIRGIN" in report
    assert "APR_2020" in report
    assert "not a statistical confidence interval" in report


def test_examples_can_be_written(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(ROOT)
    assert "report.md" in write_examples(ROOT, tmp_path)
    assert (tmp_path / "report.md").is_file()
    result = CliRunner().invoke(app, ["make-examples", "--folder", str(tmp_path / "cli")])
    assert result.exit_code == 0
    assert (tmp_path / "cli" / "report.md").is_file()


def test_run_is_saved_and_can_be_read_back(parts, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(ROOT)
    result, config, _, _, bundle = parts
    run_id = write_run(result, bundle, config, "product.yaml", None, tmp_path)
    manifest, restored = read_run(run_id, tmp_path)
    assert restored == result
    assert manifest["config_hash"] == config_hash(config, ROOT)
    assert {p.name for p in (tmp_path / run_id).iterdir()} == {
        "manifest.json",
        "result.json",
        "input_snapshot.json",
        "issues.csv",
    }


def test_missing_run_is_reported(tmp_path) -> None:
    with pytest.raises(ValueError, match="no run"):
        read_run("nope", tmp_path)


def test_cli_run_then_export_pact(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(ROOT)
    outputs = str(tmp_path)
    run = CliRunner().invoke(
        app, ["run", "--product", "config/product_pet_diecut.yaml", "--outputs-dir", outputs]
    )
    assert run.exit_code == 0
    run_id = next(p.name for p in tmp_path.iterdir())
    assert run_id in run.stdout
    export = CliRunner().invoke(app, ["export-pact", "--run-id", run_id, "--outputs-dir", outputs])
    assert export.exit_code == 0
    written = json.loads((tmp_path / run_id / "pact.json").read_text(encoding="utf-8"))
    assert validation_errors(written, ROOT) == []
    missing = CliRunner().invoke(app, ["export-pact", "--run-id", "x", "--outputs-dir", outputs])
    assert missing.exit_code == 1
