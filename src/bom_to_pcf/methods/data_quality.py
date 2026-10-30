"""Aggregate data quality ratings across a result."""

from bom_to_pcf.models import DqrScore, EmissionFactor, ResultLine


def aggregate_dqr(lines: list[ResultLine], factors: dict[str, EmissionFactor]) -> DqrScore:
    """Average each DQR dimension, weighted by the size of each line's impact."""

    def weighted(attribute: str) -> float | None:
        total = weight_sum = 0.0
        for line in lines:
            factor = factors.get(line.factor_id or "")
            score = getattr(factor, attribute) if factor else None
            if score is not None and line.impact:
                total += score * abs(line.impact)
                weight_sum += abs(line.impact)
        return total / weight_sum if weight_sum else None

    technological = weighted("dqr_tech")
    geographical = weighted("dqr_geo")
    temporal = weighted("dqr_time")
    scores = [s for s in (technological, geographical, temporal) if s is not None]
    return DqrScore(
        technological=technological,
        geographical=geographical,
        temporal=temporal,
        overall=sum(scores) / len(scores) if scores else None,
    )
