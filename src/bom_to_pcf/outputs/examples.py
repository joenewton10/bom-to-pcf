"""Generate the example outputs kept in the repository, from the demo data before any review."""

import json
from datetime import UTC, datetime
from pathlib import Path

from bom_to_pcf.engine.python_engine import run_with_config
from bom_to_pcf.io.factor_store import load_factors
from bom_to_pcf.io.inputs import load_inputs
from bom_to_pcf.methods.uncertainty import monte_carlo
from bom_to_pcf.models import AnalysisConfig, EngagementConfig, MethodConfig, ProductConfig
from bom_to_pcf.outputs.dpp_sheet import render_dpp_sheet
from bom_to_pcf.outputs.pact_export import build_footprint, validation_errors
from bom_to_pcf.outputs.report import render_report
from bom_to_pcf.suppliers.requests import request_files

# Fixed, so the examples only change when the method or data do.
EXAMPLE_CREATED = datetime(2026, 1, 1, tzinfo=UTC)
EXAMPLE_SUPPLIER = "SUP-001"
PRODUCT_CONFIG = "config/product_pet_diecut.yaml"


def build_examples(root: Path | str = ".") -> dict[str, str]:
    """All the example files, by name. Raises ValueError if the PACT file breaks the schema."""
    base = Path(root)
    config = ProductConfig.from_yaml(base / PRODUCT_CONFIG)
    bundle = load_inputs(config, base / "data" / "demo")
    result = run_with_config(config, bundle, base)
    method = MethodConfig.from_yaml(base / config.method_file)
    factors, _ = load_factors(base / config.factors_file, base / config.sources_file)
    known = {factor.factor_id: factor for factor in factors}
    footprint = build_footprint(result, config, method, known, EXAMPLE_CREATED)
    errors = validation_errors(footprint, base)
    if errors:
        raise ValueError("; ".join(errors))
    analysis = AnalysisConfig.from_yaml(base / config.analysis_file)
    rules = analysis.uncertainty
    uncertainty = monte_carlo(result.lines, known, rules, rules.runs, rules.seed)
    templates = base / "templates"
    supplier = next(s for s in bundle.suppliers if s.supplier_id == EXAMPLE_SUPPLIER)
    requests = EngagementConfig.from_yaml(base / config.engagement_file).requests
    files = {
        "pact_footprint.json": json.dumps(footprint, indent=2, ensure_ascii=False) + "\n",
        "dpp_sheet.html": render_dpp_sheet(result, config, templates),
        "report.md": render_report(result, config, uncertainty, templates),
    }
    files |= request_files(supplier, bundle.bom, config, requests, templates)
    return files


def write_examples(root: Path | str = ".") -> list[str]:
    folder = Path(root) / "outputs" / "examples"
    folder.mkdir(parents=True, exist_ok=True)
    files = build_examples(root)
    for name, content in files.items():
        (folder / name).write_text(content, encoding="utf-8", newline="\n")
    return sorted(files)
