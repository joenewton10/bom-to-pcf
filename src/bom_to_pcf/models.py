"""Data models shared by the readers, the engine and the app."""

from datetime import date
from enum import StrEnum
from pathlib import Path

import pandas as pd
import yaml
from pydantic import BaseModel, Field


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Issue(BaseModel):
    """One finding from input validation, written for an LCA reviewer."""

    severity: Severity
    code: str
    source: str
    message: str
    row: int | None = None
    material: str | None = None


def issues_table(issues: list[Issue]) -> pd.DataFrame:
    """Return issues as a table, most severe first, keeping file order within a severity."""
    columns = ["severity", "source", "row", "material", "code", "message"]
    rank = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
    ordered = sorted(issues, key=lambda issue: rank[issue.severity])
    table = pd.DataFrame([issue.model_dump(mode="json") for issue in ordered], columns=columns)
    return table.astype({"row": "Int64"})


class MaterialProperties(BaseModel):
    """Physical properties used to convert a material's BOM unit to kg."""

    density_kg_m3: float | None = Field(default=None, gt=0)
    thickness_um: float | None = Field(default=None, gt=0)
    grammage_g_m2: float | None = Field(default=None, gt=0)
    kg_per_piece: float | None = Field(default=None, gt=0)

    @property
    def kg_per_m2(self) -> float | None:
        """Area mass from grammage, or from density × thickness."""
        if self.grammage_g_m2 is not None:
            return self.grammage_g_m2 / 1_000
        if self.density_kg_m3 is not None and self.thickness_um is not None:
            return self.density_kg_m3 * self.thickness_um / 1_000_000
        return None


class ValidationRules(BaseModel):
    bom_valid_from_max_age_years: int = Field(gt=0)
    supplier_pcf_max_age_years: int = Field(gt=0)
    scrap_destinations: list[str]


class ProductConfig(BaseModel):
    """A product definition loaded from YAML."""

    product_id: str
    name: str
    finished_material: str
    part_mass_g: float = Field(gt=0)
    reference_year: int
    input_dir: str
    materials: dict[str, MaterialProperties]
    validation: ValidationRules

    @property
    def reference_date(self) -> date:
        """Last day of the reference year; age checks use it so results are reproducible."""
        return date(self.reference_year, 12, 31)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ProductConfig":
        return cls.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


class BomLine(BaseModel):
    """A cleaned BOM component, with quantities normalised to kg."""

    material_number: str
    description: str
    parent_material: str
    bom_level: int
    component_qty: float
    uom: str
    base_qty: float
    base_uom: str
    item_category: str
    plant: str
    valid_from: date | None
    supplier_id: str | None
    qty_kg: float
    qty_kg_per_kg_product: float
    source_row: int


class RoutingStep(BaseModel):
    step_id: str
    step_name: str
    machine: str
    throughput_kg_per_h: float = Field(gt=0)
    power_kw: float = Field(ge=0)
    utilisation: float = Field(ge=0, le=1)
    scrap_rate: float = Field(ge=0, lt=1)
    scrap_destination: str

    @property
    def kwh_per_kg(self) -> float:
        return self.power_kw * self.utilisation / self.throughput_kg_per_h


class Supplier(BaseModel):
    supplier_id: str
    name: str
    country: str
    contact_role: str
    materials_supplied: list[str]


class SupplierPcf(BaseModel):
    """A supplier's PCF submission. `fallback_reason` is set when it cannot be used."""

    supplier_id: str
    material_number: str
    pcf_value: float | None = None
    declared_unit: str | None = None
    reference_period_start: date | None = None
    reference_period_end: date | None = None
    method: str | None = None
    primary_data_share: float | None = None
    dqr: float | None = None
    boundary: str | None = None
    notes: str | None = None
    status: str | None = None
    fallback_reason: str | None = None

    @property
    def usable(self) -> bool:
        return self.fallback_reason is None


class TransportLeg(BaseModel):
    leg_id: str
    material_number: str
    supplier_id: str | None
    origin: str
    destination: str
    mode: str
    distance_km: float = Field(gt=0)
