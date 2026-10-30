"""Write each command line run to its own folder, so any result can be traced and re-exported."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from bom_to_pcf.io.inputs import InputBundle
from bom_to_pcf.models import PcfResult, ProductConfig, issues_table

MANIFEST = "manifest.json"
RESULT = "result.json"
SNAPSHOT = "input_snapshot.json"
ISSUES = "issues.csv"


def config_hash(config: ProductConfig, root: Path | str = ".") -> str:
    """A fingerprint of everything that shapes a result besides the inputs."""
    base = Path(root)
    digest = hashlib.sha256(config.model_dump_json().encode())
    for name in (
        config.method_file,
        config.factors_file,
        config.sources_file,
        config.mappings_file,
    ):
        digest.update((base / name).read_bytes())
    return digest.hexdigest()


def write_run(
    result: PcfResult,
    bundle: InputBundle,
    config: ProductConfig,
    product_path: Path | str,
    scenario: str | None,
    outputs_dir: Path | str,
) -> str:
    """Save a run and return its ID."""
    now = datetime.now(UTC)
    fingerprint = config_hash(config)
    run_id = f"{now.strftime('%Y%m%dT%H%M%S%f')}-{fingerprint[:8]}"
    folder = Path(outputs_dir) / run_id
    folder.mkdir(parents=True)
    manifest = {
        "run_id": run_id,
        "created": now.isoformat(timespec="seconds"),
        "product": str(product_path),
        "scenario": scenario,
        "config_hash": fingerprint,
        "status": result.status_label,
    }
    (folder / MANIFEST).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (folder / RESULT).write_text(result.model_dump_json(indent=2), encoding="utf-8")
    (folder / SNAPSHOT).write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    (folder / ISSUES).write_text(issues_table(bundle.issues).to_csv(index=False), encoding="utf-8")
    return run_id


def read_run(run_id: str, outputs_dir: Path | str) -> tuple[dict, PcfResult]:
    """Read a saved run. Raises ValueError if it does not exist."""
    folder = Path(outputs_dir) / run_id
    if not (folder / MANIFEST).is_file():
        raise ValueError(f"no run {run_id} in {outputs_dir}")
    manifest = json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
    return manifest, PcfResult.model_validate_json((folder / RESULT).read_text(encoding="utf-8"))
