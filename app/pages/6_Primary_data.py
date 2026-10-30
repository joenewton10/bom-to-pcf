"""Add supplier PCFs, compare before and after, undo changes and see the full history."""

from datetime import date

import streamlit as st
from components import START_PAGE, disclaimer, no_data_prompt
from state import (
    LAST_BEFORE,
    REVIEW_VERSION,
    backend_name,
    current_mappings,
    get_bundle,
    get_config,
    get_factors,
    get_method,
    get_project,
    get_result,
    note_revert,
    save_project,
    set_project,
    start_fresh,
    submit_pcf,
)

from bom_to_pcf.io.supplier_reader import read_submission_file
from bom_to_pcf.models import SupplierPcf
from bom_to_pcf.primary_data.replacement import (
    audit_table,
    compare_results,
    rejections_table,
    revert,
    versions_table,
)
from bom_to_pcf.primary_data.validation import secondary_per_kg
from bom_to_pcf.storage.base import SQLITE, export_state, import_state

METHODS = ["ISO 14067", "TfS", "PACT", "other"]
UNITS = ["kg", "g", "t", "m2", "piece"]
BOUNDARIES = ["cradle-to-gate", "gate-to-gate", "cradle-to-grave"]
EXAMPLE_PERIOD_START = date(2025, 1, 1)
EXAMPLE_PERIOD_END = date(2025, 12, 31)
EXAMPLE_DQR = 1.5
EXAMPLE_NOTE = "TEST RECORD: an illustrative value, not real supplier data."


def show_check(material: str, check) -> None:
    if check.accepted:
        st.success(f"Accepted for material {material}. The footprint has been recalculated.")
    else:
        st.error(f"Rejected for material {material}. The database value stays in use.")
        for reason in check.reasons:
            st.markdown(f"- {reason}")


st.title("Primary data")
disclaimer()

bundle = get_bundle()
if bundle is None:
    no_data_prompt()
    st.stop()

config = get_config()
project = get_project()
result = get_result()
lines = {line.material_number: line for line in bundle.bom}

if backend_name() == SQLITE:
    st.caption("Saved on this computer, so your work is still here next time.")
else:
    st.info(
        "This hosted app does not keep your work. Your changes last for this session, so download "
        "your progress below and upload it next time to carry on."
    )

user = st.text_input("Your name, for the audit trail", key="primary_user")


def fill_example() -> None:
    """Fill the form with a clearly labelled test record, based on the database value."""
    material = st.session_state["primary_material"]
    secondary = secondary_per_kg(material, current_mappings(), get_factors(), get_config())
    ratio = get_method().primary_data.example_ratio
    if secondary is not None:
        st.session_state["primary_value"] = round(secondary * ratio, 3)
    st.session_state["primary_supplier"] = lines[material].supplier_id or ""
    st.session_state["primary_unit"] = "kg"
    st.session_state["primary_start"] = EXAMPLE_PERIOD_START
    st.session_state["primary_end"] = EXAMPLE_PERIOD_END
    st.session_state["primary_method"] = METHODS[0]
    st.session_state["primary_boundary"] = BOUNDARIES[0]
    st.session_state["primary_dqr"] = EXAMPLE_DQR
    st.session_state["primary_share"] = get_method().primary_data.example_primary_share
    st.session_state["primary_notes"] = EXAMPLE_NOTE


st.header("Add supplier data")
enter_tab, upload_tab = st.tabs(["Enter it", "Upload a file"])
with enter_tab:
    material = st.selectbox(
        "Material",
        list(lines),
        format_func=lambda m: f"{m}, {lines[m].description}",
        key="primary_material",
    )
    st.button(
        "Fill with a test example",
        on_click=fill_example,
        help="Uses 80% of the database value, labelled as a test record.",
    )
    with st.form("primary_form"):
        left, middle, right = st.columns(3)
        supplier = left.text_input("Supplier ID", key="primary_supplier")
        value = middle.number_input(
            "PCF value (kg CO₂e per declared unit)",
            min_value=0.0,
            value=None,
            format="%.4f",
            key="primary_value",
        )
        unit = right.selectbox("Declared unit", UNITS, key="primary_unit")
        start = left.date_input("Reference period start", value=None, key="primary_start")
        end = middle.date_input("Reference period end", value=None, key="primary_end")
        method = right.selectbox("Method", METHODS, key="primary_method")
        boundary = left.selectbox("Boundary", BOUNDARIES, key="primary_boundary")
        dqr = middle.number_input(
            "DQR (1 best, 5 worst)", min_value=1.0, max_value=5.0, value=None, key="primary_dqr"
        )
        share = right.number_input(
            "Supplier's primary data share (0 to 1)",
            min_value=0.0,
            max_value=1.0,
            value=None,
            key="primary_share",
        )
        notes = st.text_input("Notes", key="primary_notes")
        comment = st.text_input(
            "Reviewer comment (required if the value looks implausible)", key="primary_comment"
        )
        submitted = st.form_submit_button("Check and add", type="primary")
    if submitted:
        pcf = SupplierPcf(
            supplier_id=supplier,
            material_number=material,
            pcf_value=value,
            declared_unit=unit,
            reference_period_start=start,
            reference_period_end=end,
            method=method,
            primary_data_share=share,
            dqr=dqr,
            boundary=boundary,
            notes=notes or None,
        )
        try:
            before = result
            check = submit_pcf(pcf, user, comment)
        except ValueError as error:
            st.error(f"Nothing was added: {error}.")
        else:
            if check.accepted:
                st.session_state[LAST_BEFORE] = before
            show_check(material, check)
            result = get_result()

with upload_tab:
    st.caption(
        "JSON or CSV with: supplier_id, material_number, pcf_value, declared_unit, "
        "reference_period_start, reference_period_end, method, primary_data_share, dqr, boundary, "
        "notes."
    )
    upload = st.file_uploader("Supplier PCF file", type=["json", "csv"], key="primary_upload")
    if st.button("Check and add from file", disabled=upload is None):
        before = result
        try:
            submissions = read_submission_file(upload.getvalue(), upload.name)
            checks = [(pcf, submit_pcf(pcf, user)) for pcf in submissions]
        except ValueError as error:
            st.error(f"Nothing more was added: {error}.")
        else:
            for pcf, check in checks:
                show_check(pcf.material_number, check)
            if any(check.accepted for _, check in checks):
                st.session_state[LAST_BEFORE] = before
            result = get_result()

before = st.session_state.get(LAST_BEFORE)
if before is not None:
    st.header("Before and after the last change")
    st.dataframe(
        compare_results(before, result),
        hide_index=True,
        width="stretch",
        column_config={
            name: st.column_config.NumberColumn(format="%.3f")
            for name in ("Before", "After", "Change")
        },
    )

st.header("Versions")
versions = versions_table(project)
if versions.empty:
    st.caption("No supplier data has been accepted yet, so database values are in use.")
else:
    st.dataframe(versions, hide_index=True, width="stretch")
    changed = sorted({v.submission.material_number for v in project.versions})
    undo_material = st.selectbox("Material to change back", changed, key="undo_material")
    options = [None] + [
        v.version_id for v in project.versions if v.submission.material_number == undo_material
    ]
    target = st.selectbox(
        "Go back to",
        options,
        format_func=lambda option: option or "Database value",
        key="undo_target",
    )
    undo_reason = st.text_input("Reason for the change", key="undo_reason")
    if st.button("Undo"):
        before = result
        try:
            revert(project, undo_material, target, user, undo_reason)
            note_revert(undo_material)
            save_project()
        except ValueError as error:
            st.error(f"Nothing was changed: {error}.")
        else:
            st.session_state[LAST_BEFORE] = before
            st.rerun()

rejected = rejections_table(project)
if not rejected.empty:
    st.header("Rejected submissions")
    st.dataframe(rejected, hide_index=True, width="stretch")

st.header("Audit trail")
audit = audit_table(project)
if audit.empty:
    st.caption("No changes yet.")
else:
    st.dataframe(audit, hide_index=True, width="stretch")
    st.download_button("Download audit trail", audit.to_csv(index=False), "audit.csv", "text/csv")

st.header("Save or restore your progress")
st.caption("One file with your supplier data, review decisions and full history.")
st.download_button(
    "Download progress", export_state(project), "bom_to_pcf_progress.json", "application/json"
)
restore = st.file_uploader("Saved progress file", type=["json"], key="restore_upload")
if st.button("Restore progress", disabled=restore is None):
    try:
        set_project(import_state(restore.getvalue()))
    except ValueError as error:
        st.error(f"Nothing was restored: {error}.")
    else:
        st.session_state[REVIEW_VERSION] += 1
        st.session_state.pop(LAST_BEFORE, None)
        st.rerun()

st.header("Start fresh")
if backend_name() == SQLITE:
    st.caption(
        "Clears your data, review decisions and supplier data from the app. The old database is "
        "kept beside the new one as data/app-archive-<date>.db."
    )
else:
    st.caption(
        "Clears your data, review decisions and supplier data from this session. Download your "
        "progress first if you want to keep it."
    )
confirmed = st.checkbox("Yes, start again", key="confirm_fresh")
if st.button("Start fresh", disabled=not confirmed):
    start_fresh()
    st.switch_page(START_PAGE)
