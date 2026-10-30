import time
from pathlib import Path

import pytest
from test_scenarios import ANALYSIS, setup  # noqa: F401
from typer.testing import CliRunner

from bom_to_pcf.cli import app
from bom_to_pcf.scenarios import Scenario, run_scenario
from bom_to_pcf.variants import (
    FamilyConfig,
    Variant,
    build_variant,
    family_table,
    family_variants,
    run_family,
)

ROOT = Path(__file__).resolve().parents[1]
FAMILY = FamilyConfig.from_yaml(ROOT / "config" / "variants_pet_family.yaml")
MAX_SECONDS = 10
MIN_VARIANTS = 20


def base_variant() -> Variant:
    return Variant(thickness_um=125, adhesive=True, recycled_share=0.0)


def calculate(setup, variant: Variant):  # noqa: F811
    bundle, config, method, factors, mappings = setup
    variant_bundle, variant_config = build_variant(bundle, config, FAMILY, variant)
    scenario = Scenario(name="v", recycled_share=variant.recycled_share)
    return (
        run_scenario(variant_bundle, variant_config, method, factors, mappings, scenario, ANALYSIS),
        variant_config,
        variant_bundle,
    )


def test_family_has_at_least_twenty_variants() -> None:
    variants = family_variants(FAMILY)
    assert len(variants) >= MIN_VARIANTS
    assert len({v.model_dump_json() for v in variants}) == len(variants)


def test_whole_family_runs_in_under_ten_seconds(setup) -> None:  # noqa: F811
    bundle, config, method, factors, mappings = setup
    start = time.perf_counter()
    results = run_family(bundle, config, method, factors, mappings, FAMILY, ANALYSIS)
    assert time.perf_counter() - start < MAX_SECONDS
    assert len(results) == len(family_variants(FAMILY))


def test_base_variant_equals_the_baseline(setup) -> None:  # noqa: F811
    result, variant_config, _ = calculate(setup, base_variant())
    baseline = run_scenario(*setup, Scenario(name="b"), ANALYSIS)
    assert result.kg_co2e_per_kg == pytest.approx(baseline.kg_co2e_per_kg)
    assert variant_config.part_mass_g == pytest.approx(2.5)


def test_thickness_changes_film_and_part_mass_by_hand(setup) -> None:  # noqa: F811
    _, variant_config, variant_bundle = calculate(
        setup, Variant(thickness_um=250, adhesive=True, recycled_share=0.0)
    )
    # Inputs per 1,000 parts: film 1.98075 kg doubles, adhesive 0.285, liner 0.684.
    base = 1.98075 + 0.285 + 0.684
    new = 2 * 1.98075 + 0.285 + 0.684
    assert variant_config.part_mass_g == pytest.approx(2.5 * new / base)
    film = next(line for line in variant_bundle.bom if line.material_number == "100001")
    assert film.qty_kg == pytest.approx(2 * 1.98075)
    assert variant_config.materials["100001"].thickness_um == 250


def test_mass_balance_holds_across_the_family(setup) -> None:  # noqa: F811
    for variant in family_variants(FAMILY):
        assert calculate(setup, variant)[0].mass_balance.passed, variant


def test_without_adhesive_the_liner_goes_too(setup) -> None:  # noqa: F811
    result, _, variant_bundle = calculate(
        setup, Variant(thickness_um=125, adhesive=False, recycled_share=0.0)
    )
    materials = {line.material_number for line in variant_bundle.bom}
    assert "100002" not in materials
    assert "100003" not in materials
    assert not any("Acrylat" in name for name in result.by_material)


def test_thicker_film_costs_more_per_part(setup) -> None:  # noqa: F811
    thin, _, _ = calculate(setup, Variant(thickness_um=25, adhesive=True, recycled_share=0.0))
    thick, _, _ = calculate(setup, Variant(thickness_um=250, adhesive=True, recycled_share=0.0))
    assert thick.kg_co2e_per_1000_pieces > thin.kg_co2e_per_1000_pieces


def test_recycled_share_lowers_the_footprint(setup) -> None:  # noqa: F811
    virgin, _, _ = calculate(setup, base_variant())
    recycled, _, _ = calculate(setup, Variant(thickness_um=125, adhesive=True, recycled_share=1.0))
    assert recycled.kg_co2e_per_kg < virgin.kg_co2e_per_kg


def test_table_has_one_row_per_variant_and_writes_csv(setup) -> None:  # noqa: F811
    bundle, config, method, factors, mappings = setup
    results = run_family(bundle, config, method, factors, mappings, FAMILY, ANALYSIS)
    table = family_table(results)
    assert len(table) == len(results)
    assert "kg CO2e per 1,000 parts" in table.to_csv(index=False)
    assert set(table["Adhesive"]) == {"Yes", "No"}


def test_cli_prints_the_family_as_csv(monkeypatch) -> None:
    monkeypatch.chdir(ROOT)
    result = CliRunner().invoke(app, ["variants", "--config", "config/variants_pet_family.yaml"])
    assert result.exit_code == 0
    assert len(result.stdout.strip().splitlines()) == len(family_variants(FAMILY)) + 1
