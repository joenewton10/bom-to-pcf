"""Supplier data requests and the status tracker. The app creates files; it never sends email."""

import csv
import io
import json
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from bom_to_pcf.models import (
    BomLine,
    ProductConfig,
    ProjectState,
    RequestRules,
    RequestStatus,
    StatusChange,
    Supplier,
    SupplierPcf,
)

TEMPLATE_NAME = "supplier_request.md.j2"
NOT_REQUESTED = "not requested"
REQUESTED = "requested"
RECEIVED = "received"
VALIDATED = "validated"
REJECTED = "rejected"
TEMPLATE_FIELDS = [
    "supplier_id",
    "material_number",
    "material_description",
    "pcf_value",
    "declared_unit",
    "reference_period_start",
    "reference_period_end",
    "method",
    "primary_data_share",
    "dqr",
    "boundary",
    "notes",
]


def _period(config: ProductConfig) -> tuple[str, str]:
    return f"{config.reference_year}-01-01", f"{config.reference_year}-12-31"


def request_records(
    supplier_id: str, bom: list[BomLine], config: ProductConfig, rules: RequestRules
) -> list[dict]:
    """Pre-filled records. Once filled in, the file loads on the Primary data page."""
    start, end = _period(config)
    return [
        {
            "supplier_id": supplier_id,
            "material_number": line.material_number,
            "material_description": line.description,
            "pcf_value": None,
            "declared_unit": rules.declared_unit,
            "reference_period_start": start,
            "reference_period_end": end,
            "method": None,
            "primary_data_share": None,
            "dqr": None,
            "boundary": rules.boundary,
            "notes": None,
        }
        for line in bom
        if line.supplier_id == supplier_id
    ]


def records_json(records: list[dict]) -> str:
    return json.dumps({"records": records}, indent=2, ensure_ascii=False)


def records_csv(records: list[dict]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=TEMPLATE_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(records)
    return buffer.getvalue()


def cover_message(
    supplier: Supplier,
    records: list[dict],
    config: ProductConfig,
    rules: RequestRules,
    templates_dir: Path | str,
) -> str:
    """The cover message. It names only this supplier's own materials."""
    environment = Environment(
        loader=FileSystemLoader(templates_dir),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    start, end = _period(config)
    return environment.get_template(TEMPLATE_NAME).render(
        supplier=supplier,
        records=records,
        rules=rules,
        period_start=start,
        period_end=end,
        max_age=config.validation.supplier_pcf_max_age_years,
    )


def request_files(
    supplier: Supplier,
    bom: list[BomLine],
    config: ProductConfig,
    rules: RequestRules,
    templates_dir: Path | str,
) -> dict[str, str]:
    """All the files in one supplier's request, by file name."""
    records = request_records(supplier.supplier_id, bom, config, rules)
    stem = f"pcf_request_{supplier.supplier_id}"
    return {
        f"{stem}.md": cover_message(supplier, records, config, rules, templates_dir),
        f"{stem}.json": records_json(records),
        f"{stem}.csv": records_csv(records),
    }


def zip_requests(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _set_status(
    state: ProjectState, material: str, supplier: str, status: str, on: date, note: str = ""
) -> None:
    entry = state.requests.get(material)
    if entry is None:
        entry = RequestStatus(material_number=material, supplier_id=supplier)
        state.requests[material] = entry
    entry.status = status
    entry.history.append(StatusChange(status=status, on=on, note=note))


def mark_requested(state: ProjectState, supplier_id: str, bom: list[BomLine], on: date) -> None:
    """Mark a supplier's materials as requested, unless data has already arrived for them."""
    for line in bom:
        if line.supplier_id != supplier_id:
            continue
        current = state.requests.get(line.material_number)
        if current is None or current.status == NOT_REQUESTED:
            _set_status(state, line.material_number, supplier_id, REQUESTED, on)


def on_submission(
    state: ProjectState, pcf: SupplierPcf, accepted: bool, bom: list[BomLine], on: date
) -> None:
    """Move the status on submission. Data from another supplier does not count."""
    line = next((b for b in bom if b.material_number == pcf.material_number), None)
    if line is None or (line.supplier_id and line.supplier_id != pcf.supplier_id):
        return
    material = pcf.material_number
    _set_status(state, material, pcf.supplier_id, RECEIVED, on)
    if accepted:
        _set_status(state, material, pcf.supplier_id, VALIDATED, on)
    elif material in state.active:
        _set_status(
            state, material, pcf.supplier_id, VALIDATED, on,
            "Latest submission was rejected; the earlier version stays in use.",
        )  # fmt: skip
    else:
        _set_status(state, material, pcf.supplier_id, REJECTED, on)


def on_revert(state: ProjectState, material: str, on: date) -> None:
    """After an undo, say honestly whether validated data is still in use for the material."""
    entry = state.requests.get(material)
    if entry is None:
        return
    if material in state.active:
        _set_status(state, material, entry.supplier_id, VALIDATED, on, "An earlier version in use.")
    else:
        _set_status(
            state, material, entry.supplier_id, RECEIVED, on,
            "Undone, so the database value is in use again.",
        )  # fmt: skip


def set_note(state: ProjectState, material: str, supplier_id: str, note: str) -> None:
    entry = state.requests.get(material)
    if entry is None:
        entry = RequestStatus(material_number=material, supplier_id=supplier_id)
        state.requests[material] = entry
    entry.note = note


def tracker_table(
    state: ProjectState, bom: list[BomLine], suppliers: list[Supplier]
) -> pd.DataFrame:
    """One row per BOM material, including those with no request yet."""
    names = {supplier.supplier_id: supplier.name for supplier in suppliers}
    rows = []
    for line in bom:
        entry = state.requests.get(line.material_number)
        history = entry.history if entry else []
        requested = next((c.on for c in history if c.status == REQUESTED), None)
        rows.append(
            {
                "Material": line.material_number,
                "Description": line.description,
                "Supplier": names.get(line.supplier_id, line.supplier_id or "Not known"),
                "Status": entry.status if entry else NOT_REQUESTED,
                "Requested on": requested,
                "Last change": history[-1].on if history else None,
                "Latest update": history[-1].note if history else "",
                "Notes": entry.note if entry else "",
            }
        )
    return pd.DataFrame(rows)
