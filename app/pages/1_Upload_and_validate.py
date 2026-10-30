"""Upload an input set or load the demo, then see what validation found."""

import streamlit as st
from components import RESULTS_PAGE, disclaimer
from state import DATA_SOURCE, get_bundle, get_result, load_demo, load_uploads

from bom_to_pcf.io.inputs import (
    BOM_FILE,
    ROUTING_FILE,
    SUPPLIER_PCF_FILE,
    SUPPLIERS_FILE,
    TRANSPORT_FILE,
)
from bom_to_pcf.models import Severity, issues_table

UPLOADS = {
    BOM_FILE: ("BOM export", ["csv"]),
    ROUTING_FILE: ("Routing and energy", ["csv"]),
    SUPPLIERS_FILE: ("Supplier master data", ["csv"]),
    SUPPLIER_PCF_FILE: ("Supplier PCFs", ["json"]),
    TRANSPORT_FILE: ("Transport legs", ["csv"]),
}

st.title("Upload & validate")
disclaimer()

if st.button("Use the demo files", type="primary"):
    load_demo()

st.subheader("Or upload your own")
st.caption(
    "All five files are needed. Materials must fit the demo product's configuration, "
    "and any material without a factor match is reported as a gap."
)
columns = st.columns(3)
files = {}
for index, (name, (label, types)) in enumerate(UPLOADS.items()):
    upload = columns[index % 3].file_uploader(label, type=types, key=f"upload_{name}")
    if upload is not None:
        files[name] = upload.getvalue()

if st.button("Validate uploaded files", disabled=len(files) < len(UPLOADS)):
    load_uploads(files)

bundle = get_bundle()
if bundle is None:
    st.stop()

source = "demo files" if st.session_state[DATA_SOURCE] == "demo" else "uploaded files"
st.header("What we found")
st.caption(f"Checking the {source}.")

counts = {severity: 0 for severity in Severity}
for issue in bundle.issues:
    counts[issue.severity] += 1
bom_col, error_col, warning_col, info_col = st.columns(4)
bom_col.metric("BOM lines kept", len(bundle.bom))
error_col.metric("Errors", counts[Severity.ERROR])
warning_col.metric("Warnings", counts[Severity.WARNING])
info_col.metric("Notes", counts[Severity.INFO])

if bundle.has_errors:
    st.error("Some inputs have errors. Results will stay in draft until they are fixed.")
else:
    st.success("No errors. Warnings are worth a look, but they do not stop the calculation.")
st.dataframe(
    issues_table(bundle.issues),
    hide_index=True,
    width="stretch",
    column_config={"message": st.column_config.TextColumn(width="large")},
)

result = get_result()
balance = result.mass_balance
st.header("Mass balance")
st.caption("Per kg of finished product. Packaging is not part of this check.")
inputs_col, product_col, scrap_col, gap_col = st.columns(4)
inputs_col.metric("Material in", f"{balance.inputs_kg:.3f} kg")
product_col.metric("Product out", f"{balance.product_kg:.3f} kg")
scrap_col.metric("Scrap out", f"{balance.scrap_kg:.3f} kg")
gap_col.metric("Unexplained", f"{balance.imbalance_share:.2%}")
if balance.passed:
    st.success(f"The balance closes within the {balance.tolerance_share:.0%} tolerance.")
else:
    st.error(
        f"The balance is out by {balance.imbalance_share:.1%}, above the "
        f"{balance.tolerance_share:.0%} tolerance. Check the BOM quantities and scrap rates."
    )

st.page_link(RESULTS_PAGE, label="See the results", icon="➡️")
