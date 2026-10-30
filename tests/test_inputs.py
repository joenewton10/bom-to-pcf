"""The shipped mock inputs must contain every quirk in the plan, and the demo must match them."""

import filecmp
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bom_to_pcf.cli import app
from bom_to_pcf.io.inputs import BOM_FILE, SUPPLIERS_FILE, InputBundle, load_inputs
from bom_to_pcf.models import ProductConfig

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "input"
DEMO = ROOT / "data" / "demo"
FILES = sorted(path.name for path in INPUT.iterdir() if path.name != ".gitkeep")


@pytest.fixture
def bundle(config: ProductConfig) -> InputBundle:
    return load_inputs(config, INPUT)


def test_mock_inputs_contain_every_planned_quirk(bundle: InputBundle) -> None:
    codes = {issue.code for issue in bundle.issues}
    assert {
        "decimal_comma_normalised",
        "unit_converted",
        "duplicate_line",
        "missing_supplier",
        "obsolete_valid_from",
        "supplier_pcf_placeholder",
        "supplier_pcf_expired",
    } <= codes
    assert {line.uom for line in bundle.bom} == {"KG", "G", "M2", "ST"}


def test_mock_inputs_have_no_errors(bundle: InputBundle) -> None:
    assert not bundle.has_errors
    assert len(bundle.bom) == 6
    assert len(bundle.routing) == 6
    assert not any(pcf.usable for pcf in bundle.supplier_pcfs)


def test_no_invented_supplier_pcf_values(bundle: InputBundle) -> None:
    assert all(pcf.pcf_value is None for pcf in bundle.supplier_pcfs)


def test_demo_set_matches_inputs() -> None:
    assert FILES
    _, mismatch, errors = filecmp.cmpfiles(INPUT, DEMO, FILES, shallow=False)
    assert mismatch == []
    assert errors == []


def test_missing_file_is_reported(config: ProductConfig, tmp_path: Path) -> None:
    shutil.copy(INPUT / BOM_FILE, tmp_path)
    bundle = load_inputs(config, tmp_path)
    assert bundle.has_errors
    assert "file_missing" in {issue.code for issue in bundle.issues}


def test_cross_checks_find_broken_references(config: ProductConfig, tmp_path: Path) -> None:
    for name in FILES:
        shutil.copy(INPUT / name, tmp_path)
    suppliers = (tmp_path / SUPPLIERS_FILE).read_text(encoding="utf-8").splitlines()
    (tmp_path / SUPPLIERS_FILE).write_text("\n".join(suppliers[:2]) + "\n", encoding="utf-8")
    bom = (tmp_path / BOM_FILE).read_text(encoding="utf-8").splitlines()
    (tmp_path / BOM_FILE).write_text(
        "\n".join(line for line in bom if not line.startswith("100001")) + "\n", encoding="utf-8"
    )
    codes = {issue.code for issue in load_inputs(config, tmp_path).issues}
    assert {"unknown_supplier", "unknown_material"} <= codes


def test_cross_check_finds_missing_transport_leg(config: ProductConfig, tmp_path: Path) -> None:
    for name in FILES:
        shutil.copy(INPUT / name, tmp_path)
    legs = tmp_path / "transport_legs.csv"
    kept = [
        line for line in legs.read_text(encoding="utf-8").splitlines() if ",100001," not in line
    ]
    legs.write_text("\n".join(kept) + "\n", encoding="utf-8")
    missing = [i for i in load_inputs(config, tmp_path).issues if i.code == "no_transport_leg"]
    assert [issue.material for issue in missing] == ["100001"]


def test_area_unit_needs_area_properties(config: ProductConfig) -> None:
    assert config.materials["100006"].kg_per_m2 is None


def test_cli_validate_inputs(tmp_path: Path) -> None:
    runner = CliRunner()
    product = str(ROOT / "config" / "product_pet_diecut.yaml")
    good = runner.invoke(app, ["validate-inputs", "--product", product, "--input-dir", str(INPUT)])
    assert good.exit_code == 0
    assert "6 BOM lines" in good.stdout
    bad = runner.invoke(
        app, ["validate-inputs", "--product", product, "--input-dir", str(tmp_path)]
    )
    assert bad.exit_code == 1
