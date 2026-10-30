"""Minimal command line interface for testing and batch runs."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from bom_to_pcf import __version__
from bom_to_pcf.io.inputs import load_inputs
from bom_to_pcf.models import ProductConfig, issues_table

app = typer.Typer(help="Calculate product carbon footprints from a bill of materials.")


@app.callback()
def main() -> None:
    """Keep subcommands explicit."""


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)


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
