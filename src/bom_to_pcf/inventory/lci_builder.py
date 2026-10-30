"""Turn cleaned inputs into a life cycle inventory per kg of finished product."""

from pydantic import BaseModel

from bom_to_pcf.inventory.mass_balance import step_masses
from bom_to_pcf.io.inputs import InputBundle
from bom_to_pcf.methods.allocation import STAGE_SCRAP, overhead_kwh_per_kg, recycling_lines
from bom_to_pcf.models import (
    BomLine,
    EmissionFactor,
    LciLine,
    Mapping,
    MethodConfig,
    ProductConfig,
    SupplierPcf,
)

STAGE_MATERIALS = "materials"
STAGE_PACKAGING = "packaging"
STAGE_TRANSPORT = "inbound_transport"
STAGE_ENERGY = "converting_energy"
STAGE_OVERHEAD = "site_overhead"
KG_PER_TONNE = 1_000
MASS_FACTOR_UNIT = "kg CO2e/kg"
PIECE_FACTOR_UNIT = "kg CO2e/piece"
PIECE_BOM_UNIT = "ST"


class Inventory(BaseModel):
    """The inventory, factors added from supplier data, and flows that could not be modelled."""

    lines: list[LciLine]
    supplier_factors: list[EmissionFactor]
    gaps: list[str]


def supplier_factor(pcf: SupplierPcf) -> EmissionFactor:
    """Express a usable supplier PCF as a primary emission factor."""
    return EmissionFactor(
        factor_id=f"SUPPLIER_{pcf.supplier_id}_{pcf.material_number}",
        name=f"Supplier PCF from {pcf.supplier_id}",
        value=pcf.pcf_value,
        unit=f"kg CO2e/{pcf.declared_unit}",
        source_id=f"supplier_pcf:{pcf.supplier_id}",
        data_type="primary",
        dqr_tech=pcf.dqr,
        dqr_geo=pcf.dqr,
        dqr_time=pcf.dqr,
        status="ACTIVE",
    )


def _material_line(
    line: BomLine, stage: str, factor_id: str, factors: dict[str, EmissionFactor]
) -> LciLine | str:
    """A material's inventory line, or a description of why the units do not fit."""
    factor = factors.get(factor_id)
    if factor is None:
        return f"{line.description}: factor {factor_id} is not in the factor table"
    if factor.unit == PIECE_FACTOR_UNIT:
        if line.uom != PIECE_BOM_UNIT:
            return (
                f"{line.description}: factor {factor_id} is per piece but the BOM uses {line.uom}"
            )
        quantity = line.component_qty * line.qty_kg_per_kg_product / line.qty_kg
        unit = "piece"
    elif factor.unit == MASS_FACTOR_UNIT:
        quantity = line.qty_kg_per_kg_product
        unit = "kg"
    else:
        return f"{line.description}: factor {factor_id} has unsupported unit {factor.unit}"
    return LciLine(
        stage=stage,
        item=line.material_number,
        description=line.description,
        quantity=quantity,
        unit=unit,
        factor_id=factor_id,
        mass_kg=line.qty_kg_per_kg_product,
    )


def build_lci(
    bundle: InputBundle,
    config: ProductConfig,
    method: MethodConfig,
    mappings: list[Mapping],
    factors: list[EmissionFactor],
) -> Inventory:
    """Build inventory lines for materials, transport, energy and scrap."""
    lines: list[LciLine] = []
    gaps: list[str] = []
    allocation = method.allocation
    usable_pcfs = {
        pcf.material_number: pcf
        for pcf in bundle.supplier_pcfs
        if pcf.usable and pcf.declared_unit == "kg"
    }
    supplier_factors = [supplier_factor(pcf) for pcf in usable_pcfs.values()]
    known = {factor.factor_id: factor for factor in [*factors, *supplier_factors]}

    for line in bundle.bom:
        material = line.material_number
        stage = STAGE_MATERIALS if config.role_of(material) == "product" else STAGE_PACKAGING
        if material in usable_pcfs:
            factor_ids = [supplier_factor(usable_pcfs[material]).factor_id]
        else:
            factor_ids = [m.factor_id for m in mappings if m.material_number == material]
        if not factor_ids:
            gaps.append(f"{line.description}: no emission factor is mapped to this material")
        for factor_id in factor_ids:
            built = _material_line(line, stage, factor_id, known)
            if isinstance(built, str):
                gaps.append(built)
            else:
                lines.append(built)

    bom_by_material = {line.material_number: line for line in bundle.bom}
    for leg in bundle.transport:
        line = bom_by_material.get(leg.material_number)
        if line is None:
            continue
        leg_factors = method.factors.transport.get(leg.mode)
        if not leg_factors:
            gaps.append(f"Transport leg {leg.leg_id}: no factor for mode '{leg.mode}'")
            continue
        tkm = line.qty_kg_per_kg_product / KG_PER_TONNE * leg.distance_km
        lines.extend(
            LciLine(
                stage=STAGE_TRANSPORT,
                item=leg.leg_id,
                description=f"{line.description}, {leg.origin} to {leg.destination}, {leg.mode}",
                quantity=tkm,
                unit="tkm",
                factor_id=factor_id,
            )
            for factor_id in leg_factors
        )

    masses = step_masses(bundle.routing, allocation.overhead_step_id)
    routing_by_id = {step.step_id: step for step in bundle.routing}
    for mass in masses:
        step = routing_by_id[mass.step_id]
        lines.extend(
            LciLine(
                stage=STAGE_ENERGY,
                item=step.step_id,
                description=f"Electricity, {step.step_name}",
                quantity=step.kwh_per_kg * mass.input_kg,
                unit="kWh",
                factor_id=factor_id,
            )
            for factor_id in method.factors.electricity
        )
        lines.extend(_scrap_lines(mass, step.step_name, method, gaps))

    overhead = routing_by_id.get(allocation.overhead_step_id)
    if overhead is None:
        gaps.append(f"Site overhead: routing has no step {allocation.overhead_step_id}")
    else:
        kwh = overhead_kwh_per_kg(overhead, bundle.routing, masses, allocation)
        lines.extend(
            LciLine(
                stage=STAGE_OVERHEAD,
                item=overhead.step_id,
                description=f"Electricity, {overhead.step_name}",
                quantity=kwh,
                unit="kWh",
                factor_id=factor_id,
            )
            for factor_id in method.factors.electricity
        )
    return Inventory(lines=lines, supplier_factors=supplier_factors, gaps=gaps)


def _scrap_lines(mass, step_name: str, method: MethodConfig, gaps: list[str]) -> list[LciLine]:
    if mass.scrap_kg == 0:
        return []
    if mass.scrap_destination == "recycling":
        return recycling_lines(mass, method.allocation)
    scrap_factors = method.factors.scrap.get(mass.scrap_destination)
    if not scrap_factors:
        gaps.append(f"Scrap from {step_name}: no treatment factor for '{mass.scrap_destination}'")
        return []
    return [
        LciLine(
            stage=STAGE_SCRAP,
            item=f"scrap_{mass.step_id}",
            description=f"Scrap from {step_name} to {mass.scrap_destination}",
            quantity=mass.scrap_kg,
            unit="kg",
            factor_id=factor_id,
            mass_kg=mass.scrap_kg,
        )
        for factor_id in scrap_factors
    ]
