"""Streamlit entry point. Pages are added here as each phase builds them."""

import streamlit as st
from components import (
    MATCH_PAGE,
    PRIMARY_PAGE,
    RESULTS_PAGE,
    START_PAGE,
    UPLOAD_PAGE,
    sidebar_progress,
)

st.set_page_config(page_title="bom-to-pcf", layout="wide")

page = st.navigation(
    [
        st.Page(START_PAGE, title="Start here", default=True),
        st.Page(UPLOAD_PAGE, title="Upload & validate"),
        st.Page(MATCH_PAGE, title="Match & review"),
        st.Page(RESULTS_PAGE, title="Results"),
        st.Page(PRIMARY_PAGE, title="Primary data"),
    ]
)
page.run()
sidebar_progress()
