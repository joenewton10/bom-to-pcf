from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest
from test_app_smoke import HOME, TIMEOUT, try_demo
from tests_support import factor_for
from typer.testing import CliRunner

from bom_to_pcf.cli import app
from bom_to_pcf.engine.python_engine import run_pcf
from bom_to_pcf.io.factor_store import load_factors, read_mappings
from bom_to_pcf.io.inputs import load_inputs
from bom_to_pcf.methods.uncertainty import monte_carlo, relative_sd
from bom_to_pcf.models import AnalysisConfig, MethodConfig, ResultLine
from bom_to_pcf.scenarios import (
    Scenario,
    blended_factor,
    load_scenarios,
    run_scenario,
    scenario_table,
)

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = AnalysisConfig.from_yaml(ROOT / "config" / "analysis.yaml")
RULES = ANALYSIS.uncertainty


@pytest.fixture
def setup(config):
    factors, _ = load_factors(ROOT / config.factors_file, ROOT / config.sources_file)
    mappings, _ = read_mappings(ROOT / config.mappings_file)
    return (
        load_inputs(config, ROOT / "data" / "demo"),
        config,
        MethodConfig.from_yaml(ROOT / config.method_file),
        factors,
        mappings,
    )


def run(setup, scenario: Scenario):
    return run_scenario(*setup, scenario, ANALYSIS)


def factor_value(setup, factor_id: str) -> float:
    return next(f.value for f in setup[3] if f.factor_id == factor_id)


def test_baseline_equals_the_normal_calculation(setup) -> None:
    bundle, config, method, factors, mappings = setup
    assert (
        run(setup, Scenario(name="b")).model_dump()
        == run_pcf(bundle, config, method, factors, mappings).model_dump()
    )


def test_scenario_files_load_with_baseline_first() -> None:
    scenarios = load_scenarios(ROOT / "config" / "scenarios")
    assert scenarios[0].name == "Baseline"
    assert {s.name for s in scenarios} == {
        "Baseline",
        "Green electricity",
        "Recycled PET",
        "High scrap",
    }
    assert all(s.description for s in scenarios)


def test_green_electricity_scales_only_electricity(setup) -> None:
    base = run(setup, Scenario(name="b"))
    green = run(setup, Scenario(name="g", renewable_share=1.0))
    ratio = factor_value(setup, "EL_DE_WIND") / factor_value(setup, "EL_DE_GRID")
    for stage in ("converting_energy", "site_overhead"):
        assert green.by_stage[stage] == pytest.approx(base.by_stage[stage] * ratio)
    assert green.by_stage["materials"] == pytest.approx(base.by_stage["materials"])


def test_recycled_share_blends_the_resin_by_hand(setup) -> None:
    base = run(setup, Scenario(name="b"))
    recycled = run(setup, Scenario(name="r", recycled_share=0.3))
    film_kg = next(line.quantity for line in base.lines if line.factor_id == "PET_RESIN_VIRGIN")
    expected = film_kg * 0.3 * (2.23 - 0.91)
    assert base.kg_co2e_per_kg - recycled.kg_co2e_per_kg == pytest.approx(expected)


def test_high_scrap_needs_more_material_and_still_balances(setup) -> None:
    base = run(setup, Scenario(name="b"))
    high = run(setup, Scenario(name="h", scrap_multiplier=1.5))
    assert high.kg_co2e_per_kg > base.kg_co2e_per_kg
    assert high.by_stage["materials"] > base.by_stage["materials"]
    assert high.by_stage["packaging"] == pytest.approx(base.by_stage["packaging"])
    assert high.mass_balance.passed
    assert high.mass_balance.inputs_kg > base.mass_balance.inputs_kg


def test_scenario_leaves_the_inputs_untouched(setup) -> None:
    before = setup[0].model_dump_json()
    run(setup, Scenario(name="h", scrap_multiplier=1.5, renewable_share=1, recycled_share=1))
    assert setup[0].model_dump_json() == before


def test_scrap_of_everything_is_refused(setup) -> None:
    with pytest.raises(ValueError, match="scrap all"):
        run(setup, Scenario(name="h", scrap_multiplier=10))


def test_blend_of_factors_mixes_value_and_quality() -> None:
    first = factor_for("A", 1.0).model_copy(update={"dqr_tech": 3, "dqr_geo": 1, "dqr_time": 1})
    second = factor_for("B", 3.0).model_copy(update={"dqr_tech": 5, "dqr_geo": 1, "dqr_time": 3})
    blend = blended_factor("X", first, second, 0.5)
    assert blend.value == 2.0
    assert blend.dqr_tech == 4
    assert blend.source_id == "TEST+TEST"
    assert blended_factor("X", first, factor_for("C", None), 0.5).is_placeholder


def test_scenario_table_compares_with_the_first(setup) -> None:
    base = run(setup, Scenario(name="b"))
    green = run(setup, Scenario(name="g", renewable_share=1.0))
    table = scenario_table([(Scenario(name="b"), base), (Scenario(name="g"), green)])
    assert table.loc[0, "Change"] == 0
    assert table.loc[1, "Change"] < 0
    assert scenario_table([]).empty


def line(impact: float | None, factor_id: str = "F") -> ResultLine:
    return ResultLine(stage="materials", item="X", description="X", quantity=1, unit="kg",
                      factor_id=factor_id, impact=impact)  # fmt: skip


def scored(factor_id: str, dqr: int):
    return factor_for(factor_id, 1.0).model_copy(
        update={"dqr_tech": dqr, "dqr_geo": dqr, "dqr_time": dqr}
    )


def test_monte_carlo_repeats_exactly_with_a_fixed_seed() -> None:
    factors = {"F": scored("F", 3)}
    first = monte_carlo([line(2.0)], factors, RULES, 1000, 42)
    second = monte_carlo([line(2.0)], factors, RULES, 1000, 42)
    assert np.array_equal(first.samples, second.samples)
    assert first.p95 == second.p95


def test_monte_carlo_differs_without_a_seed() -> None:
    factors = {"F": scored("F", 3)}
    first = monte_carlo([line(2.0)], factors, RULES, 1000, None)
    second = monte_carlo([line(2.0)], factors, RULES, 1000, None)
    assert not np.array_equal(first.samples, second.samples)


def test_monte_carlo_centres_on_the_calculated_value() -> None:
    result = monte_carlo([line(2.0)], {"F": scored("F", 3)}, RULES, 50_000, 1)
    assert result.deterministic == 2.0
    assert result.mean == pytest.approx(2.0, rel=0.01)
    assert result.p5 < result.p50 < result.p95


def test_weaker_data_gives_a_wider_range() -> None:
    strong = monte_carlo([line(2.0)], {"F": scored("F", 1)}, RULES, 5000, 1)
    weak = monte_carlo([line(2.0)], {"F": scored("F", 5)}, RULES, 5000, 1)
    assert weak.p95 - weak.p5 > 2 * (strong.p95 - strong.p5)


def test_lines_sharing_a_factor_share_its_error() -> None:
    factors = {"F": scored("F", 5), "G": scored("G", 5)}
    shared = monte_carlo([line(1.0, "F"), line(1.0, "F")], factors, RULES, 20_000, 1)
    separate = monte_carlo([line(1.0, "F"), line(1.0, "G")], factors, RULES, 20_000, 1)
    assert shared.samples.std() > separate.samples.std()


@pytest.mark.parametrize(
    ("factor", "expected"),
    [
        (scored("F", 1), 0.05),
        (scored("F", 5), 0.5),
        (None, 0.5),
        (factor_for("F", 1.0), 0.5),
    ],
)
def test_relative_sd_follows_the_table(factor, expected: float) -> None:
    assert relative_sd(factor, RULES) == pytest.approx(expected)


def test_relative_sd_interpolates_between_scores() -> None:
    factor = factor_for("F", 1.0).model_copy(update={"dqr_tech": 3, "dqr_geo": 4, "dqr_time": 3.5})
    assert relative_sd(factor, RULES) == pytest.approx(0.25)


def test_placeholder_lines_are_skipped() -> None:
    assert monte_carlo([line(None)], {}, RULES, 10, 1).mean == 0


def page() -> AppTest:
    at = try_demo(AppTest.from_file(HOME, default_timeout=TIMEOUT).run())
    at.switch_page("pages/7_Scenarios_and_variants.py")
    return at.run()


def test_page_shows_every_tab_with_demo_data() -> None:
    at = page()
    assert not at.exception
    assert len(at.dataframe) == 2
    labels = {m.label for m in at.metric}
    assert {"PCF per kg", "P5", "P50", "P95"} <= labels


def test_page_sliders_change_the_result() -> None:
    at = page()
    before = next(m.value for m in at.metric if m.label == "PCF per kg")
    at.slider[0].set_value(1.0)
    at.run()
    assert not at.exception
    assert next(m.value for m in at.metric if m.label == "PCF per kg") != before


def test_page_results_repeat_with_the_fixed_seed() -> None:
    at = page()
    first = next(m.value for m in at.metric if m.label == "P95")
    at.run()
    assert next(m.value for m in at.metric if m.label == "P95") == first


def test_page_prompts_without_data() -> None:
    at = AppTest.from_file(HOME, default_timeout=TIMEOUT).run()
    at.switch_page("pages/7_Scenarios_and_variants.py")
    at.run()
    assert any("No data loaded" in i.value for i in at.info)


def test_cli_runs_a_scenario(monkeypatch) -> None:
    monkeypatch.chdir(ROOT)
    product = "config/product_pet_diecut.yaml"
    base = CliRunner().invoke(app, ["run", "--product", product])
    green = CliRunner().invoke(
        app, ["run", "--product", product, "--scenario", "green_electricity"]
    )
    assert green.exit_code == 0
    assert base.stdout.splitlines()[1] != green.stdout.splitlines()[1]
