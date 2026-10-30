"""Read and clean a SAP-style BOM export and the production routing."""

from pathlib import Path

from pydantic import ValidationError

from bom_to_pcf.io.parsing import missing_columns, parse_date, parse_decimal, read_rows
from bom_to_pcf.models import BomLine, Issue, ProductConfig, RoutingStep, Severity

BOM_COLUMNS = [
    "material_number",
    "material_description",
    "parent_material",
    "bom_level",
    "component_qty",
    "uom",
    "base_qty",
    "base_uom",
    "item_category",
    "plant",
    "valid_from",
    "supplier_id",
]
ROUTING_COLUMNS = [
    "step_id",
    "step_name",
    "machine",
    "throughput_kg_per_h",
    "power_kw",
    "utilisation",
    "scrap_rate",
    "scrap_destination",
]
MASS_UNITS_TO_KG = {"KG": 1.0, "G": 0.001}
UNIT_ALIASES = {"M²": "M2"}


def normalise_unit(uom: str) -> str:
    unit = uom.strip().upper()
    return UNIT_ALIASES.get(unit, unit)


def to_kg(qty: float, uom: str, material: str, config: ProductConfig) -> float:
    """Convert a quantity to kg, or raise ValueError saying which data is missing."""
    if uom in MASS_UNITS_TO_KG:
        return qty * MASS_UNITS_TO_KG[uom]
    properties = config.materials.get(material)
    if uom == "M2":
        kg_per_m2 = properties.kg_per_m2 if properties else None
        if kg_per_m2 is None:
            raise ValueError("unit is M2 but the product config has no grammage or density")
        return qty * kg_per_m2
    if uom == "ST":
        if material == config.finished_material:
            return qty * config.part_mass_g / 1_000
        if properties is None or properties.kg_per_piece is None:
            raise ValueError("unit is ST but the product config has no mass per piece")
        return qty * properties.kg_per_piece
    raise ValueError(f"unit '{uom}' is not recognised")


def read_bom(
    source: Path | str | bytes, config: ProductConfig
) -> tuple[list[BomLine], list[Issue]]:
    """Clean a BOM export. Unusable rows are dropped; every change or doubt becomes an Issue."""
    rows = read_rows(source)
    issues: list[Issue] = []

    def add(severity: Severity, code: str, message: str, row: int, material: str | None) -> None:
        issues.append(
            Issue(
                severity=severity,
                code=code,
                source="bom",
                message=message,
                row=row,
                material=material,
            )
        )

    missing = missing_columns(rows, BOM_COLUMNS)
    if missing:
        issues.append(
            Issue(
                severity=Severity.ERROR,
                code="missing_columns",
                source="bom",
                message=f"The BOM file is empty or lacks columns: {', '.join(missing)}.",
            )
        )
        return [], issues

    lines: dict[tuple[str, str], BomLine] = {}
    for row_number, row in rows:
        material = row["material_number"]
        if not material:
            add(Severity.ERROR, "missing_material", "Row has no material number; dropped.",
                row_number, None)  # fmt: skip
            continue

        try:
            qty, qty_german = parse_decimal(row["component_qty"])
            base_qty, base_german = parse_decimal(row["base_qty"])
            uom = normalise_unit(row["uom"])
            base_uom = normalise_unit(row["base_uom"])
            bom_level = int(row["bom_level"])
            if qty <= 0 or base_qty <= 0:
                raise ValueError("quantities must be greater than zero")
            qty_kg = to_kg(qty, uom, material, config)
            base_kg = to_kg(base_qty, base_uom, config.finished_material, config)
        except ValueError as error:
            add(Severity.ERROR, "invalid_row", f"Row dropped: {error}.", row_number, material)
            continue

        if qty_german or base_german:
            add(Severity.INFO, "decimal_comma_normalised",
                f"German decimal notation read as {qty:g}.", row_number, material)  # fmt: skip
        if uom != "KG":
            add(Severity.INFO, "unit_converted",
                f"{qty:g} {uom} converted to {qty_kg:g} kg.", row_number, material)  # fmt: skip

        valid_from = None
        try:
            valid_from = parse_date(row["valid_from"])
        except ValueError:
            add(Severity.WARNING, "invalid_valid_from",
                f"Could not read valid_from '{row['valid_from']}'.",
                row_number, material)  # fmt: skip
        if valid_from is not None:
            age_limit = config.validation.bom_valid_from_max_age_years
            if valid_from > config.reference_date:
                add(Severity.WARNING, "future_valid_from",
                    f"valid_from {valid_from} is after the reference year.",
                    row_number, material)  # fmt: skip
            elif (config.reference_date - valid_from).days > age_limit * 365.25:
                add(Severity.WARNING, "obsolete_valid_from",
                    f"valid_from {valid_from} is more than {age_limit} years old; "
                    "check this BOM item is still current.", row_number, material)  # fmt: skip

        supplier_id = row["supplier_id"] or None
        if supplier_id is None:
            add(Severity.WARNING, "missing_supplier",
                "No supplier given; primary data cannot be requested for this material.",
                row_number, material)  # fmt: skip

        line = BomLine(
            material_number=material,
            description=row["material_description"],
            parent_material=row["parent_material"],
            bom_level=bom_level,
            component_qty=qty,
            uom=uom,
            base_qty=base_qty,
            base_uom=base_uom,
            item_category=row["item_category"],
            plant=row["plant"],
            valid_from=valid_from,
            supplier_id=supplier_id,
            qty_kg=qty_kg,
            qty_kg_per_kg_product=qty_kg / base_kg,
            source_row=row_number,
        )
        key = (line.parent_material, material)
        first = lines.get(key)
        if first is None:
            lines[key] = line
        elif first.qty_kg == line.qty_kg:
            add(Severity.WARNING, "duplicate_line",
                f"Same material and quantity as row {first.source_row}; duplicate dropped.",
                row_number, material)  # fmt: skip
        else:
            add(Severity.ERROR, "conflicting_duplicate",
                f"Same material as row {first.source_row} with a different quantity "
                f"({line.qty_kg:g} vs {first.qty_kg:g} kg). Kept row {first.source_row}; "
                "please correct the export.", row_number, material)  # fmt: skip

    return list(lines.values()), issues


def read_routing(
    source: Path | str | bytes, config: ProductConfig
) -> tuple[list[RoutingStep], list[Issue]]:
    """Read routing and energy data, dropping steps with values outside physical limits."""
    rows = read_rows(source)
    issues: list[Issue] = []
    missing = missing_columns(rows, ROUTING_COLUMNS)
    if missing:
        issues.append(
            Issue(
                severity=Severity.ERROR,
                code="missing_columns",
                source="routing",
                message=f"The routing file is empty or lacks columns: {', '.join(missing)}.",
            )
        )
        return [], issues

    steps: list[RoutingStep] = []
    for row_number, row in rows:
        try:
            step = RoutingStep(
                step_id=row["step_id"],
                step_name=row["step_name"],
                machine=row["machine"],
                throughput_kg_per_h=parse_decimal(row["throughput_kg_per_h"])[0],
                power_kw=parse_decimal(row["power_kw"])[0],
                utilisation=parse_decimal(row["utilisation"])[0],
                scrap_rate=parse_decimal(row["scrap_rate"])[0],
                scrap_destination=row["scrap_destination"].lower(),
            )
        except (ValueError, ValidationError) as error:
            reason = _first_error(error)
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    code="invalid_row",
                    source="routing",
                    message=f"Step {row['step_id'] or '(no id)'} dropped: {reason}.",
                    row=row_number,
                )
            )
            continue
        if step.scrap_destination not in config.validation.scrap_destinations:
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    code="unknown_scrap_destination",
                    source="routing",
                    message=f"Step {step.step_id} sends scrap to unknown destination "
                    f"'{step.scrap_destination}'.",
                    row=row_number,
                )
            )
        steps.append(step)
    return steps, issues


def _first_error(error: ValueError | ValidationError) -> str:
    if isinstance(error, ValidationError):
        first = error.errors()[0]
        return f"{first['loc'][0]}: {first['msg']}"
    return str(error)
