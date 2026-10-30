"""Builds the hand-calculated reference case from its YAML fixture."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from bom_to_pcf.io.inputs import InputBundle
from bom_to_pcf.models import (
    BomLine,
    EmissionFactor,
    Mapping,
    MethodConfig,
    ProductConfig,
    RoutingStep,
    TransportLeg,
)

FIXTURE = Path(__file__).parent / "fixtures" / "reference_case.yaml"


@dataclass
class Case:
    bundle: InputBundle
    config: ProductConfig
    method: MethodConfig
    factors: list[EmissionFactor]
    mappings: list[Mapping]
    expected: dict


def bom_line(material: str, description: str, qty_kg: float, base_kg: float = 2.0) -> BomLine:
    return BomLine(
        material_number=material,
        description=description,
        parent_material="900",
        bom_level=1,
        component_qty=qty_kg,
        uom="KG",
        base_qty=base_kg,
        base_uom="KG",
        item_category="L",
        plant="P",
        valid_from=date(2024, 1, 1),
        supplier_id="S",
        qty_kg=qty_kg,
        qty_kg_per_kg_product=qty_kg / base_kg,
        source_row=2,
    )


def factor(factor_id: str, value: float | None, unit: str, dqr: float | None = 1) -> EmissionFactor:
    return EmissionFactor(
        factor_id=factor_id,
        name=factor_id,
        value=value,
        unit=unit,
        source_id="" if value is None else "TEST",
        data_type="secondary",
        dqr_tech=dqr,
        dqr_geo=dqr,
        dqr_time=dqr,
        status="PLACEHOLDER" if value is None else "ACTIVE",
    )


def load_case() -> Case:
    raw = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    bundle = InputBundle(
        bom=[bom_line(b["material"], b["description"], b["qty_kg"]) for b in raw["bom"]],
        routing=[
            RoutingStep(
                step_id=r["id"],
                step_name=r["id"],
                machine="M",
                throughput_kg_per_h=r["throughput"],
                power_kw=r["power"],
                utilisation=r["utilisation"],
                scrap_rate=r["scrap"],
                scrap_destination=r["destination"],
            )
            for r in raw["routing"]
        ],
        transport=[
            TransportLeg(
                leg_id=t["id"],
                material_number=t["material"],
                supplier_id="S",
                origin="A",
                destination="B",
                mode="road",
                distance_km=t["km"],
            )
            for t in raw["transport"]
        ],
    )
    return Case(
        bundle=bundle,
        config=ProductConfig.model_validate(raw["product"]),
        method=MethodConfig.model_validate(raw["method"]),
        factors=[factor(f["id"], f["value"], f["unit"], f["dqr"]) for f in raw["factors"]],
        mappings=[
            Mapping(material_number=m["material"], factor_id=m["factor"], review_status="approved")
            for m in raw["mappings"]
        ],
        expected=raw["expected"],
    )
