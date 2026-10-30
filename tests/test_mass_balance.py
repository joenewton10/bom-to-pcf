import pytest
from engine_helpers import bom_line, load_case

from bom_to_pcf.inventory.mass_balance import check_mass_balance, step_masses


def balance(case):
    return check_mass_balance(case.bundle.bom, case.bundle.routing, case.config, "OH", 0.01)


def test_reference_case_closes_exactly() -> None:
    result = balance(load_case())
    assert result.passed
    assert result.inputs_kg == pytest.approx(1.25)
    assert result.scrap_kg == pytest.approx(0.25)
    assert result.imbalance_kg == pytest.approx(0)


def test_packaging_is_not_part_of_the_balance() -> None:
    assert balance(load_case()).inputs_kg == pytest.approx(1.25)


def test_step_masses_grow_upstream_of_scrap() -> None:
    masses = step_masses(load_case().bundle.routing, "OH")
    assert [m.step_id for m in masses] == ["S1", "S2"]
    assert masses[0].input_kg == pytest.approx(1.25)
    assert masses[1].input_kg == pytest.approx(1.0)


@pytest.mark.parametrize("film_kg", [1.5, 4.0])
def test_broken_input_fails_the_balance(film_kg: float) -> None:
    case = load_case()
    case.bundle.bom[0] = bom_line("1", "Film", film_kg)
    assert not balance(case).passed


def test_empty_bom_fails_the_balance() -> None:
    case = load_case()
    case.bundle.bom = []
    result = balance(case)
    assert not result.passed
    assert result.imbalance_share == 1.0
