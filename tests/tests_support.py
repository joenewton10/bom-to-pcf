"""Small builders shared by the primary data tests. Numbers are test inputs, not emission data."""

from bom_to_pcf.models import EmissionFactor


def factor_for(factor_id: str, value: float | None, unit: str = "kg CO2e/kg") -> EmissionFactor:
    return EmissionFactor(
        factor_id=factor_id,
        name=factor_id,
        value=value,
        unit=unit,
        source_id="" if value is None else "TEST",
        data_type="secondary",
        status="PLACEHOLDER" if value is None else "ACTIVE",
    )
