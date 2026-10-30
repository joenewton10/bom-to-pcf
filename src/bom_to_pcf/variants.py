"""Calculate a whole product family from one parameterised model."""

from itertools import product as combinations
from pathlib import Path

import pandas as pd
import yaml
from pydantic import BaseModel

from bom_to_pcf.io.inputs import InputBundle
from bom_to_pcf.models import (
    AnalysisConfig,
    BomLine,
    EmissionFactor,
    Mapping,
    MethodConfig,
    PcfResult,
    ProductConfig,
)
from bom_to_pcf.scenarios import Scenario, run_scenario

GRAMS_PER_KG = 1_000
TABLE_COLUMNS = [
    "Thickness (µm)",
    "Adhesive",
    "Recycled share",
    "Part mass (g)",
    "kg CO2e per kg",
    "kg CO2e per 1,000 parts",
    "Status",
]


class FamilyConfig(BaseModel):
    """The product family, loaded from YAML."""

    product: str
    film_material: str
    adhesive_materials: list[str]
    thickness_um: list[float]
    adhesive: list[bool]
    recycled_share: list[float]

    @classmethod
    def from_yaml(cls, path: str | Path) -> "FamilyConfig":
        return cls.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


class Variant(BaseModel):
    thickness_um: float
    adhesive: bool
    recycled_share: float


class VariantResult(BaseModel):
    variant: Variant
    part_mass_g: float
    result: PcfResult


def family_variants(family: FamilyConfig) -> list[Variant]:
    return [
        Variant(thickness_um=thickness, adhesive=adhesive, recycled_share=share)
        for thickness, adhesive, share in combinations(
            family.thickness_um, family.adhesive, family.recycled_share
        )
    ]


def build_variant(
    bundle: InputBundle, config: ProductConfig, family: FamilyConfig, variant: Variant
) -> tuple[InputBundle, ProductConfig]:
    """Rescale the BOM for a variant.

    Film mass follows thickness, and the part mass follows the product material. The same part
    area and scrap rates are assumed, so the mass balance is unchanged.
    """
    film = config.materials[family.film_material]
    film_ratio = variant.thickness_um / film.thickness_um

    def is_product(line: BomLine) -> bool:
        return config.role_of(line.material_number) == "product"

    def kept(line: BomLine) -> bool:
        return variant.adhesive or line.material_number not in family.adhesive_materials

    def scale(line: BomLine) -> float:
        return film_ratio if line.material_number == family.film_material else 1.0

    base_input = sum(line.qty_kg for line in bundle.bom if is_product(line))
    new_input = sum(
        line.qty_kg * scale(line) for line in bundle.bom if is_product(line) and kept(line)
    )
    mass_ratio = new_input / base_input

    lines = []
    for line in bundle.bom:
        if not kept(line):
            continue
        base_kg = line.qty_kg / line.qty_kg_per_kg_product
        qty_kg = line.qty_kg * scale(line)
        lines.append(
            line.model_copy(
                update={
                    "qty_kg": qty_kg,
                    "component_qty": line.component_qty * scale(line),
                    "qty_kg_per_kg_product": qty_kg / (base_kg * mass_ratio),
                }
            )
        )

    materials = dict(config.materials)
    materials[family.film_material] = film.model_copy(update={"thickness_um": variant.thickness_um})
    variant_config = config.model_copy(
        update={"materials": materials, "part_mass_g": config.part_mass_g * mass_ratio}
    )
    return bundle.model_copy(update={"bom": lines}), variant_config


def run_family(
    bundle: InputBundle,
    config: ProductConfig,
    method: MethodConfig,
    factors: list[EmissionFactor],
    mappings: list[Mapping],
    family: FamilyConfig,
    analysis: AnalysisConfig,
) -> list[VariantResult]:
    """Calculate every variant in the family."""
    results = []
    for variant in family_variants(family):
        variant_bundle, variant_config = build_variant(bundle, config, family, variant)
        scenario = Scenario(name="variant", recycled_share=variant.recycled_share)
        result = run_scenario(
            variant_bundle, variant_config, method, factors, mappings, scenario, analysis
        )
        results.append(
            VariantResult(variant=variant, part_mass_g=variant_config.part_mass_g, result=result)
        )
    return results


def family_table(results: list[VariantResult]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Thickness (µm)": item.variant.thickness_um,
                "Adhesive": "Yes" if item.variant.adhesive else "No",
                "Recycled share": item.variant.recycled_share,
                "Part mass (g)": item.part_mass_g,
                "kg CO2e per kg": item.result.kg_co2e_per_kg,
                "kg CO2e per 1,000 parts": item.result.kg_co2e_per_1000_pieces,
                "Status": item.result.status_label,
            }
            for item in results
        ],
        columns=TABLE_COLUMNS,
    )
