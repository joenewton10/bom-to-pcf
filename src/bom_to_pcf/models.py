"""Data models shared by the readers, the engine and the app."""

from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Literal

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
    role: Literal["product", "packaging"] = "product"

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
    method_file: str = "config/method.yaml"
    factors_file: str = "data/factors/emission_factors.csv"
    sources_file: str = "data/factors/SOURCES.md"
    mappings_file: str = "data/mappings/bom_to_dataset.csv"
    candidates_file: str = "data/mappings/candidates.yaml"
    matching_file: str = "config/matching.yaml"
    materials: dict[str, MaterialProperties]
    validation: ValidationRules

    def role_of(self, material: str) -> str:
        """A material's role. Unlisted materials count as product material."""
        properties = self.materials.get(material)
        return properties.role if properties else "product"

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


class EmissionFactor(BaseModel):
    """One row of the factor table. DQR scores run from 1 (best) to 5 (worst)."""

    factor_id: str = Field(min_length=1)
    name: str
    value: float | None = Field(default=None, ge=0)
    unit: str
    gwp_basis: str = ""
    geography: str = ""
    reference_year: int | None = None
    source_id: str = ""
    data_type: Literal["secondary", "primary"]
    dqr_tech: float | None = Field(default=None, ge=1, le=5)
    dqr_geo: float | None = Field(default=None, ge=1, le=5)
    dqr_time: float | None = Field(default=None, ge=1, le=5)
    notes: str = ""
    status: str

    @property
    def is_placeholder(self) -> bool:
        return self.status == "PLACEHOLDER"


class TransportLeg(BaseModel):
    leg_id: str
    material_number: str
    supplier_id: str | None
    origin: str
    destination: str
    mode: str
    distance_km: float = Field(gt=0)


class Mapping(BaseModel):
    """Links a BOM material to one emission factor. A material may need several."""

    material_number: str
    factor_id: str
    review_status: Literal["unreviewed", "approved", "rejected"]


class Candidate(BaseModel):
    """Something a BOM material can be matched to, with the factors it stands for."""

    id: str
    label: str
    terms: list[str]
    factor_ids: list[str]


class MatchingConfig(BaseModel):
    top_n: int = Field(gt=0)
    llm_default_on: bool
    llm_model: str
    llm_effort: str
    llm_max_tokens: int = Field(gt=0)
    llm_session_call_limit: int = Field(ge=0)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "MatchingConfig":
        return cls.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


class Suggestion(BaseModel):
    """A proposed match. Confidence runs from 0 to 1; rationale comes from the LLM only."""

    candidate_id: str
    label: str
    source: Literal["fuzzy", "llm"]
    confidence: float = Field(ge=0, le=1)
    rationale: str = ""


class ReviewItem(BaseModel):
    """One BOM material under review. The first suggestion is the one being proposed."""

    material_number: str
    description: str
    uom: str
    suggestions: list[Suggestion]
    decision: Literal["pending", "approve", "reject", "choose_other"] = "pending"
    chosen_id: str | None = None
    comment: str = ""


class ReviewLogEntry(BaseModel):
    """One reviewer decision. The log is only ever added to."""

    timestamp: str
    bom_item: str
    suggestion: str
    source: str
    confidence: float | None
    decision: str
    chosen: str
    reviewer: str
    comment: str


class SubstitutionFactors(BaseModel):
    burden_factor: str
    avoided_factor: str


class AllocationRules(BaseModel):
    scrap_recycling: Literal["cut_off", "substitution"]
    substitution: SubstitutionFactors
    overhead_method: Literal["mass", "machine_hours"]
    overhead_step_id: str
    overhead_machine_count: int = Field(gt=0)


class CutOffRules(BaseModel):
    flow_share: float = Field(ge=0, lt=1)
    total_share: float = Field(ge=0, lt=1)


class MassBalanceRules(BaseModel):
    tolerance_share: float = Field(ge=0, lt=1)


class FactorChoices(BaseModel):
    electricity: list[str]
    transport: dict[str, list[str]]
    scrap: dict[str, list[str]]


class PrimaryShareRules(BaseModel):
    site_stages: list[str]


class MethodConfig(BaseModel):
    """Method choices loaded from YAML."""

    gwp_set: str
    mass_balance: MassBalanceRules
    allocation: AllocationRules
    cut_off: CutOffRules
    factors: FactorChoices
    primary_share: PrimaryShareRules
    known_omissions: list[str] = []

    @classmethod
    def from_yaml(cls, path: str | Path) -> "MethodConfig":
        return cls.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


class LciLine(BaseModel):
    """One inventory quantity per kg of finished product, linked to one factor."""

    stage: str
    item: str
    description: str
    quantity: float
    unit: str
    factor_id: str | None = None
    mass_kg: float | None = None
    note: str = ""


class ResultLine(LciLine):
    """An inventory line with its impact. `impact` is None while the factor has no value."""

    impact: float | None
    source_id: str = ""


class StepMass(BaseModel):
    """Mass entering a process step, per kg of finished product."""

    step_id: str
    input_kg: float
    scrap_kg: float
    scrap_destination: str


class MassBalance(BaseModel):
    """Product material inputs against finished product plus scrap, per kg of product."""

    inputs_kg: float
    product_kg: float
    scrap_kg: float
    imbalance_kg: float
    imbalance_share: float
    tolerance_share: float
    passed: bool
    steps: list[StepMass]


class DqrScore(BaseModel):
    """Impact-weighted data quality, from 1 (best) to 5 (worst). None when no line has a score."""

    technological: float | None
    geographical: float | None
    temporal: float | None
    overall: float | None


class PcfResult(BaseModel):
    """A calculated footprint, with everything needed to judge how far to trust it."""

    kg_co2e_per_kg: float
    kg_co2e_per_1000_pieces: float
    gwp_set: str
    by_stage: dict[str, float]
    by_material: dict[str, float]
    lines: list[ResultLine]
    excluded: list[ResultLine]
    excluded_share: float
    is_draft: bool
    is_partial: bool
    status_label: str
    draft_reasons: list[str]
    missing: list[str]
    known_omissions: list[str]
    primary_data_share: float
    dqr: DqrScore
    mass_balance: MassBalance
