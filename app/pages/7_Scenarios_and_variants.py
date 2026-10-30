"""Compare what-ifs, explore sensitivity and uncertainty, and calculate the product family."""

import plotly.express as px
import streamlit as st
from components import disclaimer, no_data_prompt
from state import (
    SCENARIOS_DIR,
    current_mappings,
    get_analysis,
    get_config,
    get_effective_bundle,
    get_factors,
    get_family,
    get_method,
    get_result,
    known_factors,
)

from bom_to_pcf.methods.uncertainty import monte_carlo
from bom_to_pcf.scenarios import Scenario, load_scenarios, run_scenario, scenario_table
from bom_to_pcf.variants import family_table, run_family

# One hue, light to dark, because recycled share is an ordered quantity.
SHARE_COLOURS = ["#9CCFC0", "#4F9E8A", "#1F6F5C"]
MAX_RUNS = 20_000
MIN_RUNS = 100

st.title("Scenarios & variants")
disclaimer()

base_result = get_result()
if base_result is None:
    no_data_prompt()
    st.stop()

bundle = get_effective_bundle()
config = get_config()
method = get_method()
factors = get_factors()
mappings = current_mappings()
analysis = get_analysis()
if bundle.supplier_pcfs:
    st.caption(
        "Materials with supplier data keep that data in these calculations, so recycled PET has no "
        "effect on a film that already has a supplier value."
    )


def calculate(scenario: Scenario):
    return run_scenario(bundle, config, method, factors, mappings, scenario, analysis)


scenarios_tab, sensitivity_tab, uncertainty_tab, family_tab = st.tabs(
    ["Scenarios", "Sensitivity", "Uncertainty", "Product family"]
)

with scenarios_tab:
    results = [(scenario, calculate(scenario)) for scenario in load_scenarios(SCENARIOS_DIR)]
    st.dataframe(
        scenario_table(results),
        hide_index=True,
        width="stretch",
        column_config={
            "kg CO2e per kg": st.column_config.NumberColumn(format="%.3f"),
            "kg CO2e per 1,000 parts": st.column_config.NumberColumn(format="%.3f"),
            "Change": st.column_config.NumberColumn(format="percent"),
            "Data quality": st.column_config.NumberColumn(format="%.1f"),
            "What it assumes": st.column_config.TextColumn(width="large"),
        },
    )

with sensitivity_tab:
    st.caption(
        "Move a slider and the footprint recalculates. Nothing here changes your saved data."
    )
    renewable, recycled, scrap = st.columns(3)
    custom = Scenario(
        name="Custom",
        renewable_share=renewable.slider("Renewable electricity", 0.0, 1.0, 0.0, 0.05),
        recycled_share=recycled.slider("Recycled share of PET resin", 0.0, 1.0, 0.0, 0.05),
        scrap_multiplier=scrap.slider("Scrap, times current rate", 0.5, 2.0, 1.0, 0.1),
    )
    outcome = calculate(custom)
    per_kg, per_parts = st.columns(2)
    delta = outcome.kg_co2e_per_kg - base_result.kg_co2e_per_kg
    per_kg.metric(
        "PCF per kg", f"{outcome.kg_co2e_per_kg:.2f}", f"{delta:+.2f}", delta_color="inverse"
    )
    per_parts.metric("PCF per 1,000 parts", f"{outcome.kg_co2e_per_1000_pieces:.2f}")

with uncertainty_tab:
    st.warning(
        "The spreads are the author's assumptions, based on each factor's quality score. Sources "
        "do not publish them. Read this as how much the weak data could matter, not as a "
        "statistical confidence interval."
    )
    settings = analysis.uncertainty
    left, right = st.columns(2)
    runs = left.number_input("Runs", MIN_RUNS, MAX_RUNS, settings.runs, step=MIN_RUNS)
    fixed = right.checkbox("Use a fixed seed, so results repeat", value=True)
    simulated = monte_carlo(
        base_result.lines, known_factors(), settings, int(runs), settings.seed if fixed else None
    )
    p5, p50, p95 = st.columns(3)
    p5.metric("P5", f"{simulated.p5:.2f}")
    p50.metric("P50", f"{simulated.p50:.2f}")
    p95.metric("P95", f"{simulated.p95:.2f}")
    st.caption(f"kg CO₂e per kg. The calculated value is {simulated.deterministic:.2f}.")
    histogram = px.histogram(
        x=simulated.samples,
        nbins=40,
        labels={"x": "kg CO₂e per kg"},
        color_discrete_sequence=[st.get_option("theme.primaryColor")],
    )
    histogram.update_layout(yaxis_title="Runs", bargap=0.05, margin={"t": 8}, height=280)
    st.plotly_chart(histogram, width="stretch")

with family_tab:
    family = get_family()
    table = family_table(run_family(bundle, config, method, factors, mappings, family, analysis))
    st.caption(
        f"{len(table)} variants from one model. Assumes the same part area and scrap rates, and "
        "energy per kg that does not change with thickness. Without adhesive, the liner goes too."
    )
    figure = px.line(
        table,
        x="Thickness (µm)",
        y="kg CO2e per 1,000 parts",
        color="Recycled share",
        facet_col="Adhesive",
        markers=True,
        color_discrete_sequence=SHARE_COLOURS,
        category_orders={"Adhesive": ["Yes", "No"]},
    )
    figure.update_traces(line={"width": 2}, marker={"size": 8})
    figure.update_layout(margin={"t": 32}, height=340, legend_title_text="Recycled share")
    st.plotly_chart(figure, width="stretch")
    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        column_config={
            "Recycled share": st.column_config.NumberColumn(format="percent"),
            "Part mass (g)": st.column_config.NumberColumn(format="%.2f"),
            "kg CO2e per kg": st.column_config.NumberColumn(format="%.3f"),
            "kg CO2e per 1,000 parts": st.column_config.NumberColumn(format="%.3f"),
        },
    )
    st.download_button(
        "Download as CSV", table.to_csv(index=False), "pet_family_variants.csv", "text/csv"
    )
