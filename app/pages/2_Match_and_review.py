"""Review suggested matches. Results stay in draft until every material has a decision."""

import os

import streamlit as st
from components import RESULTS_PAGE, disclaimer, no_data_prompt
from state import (
    LLM_CALLS,
    REVIEW_VERSION,
    get_bundle,
    get_candidates,
    get_matching_config,
    get_result,
    get_review,
    get_review_log,
)

from bom_to_pcf.matching.llm_matcher import API_KEY_VARIABLE, make_client, rank_with_llm
from bom_to_pcf.matching.review import (
    DECISION_LABELS,
    PENDING,
    add_llm_suggestion,
    apply_review_table,
    log_table,
    review_complete,
    review_table,
)

LOCKED_COLUMNS = [
    "Material",
    "Description",
    "Unit",
    "Suggested match",
    "Match score",
    "Source",
    "Other suggestions",
]
COLUMN_ORDER = [
    "Description",
    "Suggested match",
    "Decision",
    "Use instead",
    "Comment",
    "Match score",
    "Source",
    "Other suggestions",
    "Unit",
    "Material",
]


def api_key() -> str | None:
    try:
        return st.secrets.get(API_KEY_VARIABLE) or os.environ.get(API_KEY_VARIABLE)
    except FileNotFoundError:
        return os.environ.get(API_KEY_VARIABLE)


st.title("Match & review")
disclaimer()

if get_bundle() is None:
    no_data_prompt()
    st.stop()

candidates = get_candidates()
config = get_matching_config()
items = get_review()

st.markdown(
    "Check each suggested match and decide. The Results page uses unreviewed suggestions only as "
    "a provisional draft. A final result needs a decision on every material."
)

client = make_client(api_key())
if client is None:
    st.caption(
        "Suggestions use text matching. AI suggestions are switched off because no API key "
        "is set up, or the optional package is not installed."
    )
else:
    used = st.session_state.get(LLM_CALLS, 0)
    remaining = config.llm_session_call_limit - used
    if st.toggle("Use AI suggestions", value=config.llm_default_on):
        st.caption(
            f"Only the description, unit and candidate list are sent. {remaining} calls left "
            "in this session."
        )
        pending = [item for item in items if item.decision == PENDING]
        if st.button("Ask AI about pending materials", disabled=remaining < len(pending)):
            failed = 0
            for item in pending:
                suggestion = rank_with_llm(item.description, item.uom, candidates, client, config)
                st.session_state[LLM_CALLS] = st.session_state.get(LLM_CALLS, 0) + 1
                if suggestion is None:
                    failed += 1
                else:
                    add_llm_suggestion(item, suggestion)
            st.session_state[REVIEW_VERSION] += 1
            if failed:
                st.warning(f"{failed} AI requests failed, so text matches stay for those.")

reviewer = st.text_input("Your name, for the review log", placeholder="Reviewer name")
edited = st.data_editor(
    review_table(items, candidates),
    key=f"review_editor_{st.session_state[REVIEW_VERSION]}",
    hide_index=True,
    width="stretch",
    disabled=LOCKED_COLUMNS,
    column_order=COLUMN_ORDER,
    column_config={
        "Match score": st.column_config.NumberColumn(format="percent"),
        "Decision": st.column_config.SelectboxColumn(
            options=list(DECISION_LABELS.values()), required=True
        ),
        "Use instead": st.column_config.SelectboxColumn(
            options=[candidate.label for candidate in candidates],
            help="Only used when the decision is Choose other.",
        ),
    },
)
if st.button("Save decisions", type="primary"):
    try:
        apply_review_table(items, edited, candidates, reviewer, get_review_log())
    except ValueError as error:
        st.error(f"Nothing was saved: {error}.")
    else:
        st.session_state[REVIEW_VERSION] += 1
        st.rerun()

result = get_result()
if review_complete(items) and not result.is_draft:
    st.success("Every material has a decision, and the result is no longer a draft.")
elif review_complete(items):
    st.warning("Every material has a decision, but the result is still a draft.")
else:
    pending_count = sum(item.decision == PENDING for item in items)
    st.warning(f"{pending_count} materials still need a decision, so the result stays in draft.")
st.page_link(RESULTS_PAGE, label="See the results", icon="➡️")

st.subheader("Review log")
log = log_table(get_review_log())
if log.empty:
    st.caption("No decisions yet.")
else:
    st.dataframe(log, hide_index=True, width="stretch")
    st.download_button("Download review log", log.to_csv(index=False), "review_log.csv", "text/csv")
