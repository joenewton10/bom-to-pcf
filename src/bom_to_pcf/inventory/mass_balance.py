"""Check that product material inputs equal finished product plus process scrap."""

from bom_to_pcf.models import BomLine, MassBalance, ProductConfig, RoutingStep, StepMass


def step_masses(routing: list[RoutingStep], overhead_step_id: str) -> list[StepMass]:
    """Work back from 1 kg of finished product to the mass entering each step."""
    masses: list[StepMass] = []
    output_kg = 1.0
    for step in reversed([s for s in routing if s.step_id != overhead_step_id]):
        input_kg = output_kg / (1 - step.scrap_rate)
        masses.append(
            StepMass(
                step_id=step.step_id,
                input_kg=input_kg,
                scrap_kg=input_kg * step.scrap_rate,
                scrap_destination=step.scrap_destination,
            )
        )
        output_kg = input_kg
    return list(reversed(masses))


def check_mass_balance(
    bom: list[BomLine],
    routing: list[RoutingStep],
    config: ProductConfig,
    overhead_step_id: str,
    tolerance_share: float,
) -> MassBalance:
    """Compare BOM product material with what the routing needs. Packaging is left out."""
    steps = step_masses(routing, overhead_step_id)
    inputs_kg = sum(
        line.qty_kg_per_kg_product
        for line in bom
        if config.role_of(line.material_number) == "product"
    )
    scrap_kg = sum(step.scrap_kg for step in steps)
    product_kg = 1.0
    imbalance_kg = inputs_kg - product_kg - scrap_kg
    imbalance_share = abs(imbalance_kg) / inputs_kg if inputs_kg else 1.0
    return MassBalance(
        inputs_kg=inputs_kg,
        product_kg=product_kg,
        scrap_kg=scrap_kg,
        imbalance_kg=imbalance_kg,
        imbalance_share=imbalance_share,
        tolerance_share=tolerance_share,
        passed=imbalance_share <= tolerance_share,
        steps=steps,
    )
