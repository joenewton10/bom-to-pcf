"""Headline footprint, breakdowns and everything needed to judge how far to trust it."""

import plotly.express as px
import streamlit as st
from components import disclaimer, no_data_prompt
from state import get_result

from bom_to_pcf.outputs.tables import lines_table, material_table, stage_table

SHARE_FORMAT = {
    "kg CO2e per kg": st.column_config.NumberColumn(format="%.3f"),
    "Share": st.column_config.NumberColumn(format="percent"),
}
MIN_CHART_HEIGHT = 220
ROW_HEIGHT = 44


def contribution_chart(table, label: str) -> None:
    """One colour, sorted bars, direct labels; the table beneath carries the same values."""
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


st.title("Results")
disclaimer()

result = get_result()
if result is None:
    no_data_prompt()
    st.stop()

if result.is_draft:
    st.warning(f"**{result.status_label}**")
    for reason in result.draft_reasons:
        st.markdown(f"- {reason}")
else:
    st.success(f"**{result.status_label}**")
for gap in result.missing:
    st.markdown(f"- Missing: {gap}")

per_kg, per_pieces, primary, dqr = st.columns(4)
per_kg.metric("PCF per kg", f"{result.kg_co2e_per_kg:.2f}")
per_pieces.metric("PCF per 1,000 parts", f"{result.kg_co2e_per_1000_pieces:.2f}")
primary.metric("Primary data share", f"{result.primary_data_share:.0%}")
dqr.metric("Data quality", "n/a" if result.dqr.overall is None else f"{result.dqr.overall:.1f}")
st.caption(
    "PCF in kg CO₂e, cradle-to-gate. Data quality runs from 1 (best) to 5 (worst). "
    f"GWP set: {result.gwp_set}; sources do not all share one GWP basis."
)

stages = stage_table(result)
materials = material_table(result)
stage_col, material_col = st.columns(2)
with stage_col:
    st.subheader("By stage")
    if not stages.empty:
        contribution_chart(stages, "Stage")
        st.dataframe(stages, hide_index=True, width="stretch", column_config=SHARE_FORMAT)
with material_col:
    st.subheader("By material")
    if not materials.empty:
        contribution_chart(materials, "Material")
        st.dataframe(materials, hide_index=True, width="stretch", column_config=SHARE_FORMAT)

st.subheader("What this result leaves out")
for text in result.known_omissions:
    st.markdown(f"- Not modelled: {text}")
st.markdown(
    f"- Cut-off rule: {result.excluded_share:.1%} of the calculated impact is left out as "
    "small flows, listed below."
)

with st.expander("Left out by the cut-off rule"):
    st.dataframe(lines_table(result.excluded), hide_index=True, width="stretch")

with st.expander("Full inventory, with factor and source for every line"):
    st.dataframe(lines_table(result.lines), hide_index=True, width="stretch")
