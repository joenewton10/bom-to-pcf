"""Landing page. All wording is the owner's, from PROJECT_PLAN.md section 10. Do not edit it."""

import streamlit as st
from components import RESULTS_PAGE, UPLOAD_PAGE
from state import load_demo

METHODOLOGY_URL = "https://github.com/joenewton10/bom-to-pcf/blob/main/docs/methodology.md"
GITHUB_URL = "https://github.com/joenewton10/bom-to-pcf"
PORTFOLIO_URL = "https://joenewton10.github.io"
BUILT_PAGES = {1: UPLOAD_PAGE, 3: RESULTS_PAGE}

FLOW = """
digraph {
  rankdir=LR;
  node [shape=box, style="rounded", fontsize=11];
  upload [label="Upload BOM"];
  validate [label="Validate"];
  match [label="Match materials"];
  review [label="Review"];
  calculate [label="Calculate PCF"];
  hotspots [label="Find hotspots"];
  request [label="Request supplier data"];
  primary [label="Add primary data"];
  export [label="Export"];
  upload -> validate -> match -> review -> calculate -> hotspots -> request -> primary -> export;
  primary -> calculate [label="recalculate", constraint=false];
}
"""

STEPS = [
    (
        "1. Upload & validate",
        "Upload a BOM export, production routing and any supplier data. The tool cleans up units, "
        "spots duplicates and checks that the mass balance adds up.",
        "BOM, routing, supplier files",
        "a clean, checked inventory",
    ),
    (
        "2. Match & review",
        "Each material is matched to an emission factor. Suggestions come from text matching and, "
        "optionally, AI. Nothing is used until a person approves it.",
        "material descriptions",
        "approved matches with an audit log",
    ),
    (
        "3. Results",
        "See the carbon footprint per kg and per 1,000 parts, broken down by material and process "
        "step, with the share of primary data and a data quality rating.",
        "approved inventory",
        "the PCF and its breakdown",
    ),
    (
        "4. Hotspots & priorities",
        "Find out what drives the footprint and which supplier to ask for data first. The ranking "
        "weighs each material's impact against how weak its current data is.",
        "results",
        "a ranked list of where better data matters most",
    ),
    (
        "5. Supplier requests",
        "Create ready-to-send data requests in a standard format and track each one, from "
        "requested to validated.",
        "priority list",
        "request templates and a status tracker",
    ),
    (
        "6. Primary data",
        "Add real supplier data when it arrives. It's checked before use, replaces the database "
        "value and recalculates the footprint, with a before-and-after comparison. Every change is "
        "logged and can be undone.",
        "supplier PCFs",
        "an updated, more accurate PCF",
    ),
    (
        "7. Scenarios & variants",
        "Test what-ifs, like green electricity, recycled PET or higher scrap rates, and calculate "
        "a whole product family in one run.",
        "model parameters",
        "comparisons and sensitivity results",
    ),
    (
        "8. Export & claims",
        "Check which environmental claims the result can support, then download the PCF in PACT "
        "format, a Digital Product Passport-style data sheet and a full methods report.",
        "final results",
        "PACT JSON, DPP sheet, report",
    ),
]

st.title("From bill of materials to product carbon footprint")

st.markdown(
    "I built this tool to show how a product carbon footprint can be calculated automatically "
    "from the data a manufacturer already has: a bill of materials, production steps and energy "
    "use. It follows ISO 14067 and the TfS PCF Guideline, and it's designed to get better over "
    "time. You start with database values, and as suppliers send their real data, the footprint "
    "becomes more accurate and more trustworthy."
)
st.markdown(
    "The example is a die-cut PET film part, based on the kind of precision converting work I "
    "see every day. All numbers are illustrative, but the method is the real thing."
)

if st.button("▶ Try the demo", type="primary"):
    load_demo()
    st.switch_page(RESULTS_PAGE)
st.caption("No files needed. The demo loads a complete example so you can explore every step.")

st.header("How it works")
st.graphviz_chart(FLOW, width="stretch")

st.header("The steps")
for start in range(0, len(STEPS), 3):
    for column, (title, description, inputs, outputs) in zip(
        st.columns(3), STEPS[start : start + 3], strict=False
    ):
        with column.container(border=True):
            st.markdown(f"**{title}**")
            st.markdown(description)
            st.markdown(f"*In:* {inputs} · *Out:* {outputs}")
            number = int(title.split(".")[0])
            if number in BUILT_PAGES:
                st.page_link(BUILT_PAGES[number], label=f"Open {title.split('. ')[1]}", icon="➡️")
            else:
                st.button(f"Open {title.split('. ')[1]}", disabled=True, key=f"open_{number}")

st.header("How to read the results")
st.info(
    "- **Product carbon footprint (PCF):** the greenhouse gas emissions linked to making one unit "
    "of product, in kg CO₂e.\n"
    "- **Cradle-to-gate:** everything from raw material extraction up to the product leaving the "
    "factory. Use and disposal are not included.\n"
    "- **Primary data share:** how much of the footprint is based on real data from suppliers or "
    "the site, rather than database averages. Higher is better.\n"
    "- **Data quality rating (DQR):** a score for how well the data fits the product in terms of "
    "technology, location and time."
)

with st.expander("Method & limitations", expanded=False):
    st.markdown(
        "- Standards: ISO 14067, ISO 14040/44, GHG Protocol Product Standard, TfS PCF Guideline, "
        "PACT.\n"
        "- Boundary: cradle-to-gate, declared unit 1 kg of finished parts.\n"
        "- GWP: IPCC AR6, 100-year.\n"
        "- All data is representative and illustrative. This is not a verified PCF and should not "
        "be used for real claims.\n"
        f"- Full details: [docs/methodology.md]({METHODOLOGY_URL})"
    )

st.caption(
    f"Built by Joseph Newton · [GitHub]({GITHUB_URL}) · [joenewton10.github.io]({PORTFOLIO_URL})"
)
