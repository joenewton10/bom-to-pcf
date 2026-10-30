"""Minimal command line interface for testing and batch runs."""

import typer

from bom_to_pcf import __version__

app = typer.Typer(help="Calculate product carbon footprints from a bill of materials.")


@app.callback()
def main() -> None:
    """Keep subcommands explicit while only one command exists."""


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)
