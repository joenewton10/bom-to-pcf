"""Rank materials by where better supplier data would matter most."""

from collections import defaultdict

import pandas as pd

from bom_to_pcf.models import (
    BomLine,
    EmissionFactor,
    PcfResult,
    PriorityRow,
    PriorityRules,
    ResultLine,
    Supplier,
)

MATERIAL_STAGES = ("materials", "packaging")
PRIMARY = "primary"
SECONDARY = "secondary"


def _line_dqr(factor: EmissionFactor | None, rules: PriorityRules) -> float:
    """A factor's mean score. A missing score counts as the worst, as PACT requires upstream."""
    scores = [factor.dqr_tech, factor.dqr_geo, factor.dqr_time] if factor else []
    known = [rules.dqr_worst if score is None else score for score in scores]
    return sum(known) / len(known) if known else rules.dqr_worst


def data_quality_gap(dqr: float, rules: PriorityRules) -> float:
    """1 minus normalised quality: 0 at the best score, 1 at the worst."""
    return (dqr - rules.dqr_best) / (rules.dqr_worst - rules.dqr_best)


def rank_materials(
    lines: list[ResultLine],
    total: float,
    factors: dict[str, EmissionFactor],
    bom: list[BomLine],
    suppliers: list[Supplier],
    rules: PriorityRules,
) -> list[PriorityRow]:
    """Score each material: contribution to the PCF × how weak its current data is."""
    grouped: dict[str, list[ResultLine]] = defaultdict(list)
    for line in lines:
        if line.stage in MATERIAL_STAGES and line.impact is not None:
            grouped[line.item].append(line)

    names = {supplier.supplier_id: supplier.name for supplier in suppliers}
    bom_by_material = {line.material_number: line for line in bom}
    rows: list[PriorityRow] = []
    for material, group in grouped.items():
        impact = sum(abs(line.impact) for line in group)
        weighted = sum(
            abs(line.impact) * _line_dqr(factors.get(line.factor_id or ""), rules) for line in group
        )
        dqr = weighted / impact if impact else rules.dqr_worst
        gap = data_quality_gap(dqr, rules)
        contribution = impact / total if total else 0.0
        kinds = {factors[line.factor_id].data_type for line in group if line.factor_id in factors}
        supplier_id = bom_by_material[material].supplier_id if material in bom_by_material else None
        rows.append(
            PriorityRow(
                material_number=material,
                description=group[0].description,
                supplier_id=supplier_id,
                supplier_name=names.get(supplier_id) if supplier_id else None,
                contribution=contribution,
                data_type=PRIMARY if kinds == {PRIMARY} else SECONDARY,
                dqr=dqr,
                gap=gap,
                score=contribution**rules.contribution_weight * gap**rules.quality_weight,
                impact_on_weak_data=impact * gap,
            )
        )
    return sorted(rows, key=lambda row: row.score, reverse=True)


def recommendations(rows: list[PriorityRow], rules: PriorityRules) -> list[str]:
    """Plain-language advice for the top materials that still have weak data."""
    advice: list[str] = []
    for row in [r for r in rows if r.score > 0][: rules.recommend_top]:
        order = "first" if not advice else "next"
        kind = "supplier" if row.data_type == PRIMARY else "database"
        who = row.supplier_name or row.supplier_id
        if who:
            advice.append(
                f"Ask {who} for {row.description} data {order} — it drives "
                f"{row.contribution:.0%} of the footprint and uses {kind} data."
            )
        else:
            advice.append(
                f"Identify the supplier of {row.description} {order} — it drives "
                f"{row.contribution:.0%} of the footprint and has no supplier on the BOM."
            )
    return advice


def priority_table(rows: list[PriorityRow]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Material": row.description,
                "Supplier": row.supplier_name or row.supplier_id or "Not known",
                "Contribution": row.contribution,
                "Data type": row.data_type,
                "DQR": row.dqr,
                "Priority score": row.score,
                "Uncertainty reduced (kg CO2e per kg)": row.impact_on_weak_data,
            }
            for row in rows
        ],
        columns=[
            "Material",
            "Supplier",
            "Contribution",
            "Data type",
            "DQR",
            "Priority score",
            "Uncertainty reduced (kg CO2e per kg)",
        ],
    )


def supplier_coverage(result: PcfResult) -> float:
    """Share of the PCF that now rests on validated supplier data."""
    total = sum(abs(line.impact or 0) for line in result.lines)
    covered = sum(
        abs(line.impact or 0) for line in result.lines if line.source_id.startswith("supplier_pcf:")
    )
    return covered / total if total else 0.0
