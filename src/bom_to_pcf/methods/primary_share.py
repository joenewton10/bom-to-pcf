"""Share of the footprint based on primary data from suppliers or the site."""

from bom_to_pcf.models import EmissionFactor, ResultLine


def primary_data_share(
    lines: list[ResultLine], factors: dict[str, EmissionFactor], site_stages: list[str]
) -> float:
    """Return the primary share of known impact, from 0 to 1.

    Quantities from the site count in full. A supplier PCF counts by the primary share the
    supplier states, and not at all if it states none. A PCF is not all primary just because a
    supplier sent it, since it is usually built partly from database values.
    """
    total = primary = 0.0
    for line in lines:
        if not line.impact:
            continue
        impact = abs(line.impact)
        total += impact
        factor = factors.get(line.factor_id or "")
        if line.stage in site_stages:
            primary += impact
        elif factor is not None and factor.data_type == "primary":
            primary += impact * (factor.primary_data_share or 0.0)
    return primary / total if total else 0.0


def unknown_primary_share(lines: list[ResultLine], factors: dict[str, EmissionFactor]) -> float:
    """Share of known impact from supplier PCFs that do not state a primary share."""
    total = unknown = 0.0
    for line in lines:
        if not line.impact:
            continue
        total += abs(line.impact)
        factor = factors.get(line.factor_id or "")
        if factor and factor.data_type == "primary" and factor.primary_data_share is None:
            unknown += abs(line.impact)
    return unknown / total if total else 0.0
