import pytest
from engine_helpers import load_case
from test_engine import run

from bom_to_pcf.inventory.mass_balance import step_masses
from bom_to_pcf.methods.allocation import overhead_kwh_per_kg
from bom_to_pcf.methods.cutoff import apply_cut_off
from bom_to_pcf.models import CutOffRules, ResultLine


def result_line(item: str, impact: float | None, mass: float | None = None) -> ResultLine:
    return ResultLine(
        stage="materials",
        item=item,
        description=item,
        quantity=1,
        unit="kg",
        factor_id="F",
        mass_kg=mass,
        impact=impact,
    )


def test_recycling_cut_off_gives_no_burden_or_credit() -> None:
    result = run(load_case())
    scrap = [line for line in result.lines if line.stage == "scrap_treatment"]
    assert scrap[0].impact == 0
    assert scrap[0].quantity == pytest.approx(0.25)
    assert "Cut-off" in scrap[0].note


def test_recycling_substitution_adds_burden_and_credit() -> None:
    case = load_case()
    case.method.allocation.scrap_recycling = "substitution"
    # 0.25 kg x (0.5 burden - 2.0 avoided) = -0.375
    assert run(case).by_stage["scrap_treatment"] == pytest.approx(-0.375)


def test_incinerated_scrap_is_charged_to_the_product() -> None:
    case = load_case()
    case.bundle.routing[0].scrap_destination = "incineration"
    # 0.25 kg x 3.0
    assert run(case).by_stage["scrap_treatment"] == pytest.approx(0.75)


def test_overhead_by_mass() -> None:
    case = load_case()
    overhead = case.bundle.routing[2]
    masses = step_masses(case.bundle.routing, "OH")
    kwh = overhead_kwh_per_kg(overhead, case.bundle.routing, masses, case.method.allocation)
    assert kwh == pytest.approx(0.1)


def test_overhead_by_machine_hours() -> None:
    case = load_case()
    case.method.allocation.overhead_method = "machine_hours"
    overhead = case.bundle.routing[2]
    masses = step_masses(case.bundle.routing, "OH")
    kwh = overhead_kwh_per_kg(overhead, case.bundle.routing, masses, case.method.allocation)
    # Machine hours 1.25/100 + 1/50 = 0.0325. Site load 20 kW over 2 machines = 10 kW each.
    assert kwh == pytest.approx(0.325)


def test_cut_off_needs_both_mass_and_impact_to_be_small() -> None:
    rules = CutOffRules(flow_share=0.01, total_share=0.05)
    lines = [result_line("big", 100, 50), result_line("light_but_high", 5, 0.01)]
    lines.append(result_line("heavy_but_low", 0.5, 5))
    lines.append(result_line("small", 0.5, 0.01))
    _, excluded = apply_cut_off(lines, rules)
    assert {line.item for line in excluded} == {"small"}


def test_cut_off_counts_a_material_with_two_factors_once() -> None:
    rules = CutOffRules(flow_share=0.01, total_share=0.05)
    # Mass share is 1.2 / 100 = 1.2%, kept. Counting "film" twice would make it 0.6% and drop it.
    lines = [result_line("film", 50, 98.8), result_line("film", 50, 98.8)]
    lines.append(result_line("pallet", 0.1, 1.2))
    _, excluded = apply_cut_off(lines, rules)
    assert excluded == []


def test_cut_off_stops_at_the_total_limit() -> None:
    rules = CutOffRules(flow_share=0.01, total_share=0.015)
    lines = [result_line("big", 100)] + [result_line(f"s{i}", 0.9) for i in range(3)]
    _, excluded = apply_cut_off(lines, rules)
    assert len({line.item for line in excluded}) == 1


def test_cut_off_never_excludes_a_placeholder() -> None:
    rules = CutOffRules(flow_share=0.5, total_share=0.5)
    lines = [result_line("big", 100), result_line("unknown", None)]
    _, excluded = apply_cut_off(lines, rules)
    assert excluded == []


def test_cut_off_with_no_known_impact_keeps_everything() -> None:
    lines = [result_line("unknown", None)]
    kept, excluded = apply_cut_off(lines, CutOffRules(flow_share=0.01, total_share=0.05))
    assert kept == lines
    assert excluded == []
