"""Read supplier master data, supplier PCF submissions and inbound transport legs."""

import json
from pathlib import Path

from pydantic import ValidationError

from bom_to_pcf.io.parsing import decode, missing_columns, parse_decimal, read_bytes, read_rows
from bom_to_pcf.models import Issue, ProductConfig, Severity, Supplier, SupplierPcf, TransportLeg

SUPPLIER_COLUMNS = ["supplier_id", "name", "country", "contact_role", "materials_supplied"]
TRANSPORT_COLUMNS = [
    "leg_id",
    "material_number",
    "supplier_id",
    "origin",
    "destination",
    "mode",
    "distance_km",
]
PCF_REQUIRED_FIELDS = ["pcf_value", "declared_unit", "reference_period_end", "method", "boundary"]
LIST_SEPARATOR = "|"
NUMERIC_SUBMISSION_FIELDS = ["pcf_value", "primary_data_share", "dqr"]


def read_suppliers(source: Path | str | bytes) -> tuple[list[Supplier], list[Issue]]:
    """Read the supplier master data."""
    rows = read_rows(source)
    missing = missing_columns(rows, SUPPLIER_COLUMNS)
    if missing:
        return [], [_missing_columns_issue("suppliers", missing)]
    suppliers = [
        Supplier(
            supplier_id=row["supplier_id"],
            name=row["name"],
            country=row["country"],
            contact_role=row["contact_role"],
            materials_supplied=[m for m in row["materials_supplied"].split(LIST_SEPARATOR) if m],
        )
        for _, row in rows
    ]
    return suppliers, []


def read_supplier_pcfs(
    source: Path | str | bytes, config: ProductConfig
) -> tuple[list[SupplierPcf], list[Issue]]:
    """Read supplier PCFs. Records that cannot be used fall back to secondary data, logged."""
    try:
        records = json.loads(decode(read_bytes(source)))["records"]
    except (ValueError, KeyError, TypeError) as error:
        return [], [
            Issue(
                severity=Severity.ERROR,
                code="invalid_file",
                source="supplier_pcf",
                message=f"The supplier PCF file could not be read: {error}.",
            )
        ]

    pcfs: list[SupplierPcf] = []
    issues: list[Issue] = []
    for position, record in enumerate(records, start=1):
        try:
            pcf = SupplierPcf.model_validate(record)
        except ValidationError as error:
            first = error.errors()[0]
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    code="invalid_record",
                    source="supplier_pcf",
                    message=f"Record {position} dropped: {first['loc'][0]}: {first['msg']}.",
                    row=position,
                )
            )
            continue
        reason, code = _fallback_reason(pcf, config)
        if reason:
            pcf.fallback_reason = reason
            issues.append(
                Issue(
                    severity=Severity.WARNING,
                    code=code,
                    source="supplier_pcf",
                    message=f"{pcf.supplier_id}: {reason}; secondary data stays in use.",
                    row=position,
                    material=pcf.material_number,
                )
            )
        pcfs.append(pcf)
    return pcfs, issues


def _fallback_reason(pcf: SupplierPcf, config: ProductConfig) -> tuple[str | None, str]:
    max_age = config.validation.supplier_pcf_max_age_years
    period_end = pcf.reference_period_end
    if period_end and (config.reference_date - period_end).days > max_age * 365.25:
        return (
            f"the reference period ended {period_end}, "
            f"more than {max_age} years before the reference date",
            "supplier_pcf_expired",
        )
    if pcf.status == "PLACEHOLDER":
        return "the PCF value is a placeholder", "supplier_pcf_placeholder"
    absent = [name for name in PCF_REQUIRED_FIELDS if getattr(pcf, name) is None]
    if absent:
        return f"the record is incomplete (missing {', '.join(absent)})", "supplier_pcf_incomplete"
    return None, ""


def read_submission_file(raw: bytes, filename: str) -> list[SupplierPcf]:
    """Read supplier PCFs from an uploaded JSON or CSV file. Raises ValueError if unreadable."""
    try:
        if filename.lower().endswith(".json"):
            payload = json.loads(decode(raw))
            records = payload["records"] if isinstance(payload, dict) else payload
        else:
            records = []
            for _, row in read_rows(raw):
                record = {key: value or None for key, value in row.items()}
                for name in NUMERIC_SUBMISSION_FIELDS:
                    if record.get(name):
                        record[name] = parse_decimal(record[name])[0]
                records.append(record)
        return [SupplierPcf.model_validate(record) for record in records]
    except (ValueError, KeyError, TypeError, ValidationError) as error:
        raise ValueError(f"{filename} could not be read as supplier PCFs") from error


def read_transport(source: Path | str | bytes) -> tuple[list[TransportLeg], list[Issue]]:
    """Read inbound transport legs."""
    rows = read_rows(source)
    missing = missing_columns(rows, TRANSPORT_COLUMNS)
    if missing:
        return [], [_missing_columns_issue("transport", missing)]
    legs: list[TransportLeg] = []
    issues: list[Issue] = []
    for row_number, row in rows:
        try:
            legs.append(
                TransportLeg(
                    leg_id=row["leg_id"],
                    material_number=row["material_number"],
                    supplier_id=row["supplier_id"] or None,
                    origin=row["origin"],
                    destination=row["destination"],
                    mode=row["mode"].lower(),
                    distance_km=parse_decimal(row["distance_km"])[0],
                )
            )
        except (ValueError, ValidationError) as error:
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    code="invalid_row",
                    source="transport",
                    message=f"Leg {row['leg_id'] or '(no id)'} dropped: invalid distance "
                    f"'{row['distance_km']}' ({type(error).__name__}).",
                    row=row_number,
                    material=row["material_number"] or None,
                )
            )
    return legs, issues


def _missing_columns_issue(source: str, missing: list[str]) -> Issue:
    return Issue(
        severity=Severity.ERROR,
        code="missing_columns",
        source=source,
        message=f"The {source} file is empty or lacks columns: {', '.join(missing)}.",
    )
