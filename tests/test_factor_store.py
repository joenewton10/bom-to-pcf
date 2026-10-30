from pathlib import Path

import pytest

from bom_to_pcf.io.factor_store import FACTOR_COLUMNS, load_factors, read_source_ids
from bom_to_pcf.models import Severity

ROOT = Path(__file__).resolve().parents[1]
FACTORS = ROOT / "data" / "factors" / "emission_factors.csv"
SOURCES = ROOT / "data" / "factors" / "SOURCES.md"
DATA_GAPS = ROOT / "docs" / "data_gaps.md"
TEST_SOURCES = b"# Sources\n\n## SRC_A\n\nA source.\n"


def factor_file(**overrides: str) -> bytes:
    # Numbers here are test inputs for the loader, not emission data.
    row = {
        "factor_id": "F1",
        "name": "Test factor",
        "value": "1.5",
        "unit": "kg CO2e/kg",
        "gwp_basis": "AR6",
        "geography": "DE",
        "reference_year": "2024",
        "source_id": "SRC_A",
        "data_type": "secondary",
        "dqr_tech": "1",
        "dqr_geo": "2",
        "dqr_time": "3",
        "notes": "",
        "status": "ACTIVE",
    } | overrides
    return (",".join(FACTOR_COLUMNS) + "\n" + ",".join(row.values()) + "\n").encode()


def test_shipped_factors_pass_every_sourcing_rule() -> None:
    factors, issues = load_factors(FACTORS, SOURCES)
    assert factors
    assert not [issue for issue in issues if issue.severity is Severity.ERROR]
    known = read_source_ids(SOURCES)
    for factor in factors:
        if not factor.is_placeholder:
            assert factor.value is not None, factor.factor_id
            assert factor.source_id in known, factor.factor_id


def test_every_source_section_is_used() -> None:
    factors, _ = load_factors(FACTORS, SOURCES)
    assert read_source_ids(SOURCES) == {f.source_id for f in factors if f.source_id}


def test_shipped_placeholders_are_listed_in_data_gaps() -> None:
    factors, _ = load_factors(FACTORS, SOURCES)
    gaps = DATA_GAPS.read_text(encoding="utf-8")
    for factor in [factor for factor in factors if factor.is_placeholder]:
        assert factor.value is None
        assert factor.factor_id in gaps


def test_proxies_are_named_and_carry_the_worst_technology_score() -> None:
    factors, _ = load_factors(FACTORS, SOURCES)
    proxies = [factor for factor in factors if "PROXY" in factor.name]
    assert {factor.factor_id for factor in proxies} == {"PET_FILM_CONVERSION", "LINER_SILICONE"}
    assert all(factor.dqr_tech == 5 for factor in proxies)
    gaps = DATA_GAPS.read_text(encoding="utf-8")
    assert all(factor.factor_id in gaps for factor in proxies)


def test_liner_proxy_matches_its_documented_calculation() -> None:
    factors, _ = load_factors(FACTORS, SOURCES)
    liner = next(factor for factor in factors if factor.factor_id == "LINER_SILICONE")
    assert liner.value == pytest.approx((58.75 * 0.462 + 1.25 * 6.36) / 60, abs=0.001)


def test_secondary_factors_respect_the_pact_quality_matrix() -> None:
    """PACT Methodology 3.0, Table 12: secondary data can score 3 at best on technology."""
    factors, _ = load_factors(FACTORS, SOURCES)
    for factor in factors:
        if factor.data_type == "secondary" and not factor.is_placeholder:
            assert factor.dqr_tech >= 3, factor.factor_id


def test_time_scores_follow_the_pact_matrix_for_a_2025_reference_year() -> None:
    factors, _ = load_factors(FACTORS, SOURCES)
    for factor in factors:
        if factor.factor_id == "PET_FILM_CONVERSION":
            continue  # built from a 2011 energy benchmark, so it takes its oldest input's score
        gap = abs(2025 - factor.reference_year)
        assert factor.dqr_time == min(max(gap, 1), 5), factor.factor_id


def test_factors_from_outside_the_site_region_score_worst_on_geography() -> None:
    factors, _ = load_factors(FACTORS, SOURCES)
    for factor in factors:
        if factor.geography in {"GB", "US", "CL"}:
            assert factor.dqr_geo == 5, factor.factor_id


def test_valid_factor_loads() -> None:
    factors, issues = load_factors(factor_file(), TEST_SOURCES)
    assert factors[0].value == 1.5
    assert issues == []


@pytest.mark.parametrize(
    ("overrides", "fragment"),
    [
        ({"source_id": ""}, "no source_id"),
        ({"source_id": "UNKNOWN"}, "not listed"),
        ({"value": ""}, "not marked PLACEHOLDER"),
        ({"status": "DRAFT"}, "not ACTIVE"),
        ({"status": "PLACEHOLDER"}, "must not have a value"),
    ],
)
def test_sourcing_rules_reject_factor(overrides: dict[str, str], fragment: str) -> None:
    factors, issues = load_factors(factor_file(**overrides), TEST_SOURCES)
    assert factors == []
    assert issues[0].code == "unsourced_factor"
    assert fragment in issues[0].message


def test_placeholder_without_value_loads_with_warning() -> None:
    factors, issues = load_factors(
        factor_file(value="", source_id="", status="PLACEHOLDER"), TEST_SOURCES
    )
    assert factors[0].is_placeholder
    assert issues[0].severity is Severity.WARNING
    assert issues[0].code == "placeholder_factor"


@pytest.mark.parametrize(
    "overrides", [{"dqr_tech": "6"}, {"value": "-1"}, {"value": "abc"}, {"data_type": "guess"}]
)
def test_invalid_values_are_rejected(overrides: dict[str, str]) -> None:
    factors, issues = load_factors(factor_file(**overrides), TEST_SOURCES)
    assert factors == []
    assert issues[0].code == "invalid_factor"


def test_duplicate_factor_id_is_rejected() -> None:
    row = factor_file().decode().splitlines()[1]
    factors, issues = load_factors(factor_file() + (row + "\n").encode(), TEST_SOURCES)
    assert len(factors) == 1
    assert "used twice" in issues[0].message


def test_missing_columns_are_reported() -> None:
    assert load_factors(b"factor_id\nF1\n", TEST_SOURCES)[1][0].code == "missing_columns"
