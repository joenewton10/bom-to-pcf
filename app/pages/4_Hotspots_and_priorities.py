"""What drives the footprint, and which supplier to ask for data first."""

import streamlit as st
from components import SUPPLIER_PAGE, contribution_chart, disclaimer, no_data_prompt
from state import HOTSPOTS, get_priorities, get_result, mark_done

from bom_to_pcf.outputs.tables import stage_table
from bom_to_pcf.suppliers.priority import priority_table, recommendations

st.title("Hotspots & priorities")
disclaimer()

result = get_result()
if result is None:
    no_data_prompt()
    st.stop()
mark_done(HOTSPOTS)

rows, rules = get_priorities()

st.header("Where to ask first")
for advice in recommendations(rows, rules):
    st.markdown(f"- {advice}")
st.page_link(SUPPLIER_PAGE, label="Create supplier requests", icon=":material/arrow_forward:")

st.header("Supplier priority ranking")
st.caption(
    "Priority score = contribution to the PCF × data quality gap. The gap runs from 0 at the best "
    "DQR to 1 at the worst. The last column is the footprint resting on weak data: an indicator, "
    "not a statistical uncertainty."
)
st.dataframe(
    priority_table(rows),
    hide_index=True,
    width="stretch",
    column_config={
        "Contribution": st.column_config.NumberColumn(format="percent"),
        "DQR": st.column_config.NumberColumn(format="%.1f"),
        "Priority score": st.column_config.NumberColumn(format="%.3f"),
        "Uncertainty reduced (kg CO2e per kg)": st.column_config.NumberColumn(format="%.3f"),
    },
)

st.header("What drives the footprint")
contribution_chart(stage_table(result), "Stage")
