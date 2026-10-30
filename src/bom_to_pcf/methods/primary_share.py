"""Share of the footprint based on primary data from suppliers or the site."""

from bom_to_pcf.models import EmissionFactor, ResultLine


def primary_data_share(
    lines: list[ResultLine], factors: dict[str, EmissionFactor], site_stages: list[str]
) -> float:
    """Return the primary share of known impact, from 0 to 1.

    A line counts as primary if its factor is supplier data or its quantity comes from the site.
    """
    total = primary = 0.0
    for line in lines:
        if not line.impact:
            continue
        factor = factors.get(line.factor_id or "")
        total += abs(line.impact)
        if line.stage in site_stages or (factor is not None and factor.data_type == "primary"):
            primary += abs(line.impact)
    return primary / total if total else 0.0
