from datetime import date

import pytest
from engine_helpers import load_case
from test_engine import run

from bom_to_pcf.methods.data_quality import aggregate_dqr
from bom_to_pcf.methods.primary_share import primary_data_share
from bom_to_pcf.models import SupplierPcf


def supplier_pcf(**overrides: object) -> SupplierPcf:
    # Test values for the calculation, not emission data.
    fields = {
        "supplier_id": "S",
        "material_number": "1",
        "pcf_value": 1.0,
        "declared_unit": "kg",
        "reference_period_end": date(2025, 1, 1),
        "method": "ISO 14067",
        "boundary": "cradle-to-gate",
        "dqr": 1.0,
        "primary_data_share": 0.5,
    }
    return SupplierPcf(**(fields | overrides))


def test_usable_supplier_pcf_replaces_secondary_and_raises_primary_share() -> None:
    case = load_case()
    before = run(case)
    case.bundle.supplier_pcfs = [supplier_pcf()]
    after = run(case)
    # Film 1.25 kg x 1.0 instead of x 2.0.
    assert after.by_stage["materials"] == pytest.approx(1.25)
    assert after.primary_data_share > before.primary_data_share
    film = [line for line in after.lines if line.stage == "materials"]
    assert film[0].factor_id == "SUPPLIER_S_1"


def test_unusable_supplier_pcf_changes_nothing() -> None:
    case = load_case()
    before = run(case)
    case.bundle.supplier_pcfs = [supplier_pcf(fallback_reason="expired")]
    assert run(case).kg_co2e_per_kg == before.kg_co2e_per_kg


def test_supplier_pcf_in_another_unit_is_not_used() -> None:
    case = load_case()
    before = run(case)
    case.bundle.supplier_pcfs = [supplier_pcf(declared_unit="m2")]
    assert run(case).kg_co2e_per_kg == before.kg_co2e_per_kg


def test_share_is_zero_with_no_impact() -> None:
    assert primary_data_share([], {}) == 0.0


def test_dqr_is_none_with_no_scores() -> None:
    assert aggregate_dqr([], {}).overall is None
