"""Create data requests for suppliers and track each one. The app does not send anything."""

from datetime import date

import streamlit as st
from components import PRIMARY_PAGE, disclaimer, no_data_prompt
from state import (
    REVIEW_VERSION,
    get_bundle,
    get_config,
    get_engagement,
    get_priorities,
    get_project,
    get_result,
    save_project,
    templates_dir,
)

from bom_to_pcf.suppliers.priority import supplier_coverage
from bom_to_pcf.suppliers.requests import (
    mark_requested,
    request_files,
    set_note,
    tracker_table,
    zip_requests,
)

st.title("Supplier requests")
disclaimer()

result = get_result()
bundle = get_bundle()
if result is None:
    no_data_prompt()
    st.stop()

project = get_project()
config = get_config()
rules = get_engagement().requests
rows, _ = get_priorities()
suppliers = {supplier.supplier_id: supplier for supplier in bundle.suppliers}

st.metric("PCF covered by validated supplier data", f"{supplier_coverage(result):.0%}")

st.header("Create requests")
ranked = [row.supplier_id for row in rows if row.supplier_id in suppliers]
options = list(dict.fromkeys(ranked))
chosen = st.multiselect(
    "Suppliers, highest priority first",
    options,
    default=options[:1],
    format_func=lambda supplier_id: suppliers[supplier_id].name,
)
if not chosen:
    st.caption("Choose at least one supplier.")
else:
    files: dict[str, str] = {}
    for supplier_id in chosen:
        files |= request_files(suppliers[supplier_id], bundle.bom, config, rules, templates_dir())
    st.caption("Each request has a cover message and a template in JSON and CSV. Nothing is sent.")
    st.download_button(
        "Download all as ZIP", zip_requests(files), "supplier_requests.zip", "application/zip"
    )
    for supplier_id in chosen:
        name = f"pcf_request_{supplier_id}"
        with st.expander(suppliers[supplier_id].name):
            st.markdown(files[f"{name}.md"])
            cover, as_json, as_csv = st.columns(3)
            cover.download_button(
                "Cover message", files[f"{name}.md"], f"{name}.md", key=f"{name}m"
            )
            as_json.download_button("JSON", files[f"{name}.json"], f"{name}.json", key=f"{name}j")
            as_csv.download_button("CSV", files[f"{name}.csv"], f"{name}.csv", key=f"{name}c")
    if st.button("Mark these as requested", type="primary"):
        for supplier_id in chosen:
            mark_requested(project, supplier_id, bundle.bom, date.today())
        save_project()
        st.session_state[REVIEW_VERSION] += 1
        st.rerun()

st.header("Status tracker")
st.caption(
    "Status moves to received, then validated or rejected, by itself when data is added on the "
    "Primary data page. You can edit the notes."
)
tracker = tracker_table(project, bundle.bom, bundle.suppliers)
edited = st.data_editor(
    tracker,
    key=f"tracker_{st.session_state[REVIEW_VERSION]}",
    hide_index=True,
    width="stretch",
    disabled=[column for column in tracker.columns if column != "Notes"],
)
if st.button("Save notes"):
    supplier_by_material = {line.material_number: line.supplier_id for line in bundle.bom}
    for row in edited.to_dict("records"):
        note = row["Notes"] if isinstance(row["Notes"], str) else ""
        if note != (
            project.requests.get(row["Material"]).note
            if row["Material"] in project.requests
            else ""
        ):
            set_note(project, row["Material"], supplier_by_material[row["Material"]] or "", note)
    save_project()
    st.rerun()
st.page_link(PRIMARY_PAGE, label="Add supplier data", icon=":material/arrow_forward:")
