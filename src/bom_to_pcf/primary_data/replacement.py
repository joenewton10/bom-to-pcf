"""Swap database values for supplier data, traceably and reversibly.

History is only added to. Undoing a change moves the pointer to an earlier version, so a revert
restores the earlier inputs exactly.
"""

from datetime import UTC, datetime

import pandas as pd

from bom_to_pcf.io.inputs import InputBundle
from bom_to_pcf.models import (
    AuditEntry,
    PcfResult,
    PrimaryVersion,
    ProjectState,
    RejectedSubmission,
    SupplierPcf,
)
from bom_to_pcf.primary_data.validation import SubmissionCheck

SECONDARY = "secondary"
AUDITED_FIELDS = [
    "pcf_value",
    "declared_unit",
    "reference_period_start",
    "reference_period_end",
    "method",
    "primary_data_share",
    "dqr",
    "boundary",
]
AUDIT_COLUMNS = list(AuditEntry.model_fields)
FILE_IMPORT_USER = "file import"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _version(state: ProjectState, version_id: str | None) -> PrimaryVersion | None:
    return next((v for v in state.versions if v.version_id == version_id), None)


def _text(value: object) -> str:
    return "" if value is None else str(value)


def record_submission(
    state: ProjectState,
    pcf: SupplierPcf,
    check: SubmissionCheck,
    user: str,
    comment: str = "",
) -> PrimaryVersion | None:
    """Store a checked submission. If rejected, the value in use stays and the reasons are kept."""
    if not user.strip():
        raise ValueError("a name is needed for the audit trail")
    timestamp = _now()
    material, supplier = pcf.material_number, pcf.supplier_id
    if not check.accepted:
        reason = " ".join(check.reasons)
        state.rejections.append(
            RejectedSubmission(
                timestamp=timestamp, user=user, submission=pcf, reasons=check.reasons
            )
        )
        state.audit.append(
            AuditEntry(
                timestamp=timestamp,
                user=user,
                material=material,
                supplier=supplier,
                field="submission",
                old_value=_text(state.active.get(material, SECONDARY)),
                new_value=f"rejected: {_text(pcf.pcf_value)} per {_text(pcf.declared_unit)}",
                reason=reason,
                version_id="",
            )
        )
        return None

    version = PrimaryVersion(
        version_id=f"V{len(state.versions) + 1:04d}",
        created_at=timestamp,
        user=user,
        submission=pcf,
        value_per_kg=check.value_per_kg,
        comment=comment,
    )
    previous = _version(state, state.active.get(material))
    reason = comment or "Supplier data passed validation."
    for field in AUDITED_FIELDS:
        old = getattr(previous.submission, field) if previous else None
        new = getattr(pcf, field)
        if field == "pcf_value" and previous is None:
            old = f"{SECONDARY}: {_text(check.secondary_per_kg)} per kg"
        if _text(old) != _text(new):
            state.audit.append(
                AuditEntry(
                    timestamp=timestamp,
                    user=user,
                    material=material,
                    supplier=supplier,
                    field=field,
                    old_value=_text(old),
                    new_value=_text(new),
                    reason=reason,
                    version_id=version.version_id,
                )
            )
    state.versions.append(version)
    state.active[material] = version.version_id
    return version


def revert(
    state: ProjectState, material: str, target_version: str | None, user: str, reason: str
) -> None:
    """Go back to an earlier version of a material, or to the database value with None."""
    if not user.strip():
        raise ValueError("a name is needed for the audit trail")
    if not reason.strip():
        raise ValueError("a reason is needed to undo a change")
    target = _version(state, target_version)
    if target_version is not None and (
        target is None or target.submission.material_number != material
    ):
        raise ValueError(f"version {target_version} does not belong to material {material}")
    current = state.active.get(material)
    if current == target_version:
        raise ValueError("that version is already in use")
    if target_version is None:
        del state.active[material]
    else:
        state.active[material] = target_version
    supplier = (_version(state, current) or target).submission.supplier_id if current else ""
    state.audit.append(
        AuditEntry(
            timestamp=_now(),
            user=user,
            material=material,
            supplier=supplier,
            field="active_version",
            old_value=_text(current or SECONDARY),
            new_value=_text(target_version or SECONDARY),
            reason=reason,
            version_id=_text(target_version),
        )
    )


def apply_primary(bundle: InputBundle, state: ProjectState) -> InputBundle:
    """The inputs with active versions as the only supplier data the engine will use."""
    pcfs = []
    for version_id in state.active.values():
        version = _version(state, version_id)
        pcfs.append(
            version.submission.model_copy(
                update={
                    "pcf_value": version.value_per_kg,
                    "declared_unit": "kg",
                    "fallback_reason": None,
                    "version_id": version.version_id,
                }
            )
        )
    return bundle.model_copy(update={"supplier_pcfs": pcfs})


def already_seen(state: ProjectState, pcf: SupplierPcf) -> bool:
    """Whether this exact submission was already handled, so re-reading a file adds nothing."""
    return any(v.submission == pcf for v in state.versions) or any(
        r.submission == pcf for r in state.rejections
    )


def compare_results(before: PcfResult, after: PcfResult) -> pd.DataFrame:
    """Old and new headline figures, with the change in each."""

    def row(metric: str, old: float | None, new: float | None) -> dict:
        delta = None if old is None or new is None else new - old
        return {"Measure": metric, "Before": old, "After": new, "Change": delta}

    return pd.DataFrame(
        [
            row("PCF, kg CO2e per kg", before.kg_co2e_per_kg, after.kg_co2e_per_kg),
            row(
                "PCF, kg CO2e per 1,000 parts",
                before.kg_co2e_per_1000_pieces,
                after.kg_co2e_per_1000_pieces,
            ),
            row(
                "Primary data share, %",
                before.primary_data_share * 100,
                after.primary_data_share * 100,
            ),
            row("Data quality (1 best, 5 worst)", before.dqr.overall, after.dqr.overall),
        ]
    )


def versions_table(state: ProjectState) -> pd.DataFrame:
    """Every accepted version, showing which one each material uses now."""
    columns = [
        "Version",
        "Material",
        "Supplier",
        "kg CO2e per kg",
        "Method",
        "Period end",
        "Added by",
        "Added",
        "In use",
    ]
    return pd.DataFrame(
        [
            {
                "Version": v.version_id,
                "Material": v.submission.material_number,
                "Supplier": v.submission.supplier_id,
                "kg CO2e per kg": v.value_per_kg,
                "Method": v.submission.method,
                "Period end": v.submission.reference_period_end,
                "Added by": v.user,
                "Added": v.created_at,
                "In use": state.active.get(v.submission.material_number) == v.version_id,
            }
            for v in state.versions
        ],
        columns=columns,
    )


def rejections_table(state: ProjectState) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "When": r.timestamp,
                "Material": r.submission.material_number,
                "Supplier": r.submission.supplier_id,
                "Why it was rejected": " ".join(r.reasons),
            }
            for r in state.rejections
        ],
        columns=["When", "Material", "Supplier", "Why it was rejected"],
    )


def audit_table(state: ProjectState) -> pd.DataFrame:
    return pd.DataFrame([e.model_dump() for e in state.audit], columns=AUDIT_COLUMNS)
