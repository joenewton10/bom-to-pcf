"""What-if scenarios: one set of levers, used by scenario files and the sensitivity sliders."""

from pathlib import Path

import pandas as pd
import yaml
from pydantic import BaseModel, Field

from bom_to_pcf.engine.python_engine import run_pcf
from bom_to_pcf.inventory.mass_balance import step_masses
from bom_to_pcf.io.inputs import InputBundle
from bom_to_pcf.models import (
    AnalysisConfig,
    EmissionFactor,
    Mapping,
    MethodConfig,
    PcfResult,
    ProductConfig,
)

BASELINE_FILE = "baseline.yaml"
DQR_FIELDS = ("dqr_tech", "dqr_geo", "dqr_time")


class Scenario(BaseModel):
    """Changes to apply. The defaults change nothing."""

    name: str
    description: str = ""
    renewable_share: float = Field(default=0.0, ge=0, le=1)
    recycled_share: float = Field(default=0.0, ge=0, le=1)
    scrap_multiplier: float = Field(default=1.0, gt=0)


def load_scenarios(folder: Path | str) -> list[Scenario]:
    """Read every scenario file, with the baseline first."""
    paths = sorted(Path(folder).glob("*.yaml"), key=lambda p: (p.name != BASELINE_FILE, p.name))
    return [Scenario.model_validate(yaml.safe_load(p.read_text(encoding="utf-8"))) for p in paths]


def blended_factor(
    factor_id: str, first: EmissionFactor, second: EmissionFactor, share_second: float
) -> EmissionFactor:
    """A mix of two factors. Value and quality scores are weighted by share."""

    def mix(a: float | None, b: float | None) -> float | None:
        return None if a is None or b is None else a * (1 - share_second) + b * share_second

    return EmissionFactor(
        factor_id=factor_id,
        name=f"{first.name} / {second.name}, {share_second:.0%} second",
        value=mix(first.value, second.value),
        unit=first.unit,
        source_id=f"{first.source_id}+{second.source_id}",
        data_type="secondary",
        **{field: mix(getattr(first, field), getattr(second, field)) for field in DQR_FIELDS},
        notes="Scenario blend.",
        status="ACTIVE" if mix(first.value, second.value) is not None else "PLACEHOLDER",
    )


def _required_input(routing, overhead_step_id: str) -> float:
    masses = step_masses(routing, overhead_step_id)
    return masses[0].input_kg if masses else 1.0


def _apply_scrap(
    bundle: InputBundle, config: ProductConfig, method: MethodConfig, multiplier: float
) -> InputBundle:
    """Raise scrap rates, and product material by the same ratio so the mass balances."""
    overhead = method.allocation.overhead_step_id
    before = _required_input(bundle.routing, overhead)
    routing = []
    for step in bundle.routing:
        rate = step.scrap_rate * multiplier
        if rate >= 1:
            raise ValueError(f"step {step.step_id} would scrap all of its material")
        routing.append(step.model_copy(update={"scrap_rate": rate}))
    ratio = _required_input(routing, overhead) / before
    bom = [
        line.model_copy(
            update={
                "qty_kg": line.qty_kg * ratio,
                "component_qty": line.component_qty * ratio,
                "qty_kg_per_kg_product": line.qty_kg_per_kg_product * ratio,
            }
        )
        if config.role_of(line.material_number) == "product"
        else line
        for line in bundle.bom
    ]
    return bundle.model_copy(update={"routing": routing, "bom": bom})


def run_scenario(
    bundle: InputBundle,
    config: ProductConfig,
    method: MethodConfig,
    factors: list[EmissionFactor],
    mappings: list[Mapping],
    scenario: Scenario,
    analysis: AnalysisConfig,
) -> PcfResult:
    """Calculate a footprint with a scenario's changes. The inputs are left untouched."""
    levers = analysis.levers
    by_id = {factor.factor_id: factor for factor in factors}
    run_factors = list(factors)
    run_mappings = mappings
    run_method = method

    if scenario.renewable_share:
        blend = blended_factor(
            "SCENARIO_ELECTRICITY",
            by_id[levers.electricity_grid],
            by_id[levers.electricity_renewable],
            scenario.renewable_share,
        )
        run_factors.append(blend)
        choices = method.factors.model_copy(update={"electricity": [blend.factor_id]})
        run_method = method.model_copy(update={"factors": choices})

    if scenario.recycled_share:
        blend = blended_factor(
            "SCENARIO_RESIN",
            by_id[levers.resin_virgin],
            by_id[levers.resin_recycled],
            scenario.recycled_share,
        )
        run_factors.append(blend)
        run_mappings = [
            m.model_copy(update={"factor_id": blend.factor_id})
            if m.factor_id == levers.resin_virgin
            else m
            for m in mappings
        ]

    run_bundle = bundle
    if scenario.scrap_multiplier != 1:
        run_bundle = _apply_scrap(bundle, config, method, scenario.scrap_multiplier)
    return run_pcf(run_bundle, config, run_method, run_factors, run_mappings)


def scenario_table(results: list[tuple[Scenario, PcfResult]]) -> pd.DataFrame:
    """Scenarios side by side, each compared with the first."""
    base = results[0][1].kg_co2e_per_kg if results else 0.0
    return pd.DataFrame(
        [
            {
                "Scenario": scenario.name,
                "kg CO2e per kg": result.kg_co2e_per_kg,
                "kg CO2e per 1,000 parts": result.kg_co2e_per_1000_pieces,
                "Change": (result.kg_co2e_per_kg - base) / base if base else 0.0,
                "Data quality": result.dqr.overall,
                "What it assumes": scenario.description,
            }
            for scenario, result in results
        ]
    )
