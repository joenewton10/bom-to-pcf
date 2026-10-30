from datetime import date

import pytest
from test_replacement import RULES, line, submission
from tests_support import factor_for

from bom_to_pcf.models import Mapping
from bom_to_pcf.primary_data.validation import (
    check_submission,
    secondary_per_kg,
    value_per_kg,
)


def check(config, pcf, secondary=2.0, comment=""):
    return check_submission(pcf, config, RULES, [line()], secondary, comment)


def test_valid_submission_is_accepted(config) -> None:
    result = check(config, submission())
    assert result.accepted
    assert result.reasons == []
    assert result.value_per_kg == 1.5


@pytest.mark.parametrize(
    ("overrides", "fragment"),
    [
        ({"declared_unit": "litre"}, "cannot be converted"),
        ({"declared_unit": None}, "cannot be converted"),
        ({"reference_period_end": date(2021, 12, 31)}, "more than 3 years"),
        ({"reference_period_end": None}, "no reference period"),
        ({"reference_period_start": date(2030, 1, 1)}, "starts after"),
        ({"method": None}, "No calculation method"),
        ({"method": "  "}, "No calculation method"),
        ({"boundary": "gate-to-gate"}, "not compatible"),
        ({"boundary": None}, "not compatible"),
        ({"pcf_value": None}, "no PCF value"),
        ({"pcf_value": 0.0}, "greater than zero"),
        ({"pcf_value": -1.0}, "greater than zero"),
        ({"material_number": "999"}, "not in the BOM"),
        ({"supplier_id": "OTHER"}, "not OTHER"),
        ({"dqr": 6.0}, "between 1 and 5"),
        ({"primary_data_share": 40.0}, "between 0 and 1"),
    ],
)
def test_invalid_submission_is_rejected_with_a_reason(config, overrides, fragment) -> None:
    result = check(config, submission(**overrides))
    assert not result.accepted
    assert any(fragment in reason for reason in result.reasons)


def test_all_problems_are_reported_together(config) -> None:
    result = check(config, submission(method=None, boundary="gate-to-gate"))
    assert len(result.reasons) == 2


def test_boundary_spelling_is_forgiving(config) -> None:
    assert check(config, submission(boundary="Cradle to Gate")).accepted


@pytest.mark.parametrize("value", [0.3, 11.0])
def test_implausible_value_needs_a_comment(config, value: float) -> None:
    rejected = check(config, submission(pcf_value=value))
    assert not rejected.accepted
    assert "plausible range" in rejected.reasons[0]
    accepted = check(config, submission(pcf_value=value), comment="Confirmed with supplier")
    assert accepted.accepted
    assert accepted.needs_comment


@pytest.mark.parametrize("value", [0.4, 10.0])
def test_values_at_the_plausibility_limits_pass(config, value: float) -> None:
    assert check(config, submission(pcf_value=value)).accepted


def test_no_database_value_needs_a_comment(config) -> None:
    rejected = check(config, submission(), secondary=None)
    assert any("no database value" in reason for reason in rejected.reasons)
    assert check(config, submission(), secondary=None, comment="OK").accepted


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        (2.0, "kg", 2.0),
        (2.0, "KG", 2.0),
        (0.002, "g", 2.0),
        (2000.0, "t", 2.0),
    ],
)
def test_mass_units_convert(config, value, unit, expected) -> None:
    pcf = submission(pcf_value=value, declared_unit=unit)
    assert value_per_kg(pcf, config) == pytest.approx(expected)


def test_area_and_piece_units_use_material_properties(config) -> None:
    film = submission(material_number="100001", pcf_value=1.0, declared_unit="m2")
    assert value_per_kg(film, config) == pytest.approx(1 / (1390 * 125e-6))
    pallet = submission(material_number="100006", pcf_value=4.0, declared_unit="piece")
    assert value_per_kg(pallet, config) == pytest.approx(4 / 20)


def test_area_unit_without_properties_cannot_convert(config) -> None:
    assert value_per_kg(submission(material_number="100006", declared_unit="m2"), config) is None
    assert value_per_kg(submission(material_number="X", declared_unit="m2"), config) is None


def _mapping(factor_id: str, material: str = "100002") -> Mapping:
    return Mapping(material_number=material, factor_id=factor_id, review_status="approved")


def test_secondary_sums_a_materials_factors(config) -> None:
    factors = [factor_for("A", 1.0), factor_for("B", 0.5)]
    assert secondary_per_kg("100002", [_mapping("A"), _mapping("B")], factors, config) == 1.5


def test_secondary_converts_a_per_piece_factor(config) -> None:
    factors = [factor_for("P", 4.0, "kg CO2e/piece")]
    assert secondary_per_kg("100006", [_mapping("P", "100006")], factors, config) == 0.2
    assert secondary_per_kg("100002", [_mapping("P")], factors, config) is None


def test_secondary_is_none_without_a_usable_factor(config) -> None:
    assert secondary_per_kg("100002", [], [], config) is None
    placeholder = [factor_for("A", None)]
    assert secondary_per_kg("100002", [_mapping("A")], placeholder, config) is None
