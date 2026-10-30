"""Share of the footprint based on primary data (PACT 3.0, 4.2.2; TfS 3.0, 5.2.11.1)."""

from bom_to_pcf.models import EmissionFactor, ResultLine


def primary_data_share(lines: list[ResultLine], factors: dict[str, EmissionFactor]) -> float:
    """Return the primary share of the absolute footprint, from 0 to 1.

    An input is primary only if both its activity data and emission factor are, so a site's own
    kWh multiplied by a database factor scores 0%. A supplier PCF counts by the share the supplier
    states, and an unknown share scores 0%.
    """
    total = primary = 0.0
    for line in lines:
        if not line.impact:
            continue
        impact = abs(line.impact)
        total += impact
        factor = factors.get(line.factor_id or "")
        if factor is not None and factor.data_type == "primary":
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
