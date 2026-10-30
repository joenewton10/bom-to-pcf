"""Shared UI pieces."""

import streamlit as st
from state import CHECKLIST, is_done

DISCLAIMER = "Illustrative data — not a verified PCF."
START_PAGE = "pages/0_Start_here.py"
UPLOAD_PAGE = "pages/1_Upload_and_validate.py"
RESULTS_PAGE = "pages/3_Results.py"


def sidebar_progress() -> None:
    with st.sidebar:
        st.subheader("Your progress")
        for step in CHECKLIST:
            icon = ":material/check_circle:" if is_done(step) else ":material/circle:"
            st.markdown(f"{icon} {step}")


def disclaimer() -> None:
    st.caption(DISCLAIMER)


def no_data_prompt() -> None:
    st.info("No data loaded yet. Try the demo or upload your own files.")
    st.page_link(START_PAGE, label="Go to Start here", icon="▶️")
    st.page_link(UPLOAD_PAGE, label="Go to Upload & validate", icon="📤")
