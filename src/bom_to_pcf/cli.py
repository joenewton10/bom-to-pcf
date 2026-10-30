"""Minimal command line interface for testing and batch runs."""

from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.console import Console
from rich.table import Table

from bom_to_pcf import __version__
from bom_to_pcf.engine.python_engine import run_with_config
from bom_to_pcf.io.factor_store import load_factors, read_mappings
from bom_to_pcf.io.inputs import load_inputs
from bom_to_pcf.models import AnalysisConfig, MethodConfig, ProductConfig, issues_table
from bom_to_pcf.scenarios import Scenario, run_scenario
from bom_to_pcf.variants import FamilyConfig, family_table, run_family

app = typer.Typer(help="Calculate product carbon footprints from a bill of materials.")


@app.callback()
def main() -> None:
    """Keep subcommands explicit."""


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)


@app.command()
def run(
    product: Annotated[Path, typer.Option(help="Product config YAML.")],
    scenario: Annotated[str | None, typer.Option(help="Scenario file name, no extension.")] = None,
) -> None:
    """Calculate the footprint and print it with its status and data gaps."""
    config = ProductConfig.from_yaml(product)
    bundle = load_inputs(config)
    if scenario is None:
        result = run_with_config(config, bundle)
    else:
        chosen = Scenario.model_validate(
            yaml.safe_load((Path(config.scenarios_dir) / f"{scenario}.yaml").read_text("utf-8"))
        )
        method = MethodConfig.from_yaml(config.method_file)
        factors, _ = load_factors(config.factors_file, config.sources_file)
        mappings, _ = read_mappings(config.mappings_file)
        analysis = AnalysisConfig.from_yaml(config.analysis_file)
        result = run_scenario(bundle, config, method, factors, mappings, chosen, analysis)
    console = Console(width=140)
    console.print(result.status_label, markup=False)
    console.print(f"{result.kg_co2e_per_kg:.3f} kg CO2e per kg", markup=False)
    console.print(f"{result.kg_co2e_per_1000_pieces:.3f} kg CO2e per 1,000 pieces", markup=False)
    console.print(f"Primary data share: {result.primary_data_share:.1%}", markup=False)
    if result.dqr.overall is not None:
        console.print(f"DQR (1 best, 5 worst): {result.dqr.overall:.2f}", markup=False)
    for stage, impact in result.by_stage.items():
        console.print(f"  {stage}: {impact:.3f}", markup=False)
    for text in [*result.missing, *result.draft_reasons]:
        console.print(f"- {text}", markup=False)
    for text in result.known_omissions:
        console.print(f"- Not modelled: {text}", markup=False)
    console.print(
        f"Left out by cut-off ({result.excluded_share:.1%} of known impact): "
        f"{sorted({x.item for x in result.excluded})}",
        markup=False,
    )


@app.command()
def variants(config: Annotated[Path, typer.Option(help="Product family YAML.")]) -> None:
    """Calculate every variant in a product family and print the results as CSV."""
    family = FamilyConfig.from_yaml(config)
    product = ProductConfig.from_yaml(family.product)
    method = MethodConfig.from_yaml(product.method_file)
    factors, _ = load_factors(product.factors_file, product.sources_file)
    mappings, _ = read_mappings(product.mappings_file)
    analysis = AnalysisConfig.from_yaml(product.analysis_file)
    results = run_family(load_inputs(product), product, method, factors, mappings, family, analysis)
    typer.echo(family_table(results).to_csv(index=False).strip())


@app.command("validate-inputs")
def validate_inputs(
    product: Annotated[Path, typer.Option(help="Product config YAML.")],
    input_dir: Annotated[Path | None, typer.Option(help="Overrides the config's folder.")] = None,
) -> None:
    """Check an input set and print its issues. Exits with 1 if there are errors."""
    bundle = load_inputs(ProductConfig.from_yaml(product), input_dir)
    table = Table(title=f"{len(bundle.bom)} BOM lines, {len(bundle.issues)} issues")
    frame = issues_table(bundle.issues).astype(object).fillna("")
    for column in frame.columns:
        table.add_column(column)
    for row in frame.itertuples(index=False):
        table.add_row(*(str(value) for value in row))
    Console(width=140).print(table)
    if bundle.has_errors:
        raise typer.Exit(code=1)
