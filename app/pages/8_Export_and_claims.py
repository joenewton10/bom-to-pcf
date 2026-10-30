"""Check a claim, then download the outputs."""

import json

import streamlit as st
from components import disclaimer, no_data_prompt
from state import (
    EXPORTED,
    ROOT,
    get_analysis,
    get_claims_rules,
    get_config,
    get_method,
    get_project,
    get_result,
    get_review_log,
    known_factors,
    mark_done,
    templates_dir,
)

from bom_to_pcf.claims import BLOCKED, NEEDS_MORE, NOT_SUPPORTED, SUPPORTED, check_claim
from bom_to_pcf.matching.review import log_table
from bom_to_pcf.methods.uncertainty import monte_carlo
from bom_to_pcf.outputs.dpp_sheet import render_dpp_sheet
from bom_to_pcf.outputs.pact_export import build_footprint, validation_errors
from bom_to_pcf.outputs.report import render_report
from bom_to_pcf.primary_data.replacement import audit_table

OWN_CLAIM = "Type your own"
SHOW_VERDICT = {
    SUPPORTED: st.success,
    NEEDS_MORE: st.warning,
    NOT_SUPPORTED: st.error,
    BLOCKED: st.error,
}


def exported() -> None:
    mark_done(EXPORTED)


st.title("Export & claims")
disclaimer()

result = get_result()
if result is None:
    no_data_prompt()
    st.stop()

config = get_config()
rules = get_claims_rules()
known = known_factors()

if result.is_draft:
    st.warning(
        f"**{result.status_label}.** Every claim is blocked until the draft reasons are resolved."
    )

st.header("Check a claim")
examples = [text.format(per_kg=f"{result.kg_co2e_per_kg:.2f}") for text in rules.examples]
choice = st.selectbox("Claim", [*examples, OWN_CLAIM])
claim = st.text_input("Your claim") if choice == OWN_CLAIM else choice
if claim.strip():
    verdict = check_claim(claim, result, rules)
    SHOW_VERDICT[verdict.verdict](f"**{verdict.label}.** {verdict.reason}")
    st.caption(f"Basis: {verdict.basis}")
st.caption(rules.legal_note)

st.header("Download")
footprint = build_footprint(result, config, get_method(), known)
errors = validation_errors(footprint, ROOT)
if errors:
    st.error("The PACT file does not pass the official schema: " + "; ".join(errors))
else:
    st.success(f"The PACT file passes the official schema, version {footprint['specVersion']}.")
settings = get_analysis().uncertainty
uncertainty = monte_carlo(result.lines, known, settings, settings.runs, settings.seed)
stem = config.product_id
pact, sheet, report = st.columns(3)
pact.download_button(
    "PACT JSON",
    json.dumps(footprint, indent=2, ensure_ascii=False),
    f"{stem}_pact.json",
    "application/json",
    disabled=bool(errors),
    on_click=exported,
)
sheet.download_button(
    "Data sheet (DPP style)",
    render_dpp_sheet(result, config, templates_dir()),
    f"{stem}_data_sheet.html",
    "text/html",
    on_click=exported,
)
report.download_button(
    "Methods report",
    render_report(result, config, uncertainty, templates_dir()),
    f"{stem}_report.md",
    "text/markdown",
    on_click=exported,
)
review, audit = st.columns(2)
review.download_button(
    "Review log",
    log_table(get_review_log()).to_csv(index=False),
    f"{stem}_review_log.csv",
    "text/csv",
    on_click=exported,
)
audit.download_button(
    "Audit trail",
    audit_table(get_project()).to_csv(index=False),
    f"{stem}_audit.csv",
    "text/csv",
    on_click=exported,
)
