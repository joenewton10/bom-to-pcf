"""Shared UI pieces."""

import plotly.express as px
import streamlit as st
from state import CHECKLIST, is_done

DISCLAIMER = "Illustrative data — not a verified PCF."
START_PAGE = "pages/0_Start_here.py"
UPLOAD_PAGE = "pages/1_Upload_and_validate.py"
MATCH_PAGE = "pages/2_Match_and_review.py"
RESULTS_PAGE = "pages/3_Results.py"
HOTSPOTS_PAGE = "pages/4_Hotspots_and_priorities.py"
SUPPLIER_PAGE = "pages/5_Supplier_requests.py"
PRIMARY_PAGE = "pages/6_Primary_data.py"
SCENARIOS_PAGE = "pages/7_Scenarios_and_variants.py"
MIN_CHART_HEIGHT = 220
ROW_HEIGHT = 44


def contribution_chart(table, label: str) -> None:
    """One colour, sorted bars, direct labels; a table nearby carries the same values."""
    figure = px.bar(
        table,
        x="kg CO2e per kg",
        y=label,
        orientation="h",
        text=table["Share"].map("{:.0%}".format),
        color_discrete_sequence=[st.get_option("theme.primaryColor")],
        hover_data={"Share": ":.1%", "kg CO2e per kg": ":.3f"},
    )
    figure.update_traces(textposition="outside", cliponaxis=False, width=0.5)
    figure.update_layout(
        yaxis={"categoryorder": "total ascending", "title": None},
        xaxis={"title": "kg CO₂e per kg of product", "showgrid": False, "zeroline": True},
        margin={"l": 0, "r": 40, "t": 8, "b": 0},
        height=max(MIN_CHART_HEIGHT, ROW_HEIGHT * len(table) + 80),
        showlegend=False,
    )
    st.plotly_chart(figure, width="stretch")


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
