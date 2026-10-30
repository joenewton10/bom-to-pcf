"""Pure-Python calculation engine and the full calculation run."""

from collections import defaultdict

from bom_to_pcf.engine.base import Engine
from bom_to_pcf.inventory.lci_builder import STAGE_MATERIALS, STAGE_PACKAGING, build_lci
from bom_to_pcf.inventory.mass_balance import check_mass_balance
from bom_to_pcf.io.inputs import InputBundle
from bom_to_pcf.methods.cutoff import apply_cut_off
from bom_to_pcf.methods.data_quality import aggregate_dqr
from bom_to_pcf.methods.primary_share import primary_data_share
from bom_to_pcf.models import (
    EmissionFactor,
    LciLine,
    Mapping,
    MethodConfig,
    PcfResult,
    ProductConfig,
    ResultLine,
)

LABEL_FINAL = "Calculated"
LABEL_DRAFT = "DRAFT"
LABEL_PLACEHOLDERS = "DRAFT — contains placeholders"
PIECES_PER_REPORT_UNIT = 1_000
GRAMS_PER_KG = 1_000


class PythonEngine(Engine):
    """Multiplies each inventory quantity by its emission factor."""

    name = "python"

    def impacts(self, lines: list[LciLine], factors: dict[str, EmissionFactor]) -> list[ResultLine]:
        results = []
        for line in lines:
            if line.factor_id is None:
                impact = 0.0
            else:
                value = factors[line.factor_id].value
                impact = None if value is None else line.quantity * value
            results.append(ResultLine(**line.model_dump(), impact=impact))
        return results


def run_pcf(
    bundle: InputBundle,
    config: ProductConfig,
    method: MethodConfig,
    factors: list[EmissionFactor],
    mappings: list[Mapping],
    engine: Engine | None = None,
) -> PcfResult:
    """Calculate a footprint and state every reason it is a draft or incomplete."""
    engine = engine or PythonEngine()
    inventory = build_lci(bundle, config, method, mappings, factors)
    known = {f.factor_id: f for f in [*factors, *inventory.supplier_factors]}
    calculated = engine.impacts(inventory.lines, known)
    kept, excluded = apply_cut_off(calculated, method.cut_off)

    balance = check_mass_balance(
        bundle.bom,
        bundle.routing,
        config,
        method.allocation.overhead_step_id,
        method.mass_balance.tolerance_share,
    )

    placeholder_lines = [line for line in kept if line.impact is None]
    missing = [
        f"{line.description}: factor {line.factor_id} has no value "
        f"({line.quantity:.3g} {line.unit} per kg of product)"
        for line in placeholder_lines
    ]
    missing.extend(inventory.gaps)

    draft_reasons: list[str] = []
    if placeholder_lines:
        draft_reasons.append(f"{len(placeholder_lines)} inventory lines use placeholder factors.")
    if inventory.gaps:
        draft_reasons.append(f"{len(inventory.gaps)} flows could not be modelled.")
    used_materials = {line.item for line in calculated if line.stage in _MATERIAL_STAGES}
    unreviewed = {
        m.material_number
        for m in mappings
        if m.review_status != "approved" and m.material_number in used_materials
    }
    if unreviewed:
        draft_reasons.append(f"{len(unreviewed)} materials have unreviewed factor matches.")
    if not balance.passed:
        draft_reasons.append(
            f"The mass balance is out by {balance.imbalance_share:.1%}, "
            f"above the {balance.tolerance_share:.1%} tolerance."
        )
    if bundle.has_errors:
        draft_reasons.append("The inputs have validation errors.")

    is_partial = bool(missing)
    if placeholder_lines:
        status_label = LABEL_PLACEHOLDERS
    elif draft_reasons:
        status_label = LABEL_DRAFT
    else:
        status_label = LABEL_FINAL
    if is_partial:
        status_label += " — partial total, the true footprint is higher"

    total = sum(line.impact or 0 for line in kept)
    known_impact = sum(abs(line.impact or 0) for line in calculated)
    excluded_impact = sum(abs(line.impact or 0) for line in excluded)
    by_stage: dict[str, float] = defaultdict(float)
    by_material: dict[str, float] = defaultdict(float)
    for line in kept:
        by_stage[line.stage] += line.impact or 0
        if line.stage in _MATERIAL_STAGES:
            by_material[line.description] += line.impact or 0

    return PcfResult(
        kg_co2e_per_kg=total,
        kg_co2e_per_1000_pieces=total * config.part_mass_g / GRAMS_PER_KG * PIECES_PER_REPORT_UNIT,
        gwp_set=method.gwp_set,
        by_stage=dict(by_stage),
        by_material=dict(by_material),
        lines=kept,
        excluded=excluded,
        excluded_share=excluded_impact / known_impact if known_impact else 0.0,
        is_draft=bool(draft_reasons),
        is_partial=is_partial,
        status_label=status_label,
        draft_reasons=draft_reasons,
        missing=missing,
        known_omissions=method.known_omissions,
        primary_data_share=primary_data_share(kept, known, method.primary_share.site_stages),
        dqr=aggregate_dqr(kept, known),
        mass_balance=balance,
    )


_MATERIAL_STAGES = (STAGE_MATERIALS, STAGE_PACKAGING)
