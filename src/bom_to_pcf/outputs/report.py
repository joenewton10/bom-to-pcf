"""The methods and results report."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from bom_to_pcf.methods.uncertainty import MonteCarloResult
from bom_to_pcf.models import PcfResult, ProductConfig
from bom_to_pcf.outputs.tables import STAGE_LABELS, material_table, stage_table

TEMPLATE_NAME = "report.md.j2"


def render_report(
    result: PcfResult,
    config: ProductConfig,
    uncertainty: MonteCarloResult,
    templates_dir: Path | str,
) -> str:
    environment = Environment(
        loader=FileSystemLoader(templates_dir),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    return environment.get_template(TEMPLATE_NAME).render(
        result=result,
        config=config,
        uncertainty=uncertainty,
        stages=stage_table(result).to_dict("records"),
        materials=material_table(result).to_dict("records"),
        stage_labels=STAGE_LABELS,
    )
