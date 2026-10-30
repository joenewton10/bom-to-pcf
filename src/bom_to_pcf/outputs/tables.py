"""Turn a result into plain-English tables for the app and exports."""

import pandas as pd

from bom_to_pcf.models import PcfResult, ResultLine

STAGE_LABELS = {
    "materials": "Materials",
    "packaging": "Packaging",
    "inbound_transport": "Inbound transport",
    "converting_energy": "Converting energy",
    "site_overhead": "Site overhead",
    "scrap_treatment": "Scrap treatment",
}


def contribution_table(values: dict[str, float], total: float, label: str) -> pd.DataFrame:
    """Contributions sorted largest first, each with its share of the total."""
    table = pd.DataFrame(
        [
            {label: name, "kg CO2e per kg": value, "Share": value / total if total else 0.0}
            for name, value in values.items()
        ],
        columns=[label, "kg CO2e per kg", "Share"],
    )
    return table.sort_values("kg CO2e per kg", ascending=False, ignore_index=True)


def stage_table(result: PcfResult) -> pd.DataFrame:
    labelled = {STAGE_LABELS.get(k, k): v for k, v in result.by_stage.items()}
    return contribution_table(labelled, result.kg_co2e_per_kg, "Stage")


def material_table(result: PcfResult) -> pd.DataFrame:
    return contribution_table(result.by_material, result.kg_co2e_per_kg, "Material")


def lines_table(lines: list[ResultLine]) -> pd.DataFrame:
    """One row per inventory line, tracing each impact to its factor and source."""
    return pd.DataFrame(
        [
            {
                "Stage": STAGE_LABELS.get(line.stage, line.stage),
                "Item": line.description,
                "Quantity per kg": line.quantity,
                "Unit": line.unit,
                "Factor": line.factor_id or "",
                "Source": line.source_id,
                "kg CO2e per kg": line.impact,
                "Note": line.note,
            }
            for line in lines
        ],
        columns=[
            "Stage",
            "Item",
            "Quantity per kg",
            "Unit",
            "Factor",
            "Source",
            "kg CO2e per kg",
            "Note",
        ],
    )
