"""Apply the cut-off rule and report what it leaves out."""

from collections import defaultdict

from bom_to_pcf.models import CutOffRules, ResultLine


def apply_cut_off(
    lines: list[ResultLine], rules: CutOffRules
) -> tuple[list[ResultLine], list[ResultLine]]:
    """Split lines into kept and excluded, smallest items first, within the total limit.

    An item with a placeholder is never excluded, because its impact is unknown. Scrap and
    transport are grouped by item, so a flow is never split across the rule.
    """
    groups: dict[str, list[ResultLine]] = defaultdict(list)
    for line in lines:
        groups[line.item].append(line)

    total_impact = sum(abs(line.impact or 0) for line in lines)
    # A material with several factors has several lines, but its mass counts once.
    total_mass = sum(
        max(line.mass_kg or 0 for line in group)
        for group in groups.values()
        if group[0].stage != "scrap_treatment"
    )
    if total_impact == 0:
        return lines, []

    candidates: list[tuple[float, str]] = []
    for item, group in groups.items():
        if any(line.impact is None or line.factor_id is None for line in group):
            continue
        impact_share = sum(abs(line.impact) for line in group) / total_impact
        mass = max((line.mass_kg or 0) for line in group)
        is_scrap = group[0].stage == "scrap_treatment"
        mass_share = 0.0 if is_scrap or not total_mass else mass / total_mass
        if impact_share < rules.flow_share and mass_share < rules.flow_share:
            candidates.append((impact_share, item))

    excluded_items: set[str] = set()
    excluded_share = 0.0
    for impact_share, item in sorted(candidates):
        if excluded_share + impact_share > rules.total_share:
            break
        excluded_items.add(item)
        excluded_share += impact_share

    kept = [line for line in lines if line.item not in excluded_items]
    excluded = [line for line in lines if line.item in excluded_items]
    return kept, excluded
