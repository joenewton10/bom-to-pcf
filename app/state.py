"""Session state keys, progress checklist and calls into the engine."""

from collections.abc import Mapping
from pathlib import Path

import streamlit as st

from bom_to_pcf.engine.python_engine import run_with_config
from bom_to_pcf.io.inputs import InputBundle, bundle_from_files, load_inputs
from bom_to_pcf.models import PcfResult, ProductConfig

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_CONFIG = ROOT / "config" / "product_pet_diecut.yaml"
DEMO_DIR = ROOT / "data" / "demo"

BUNDLE = "bundle"
DATA_SOURCE = "data_source"
PROGRESS = "progress"

UPLOADED = "Data uploaded"
VALIDATED = "Inputs validated"
REVIEWED = "Matches reviewed"
CALCULATED = "PCF calculated"
HOTSPOTS = "Hotspots checked"
PRIMARY = "Primary data added"
EXPORTED = "Exported"
CHECKLIST = [UPLOADED, VALIDATED, REVIEWED, CALCULATED, HOTSPOTS, PRIMARY, EXPORTED]


def mark_done(step: str) -> None:
    st.session_state.setdefault(PROGRESS, set()).add(step)


def is_done(step: str) -> bool:
    return step in st.session_state.get(PROGRESS, set())


def get_config() -> ProductConfig:
    return ProductConfig.from_yaml(PRODUCT_CONFIG)


def get_bundle() -> InputBundle | None:
    return st.session_state.get(BUNDLE)


def _store(bundle: InputBundle, source: str) -> None:
    st.session_state[BUNDLE] = bundle
    st.session_state[DATA_SOURCE] = source
    st.session_state[PROGRESS] = {UPLOADED}
    if not bundle.has_errors:
        mark_done(VALIDATED)


def load_demo() -> None:
    _store(load_inputs(get_config(), DEMO_DIR), "demo")


def load_uploads(files: Mapping[str, bytes]) -> None:
    _store(bundle_from_files(get_config(), files), "upload")


@st.cache_data(show_spinner=False)
def _calculate(input_hash: str, _bundle: InputBundle) -> PcfResult:
    return run_with_config(get_config(), _bundle, ROOT)


def get_result() -> PcfResult | None:
    """The result for the current inputs, recalculated whenever they change."""
    bundle = get_bundle()
    if bundle is None:
        return None
    result = _calculate(bundle.model_dump_json(), bundle)
    mark_done(CALCULATED)
    return result
