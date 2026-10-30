"""Allocation choices: site overheads and production scrap sent to recycling."""

from bom_to_pcf.models import AllocationRules, LciLine, RoutingStep, StepMass

STAGE_SCRAP = "scrap_treatment"


def overhead_kwh_per_kg(
    overhead: RoutingStep,
    routing: list[RoutingStep],
    masses: list[StepMass],
    rules: AllocationRules,
) -> float:
    """Site overhead electricity per kg of finished product.

    By mass, the site's load is shared over its output. By machine hours, each machine carries
    an equal share of the load for as long as this product occupies it.
    """
    if rules.overhead_method == "mass":
        return overhead.kwh_per_kg
    throughput = {step.step_id: step.throughput_kg_per_h for step in routing}
    machine_hours = sum(mass.input_kg / throughput[mass.step_id] for mass in masses)
    site_kw = overhead.power_kw * overhead.utilisation
    return site_kw / rules.overhead_machine_count * machine_hours


def recycling_lines(step: StepMass, rules: AllocationRules) -> list[LciLine]:
    """Inventory lines for scrap sent to recycling, under the configured approach."""
    base = {
        "stage": STAGE_SCRAP,
        "item": f"scrap_{step.step_id}",
        "unit": "kg",
        "mass_kg": step.scrap_kg,
    }
    if rules.scrap_recycling == "cut_off":
        return [
            LciLine(
                **base,
                description=f"Scrap from {step.step_id} to recycling",
                quantity=step.scrap_kg,
                note="Cut-off: no burden and no credit.",
            )
        ]
    return [
        LciLine(
            **base,
            description=f"Recycling scrap from {step.step_id}",
            quantity=step.scrap_kg,
            factor_id=rules.substitution.burden_factor,
            note="Substitution: burden of the recycled material.",
        ),
        LciLine(
            **base,
            description=f"Virgin material avoided by scrap from {step.step_id}",
            quantity=-step.scrap_kg,
            factor_id=rules.substitution.avoided_factor,
            note="Substitution: credit for avoided virgin material.",
        ),
    ]
