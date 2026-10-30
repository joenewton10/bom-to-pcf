"""Monte Carlo uncertainty on the footprint."""

import numpy as np
from pydantic import BaseModel, ConfigDict

from bom_to_pcf.models import EmissionFactor, ResultLine, UncertaintyRules

P5, P50, P95 = 5, 50, 95


class MonteCarloResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    deterministic: float
    mean: float
    p5: float
    p50: float
    p95: float
    runs: int
    seed: int | None
    samples: np.ndarray


def relative_sd(factor: EmissionFactor | None, rules: UncertaintyRules) -> float:
    """A factor's assumed spread, from its mean quality score. Unknown scores count as the worst."""
    table = sorted(rules.relative_sd_by_dqr.items())
    scores = [factor.dqr_tech, factor.dqr_geo, factor.dqr_time] if factor else []
    known = [score for score in scores if score is not None]
    dqr = sum(known) / len(known) if len(known) == len(scores) and known else table[-1][0]
    return float(np.interp(dqr, [t[0] for t in table], [t[1] for t in table]))


def _lognormal(generator: np.random.Generator, cv: float, size) -> np.ndarray:
    """Multipliers with a mean of 1 and the given coefficient of variation."""
    sigma_squared = np.log(1 + cv**2)
    return generator.lognormal(-sigma_squared / 2, np.sqrt(sigma_squared), size)


def monte_carlo(
    lines: list[ResultLine],
    factors: dict[str, EmissionFactor],
    rules: UncertaintyRules,
    runs: int,
    seed: int | None,
) -> MonteCarloResult:
    """Sample the footprint. Lines sharing a factor share its draw, because the error is common."""
    generator = np.random.default_rng(seed)
    known = [line for line in lines if line.impact]
    draws: dict[str, np.ndarray] = {}
    total = np.zeros(runs)
    for line in known:
        key = line.factor_id or ""
        if key not in draws:
            draws[key] = _lognormal(generator, relative_sd(factors.get(key), rules), runs)
        activity = _lognormal(generator, rules.activity_relative_sd, runs)
        total += line.impact * draws[key] * activity
    return MonteCarloResult(
        deterministic=sum(line.impact for line in known),
        mean=float(total.mean()),
        p5=float(np.percentile(total, P5)),
        p50=float(np.percentile(total, P50)),
        p95=float(np.percentile(total, P95)),
        runs=runs,
        seed=seed,
        samples=total,
    )
