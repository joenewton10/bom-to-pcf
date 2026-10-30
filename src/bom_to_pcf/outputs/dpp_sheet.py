"""A Digital Product Passport-style data sheet. Not an ESPR-compliant passport."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from bom_to_pcf.models import PcfResult, ProductConfig
from bom_to_pcf.outputs.tables import material_table, stage_table

TEMPLATE_NAME = "dpp_sheet.html.j2"


def render_dpp_sheet(result: PcfResult, config: ProductConfig, templates_dir: Path | str) -> str:
    environment = Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=select_autoescape(["html", "j2"]),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    return environment.get_template(TEMPLATE_NAME).render(
        result=result,
        config=config,
        stages=stage_table(result).to_dict("records"),
        materials=material_table(result).to_dict("records"),
    )
