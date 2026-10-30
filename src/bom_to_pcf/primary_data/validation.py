"""Checks a supplier PCF must pass before it can replace a database value."""

from pydantic import BaseModel

from bom_to_pcf.models import (
    BomLine,
    EmissionFactor,
    Mapping,
    PrimaryDataRules,
    ProductConfig,
    SupplierPcf,
)

DAYS_PER_YEAR = 365.25
MASS_UNITS_PER_KG = {"kg": 1.0, "g": 1_000.0, "t": 0.001, "tonne": 0.001}
PIECE_UNITS = {"piece", "pc", "st"}
AREA_UNITS = {"m2", "m²"}
PIECE_FACTOR_UNIT = "kg CO2e/piece"


class SubmissionCheck(BaseModel):
    """The verdict on a submission, with a plain-English reason for every problem."""

    accepted: bool
    reasons: list[str]
    value_per_kg: float | None = None
    secondary_per_kg: float | None = None
    needs_comment: bool = False


def value_per_kg(pcf: SupplierPcf, config: ProductConfig) -> float | None:
    """Convert a PCF to kg CO2e per kg, or None if its declared unit cannot be converted."""
    if pcf.pcf_value is None or not pcf.declared_unit:
        return None
    unit = pcf.declared_unit.strip().lower()
    if unit in MASS_UNITS_PER_KG:
        return pcf.pcf_value * MASS_UNITS_PER_KG[unit]
    properties = config.materials.get(pcf.material_number)
    if properties is None:
        return None
    if unit in AREA_UNITS and properties.kg_per_m2 is not None:
        return pcf.pcf_value / properties.kg_per_m2
    if unit in PIECE_UNITS and properties.kg_per_piece is not None:
        return pcf.pcf_value / properties.kg_per_piece
    return None


def secondary_per_kg(
    material: str,
    mappings: list[Mapping],
    factors: list[EmissionFactor],
    config: ProductConfig,
) -> float | None:
    """The database value a material now uses, per kg. None if there is nothing to compare."""
    by_id = {factor.factor_id: factor for factor in factors}
    linked = [by_id.get(m.factor_id) for m in mappings if m.material_number == material]
    if not linked or any(factor is None or factor.value is None for factor in linked):
        return None
    properties = config.materials.get(material)
    total = 0.0
    for factor in linked:
        if factor.unit == PIECE_FACTOR_UNIT:
            if properties is None or properties.kg_per_piece is None:
                return None
            total += factor.value / properties.kg_per_piece
        else:
            total += factor.value
    return total


def check_submission(
    pcf: SupplierPcf,
    config: ProductConfig,
    rules: PrimaryDataRules,
    bom: list[BomLine],
    secondary: float | None,
    comment: str = "",
) -> SubmissionCheck:
    """Apply every rule and report all the problems at once, not just the first."""
    reasons: list[str] = []
    line = next((b for b in bom if b.material_number == pcf.material_number), None)
    if line is None:
        reasons.append(f"Material {pcf.material_number} is not in the BOM.")
    elif line.supplier_id and line.supplier_id != pcf.supplier_id:
        reasons.append(
            f"The BOM buys this material from {line.supplier_id}, not {pcf.supplier_id}."
        )

    per_kg = value_per_kg(pcf, config)
    if pcf.pcf_value is None:
        reasons.append("There is no PCF value.")
    elif pcf.pcf_value <= 0:
        reasons.append("The PCF value must be greater than zero.")
    elif per_kg is None:
        reasons.append(f"The declared unit '{pcf.declared_unit}' cannot be converted to kg.")

    if pcf.reference_period_end is None:
        reasons.append("There is no reference period end date.")
    else:
        max_age = config.validation.supplier_pcf_max_age_years
        age_days = (config.reference_date - pcf.reference_period_end).days
        if age_days > max_age * DAYS_PER_YEAR:
            reasons.append(
                f"The reference period ended {pcf.reference_period_end}, more than {max_age} "
                "years before the reference date."
            )
        start = pcf.reference_period_start
        if start is not None and start > pcf.reference_period_end:
            reasons.append("The reference period starts after it ends.")

    if not (pcf.method or "").strip():
        reasons.append("No calculation method is stated.")
    boundary = (pcf.boundary or "").strip().lower().replace(" ", "-")
    if boundary not in rules.allowed_boundaries:
        allowed = ", ".join(rules.allowed_boundaries)
        reasons.append(f"The boundary '{pcf.boundary or 'none'}' is not compatible ({allowed}).")
    if pcf.dqr is not None and not 1 <= pcf.dqr <= 5:
        reasons.append("The DQR must be between 1 and 5.")
    if pcf.primary_data_share is not None and not 0 <= pcf.primary_data_share <= 1:
        reasons.append("The primary data share must be between 0 and 1.")

    needs_comment = False
    if per_kg is not None and pcf.pcf_value is not None and pcf.pcf_value > 0:
        if secondary is None:
            needs_comment = True
            problem = "There is no database value to compare it with"
        else:
            low = secondary * rules.plausibility_low
            high = secondary * rules.plausibility_high
            needs_comment = not low <= per_kg <= high
            problem = (
                f"{per_kg:.3g} kg CO2e/kg is outside the plausible range {low:.3g} to {high:.3g}"
            )
        if needs_comment and not comment.strip():
            reasons.append(f"{problem}, so a reviewer comment is required.")

    return SubmissionCheck(
        accepted=not reasons,
        reasons=reasons,
        value_per_kg=per_kg,
        secondary_per_kg=secondary,
        needs_comment=needs_comment,
    )
