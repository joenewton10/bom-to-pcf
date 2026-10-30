"""Export a result as a PACT ProductFootprint, validated against the pinned official schema."""

import uuid
from datetime import UTC, datetime
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from bom_to_pcf.models import EmissionFactor, MethodConfig, PcfResult, ProductConfig

SPEC_VERSION = "3.0.3"
SCHEMA_FILE = f"schemas/pact/openapi-{SPEC_VERSION}.yaml"
DECIMALS = 6
UNIT = "kilogram"
PERCENT = 100
# PACT Methodology 3.0, Table 3: a PCF is valid for up to three years.
VALIDITY_YEARS = 3
# The schema asks for every assessment report used. See docs/data_gaps.md on the mixed basis.
CHARACTERIZATION_FACTORS = ["AR6", "AR5", "AR4"]
STANDARDS = ["ISO14067", "PACT-3.0"]
TFS_RULE = {
    "operator": "Other",
    "ruleNames": ["The Product Carbon Footprint Guideline for the Chemical Industry, v.3"],
}
TFS_OPERATOR = "TfS"
PACKAGING_STAGE = "packaging"


def _decimal(value: float) -> str:
    return f"{value:.{DECIMALS}f}"


def _timestamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def load_validator(root: Path | str = ".") -> Draft202012Validator:
    """Build a validator for ProductFootprint from the official OpenAPI document."""
    document = yaml.safe_load((Path(root) / SCHEMA_FILE).read_text(encoding="utf-8"))
    schema = {
        "$ref": "#/components/schemas/ProductFootprint",
        "components": document["components"],
    }
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validation_errors(footprint: dict, root: Path | str = ".") -> list[str]:
    """Plain descriptions of everything in a footprint that breaks the official schema."""
    errors = load_validator(root).iter_errors(footprint)
    return [f"{'/'.join(str(p) for p in e.absolute_path)}: {e.message}" for e in errors]


def _fossil_carbon(result: PcfResult, config: ProductConfig) -> float:
    """Fossil carbon in 1 kg of product, for materials with a known carbon fraction.

    A material's share of the finished part is taken as its share of product material inputs.
    """
    inputs = result.mass_balance.inputs_kg
    if not inputs:
        return 0.0
    # A material with several factors has several lines, so take each material once.
    masses = {line.item: line.mass_kg for line in result.lines if line.stage == "materials"}
    total = 0.0
    for material, mass in masses.items():
        properties = config.materials.get(material)
        if properties and properties.fossil_carbon_fraction and mass:
            total += mass / inputs * properties.fossil_carbon_fraction
    return total


def _comment(result: PcfResult) -> str:
    parts = [
        "ILLUSTRATIVE DATA, not a verified PCF. Do not use for real claims.",
        f"Tool status: {result.status_label}.",
        "Biogenic carbon is not separately modelled, so both PCF values are equal.",
        "Fossil carbon content covers PET film only.",
        "Sources do not share one GWP basis.",
    ]
    if result.known_omissions:
        parts.append("Not modelled: " + "; ".join(result.known_omissions) + ".")
    return " ".join(parts)


def _emission_sources(
    result: PcfResult, factors: dict[str, EmissionFactor]
) -> list[dict[str, str]]:
    sources: dict[str, str] = {}
    for line in result.lines:
        factor = factors.get(line.factor_id or "")
        if factor and factor.data_type == "secondary":
            sources.setdefault(factor.source_id, str(factor.reference_year))
    return [{"name": name, "version": version} for name, version in sorted(sources.items())]


def build_footprint(
    result: PcfResult,
    config: ProductConfig,
    method: MethodConfig,
    factors: dict[str, EmissionFactor],
    created: datetime | None = None,
) -> dict:
    """Build a ProductFootprint for 1 kg of product. Its id repeats for the same result."""
    info = config.pact
    if info is None:
        raise ValueError("the product config has no PACT details")
    created = created or datetime.now(UTC)
    year = config.reference_year
    value = _decimal(result.kg_co2e_per_kg)
    identity = f"{config.product_id}|{year}|{value}|{result.status_label}"
    pcf: dict = {
        "declaredUnitOfMeasurement": UNIT,
        "declaredUnitAmount": "1",
        "productMassPerDeclaredUnit": "1",
        "referencePeriodStart": _timestamp(datetime(year, 1, 1, tzinfo=UTC)),
        "referencePeriodEnd": _timestamp(datetime(year + 1, 1, 1, tzinfo=UTC)),
        "geographyCountry": info.geography_country,
        "boundaryProcessesDescription": info.boundary_description,
        "pcfExcludingBiogenicUptake": value,
        "pcfIncludingBiogenicUptake": value,
        "fossilCarbonContent": _decimal(_fossil_carbon(result, config)),
        "fossilGhgEmissions": value,
        "packagingEmissionsIncluded": True,
        "packagingGhgEmissions": _decimal(result.by_stage.get(PACKAGING_STAGE, 0.0)),
        "ipccCharacterizationFactors": CHARACTERIZATION_FACTORS,
        "crossSectoralStandards": STANDARDS,
        "productOrSectorSpecificRules": [TFS_RULE],
        "otherOperatorName": TFS_OPERATOR,
        "exemptedEmissionsPercent": _decimal(result.excluded_share * PERCENT),
        "allocationRulesDescription": info.allocation_description,
        "secondaryEmissionFactorSources": _emission_sources(result, factors),
        "primaryDataShare": _decimal(result.primary_data_share * PERCENT),
    }
    if result.dqr.overall is not None:
        pcf["dqi"] = {
            "technologicalDQR": _decimal(result.dqr.technological),
            "geographicalDQR": _decimal(result.dqr.geographical),
            "temporalDQR": _decimal(result.dqr.temporal),
        }
    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, identity)),
        "specVersion": SPEC_VERSION,
        "created": _timestamp(created),
        "status": "Active",
        "validityPeriodStart": _timestamp(datetime(year + 1, 1, 1, tzinfo=UTC)),
        "validityPeriodEnd": _timestamp(datetime(year + 1 + VALIDITY_YEARS, 1, 1, tzinfo=UTC)),
        "companyName": info.company_name,
        "companyIds": [info.company_id],
        "productDescription": config.name,
        "productIds": [info.product_id],
        "productNameCompany": config.name,
        "comment": _comment(result),
        "pcf": pcf,
    }
