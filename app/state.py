"""Session state keys, progress checklist and calls into the engine."""

from collections.abc import Mapping as MappingType
from pathlib import Path

import streamlit as st

from bom_to_pcf.engine.python_engine import run_with_config
from bom_to_pcf.io.inputs import InputBundle, bundle_from_files, load_inputs
from bom_to_pcf.matching.fuzzy_matcher import load_candidates
from bom_to_pcf.matching.review import build_review, mappings_from_review, review_complete
from bom_to_pcf.models import (
    Candidate,
    Mapping,
    MatchingConfig,
    PcfResult,
    ProductConfig,
    ReviewItem,
    ReviewLogEntry,
)

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_CONFIG = ROOT / "config" / "product_pet_diecut.yaml"
DEMO_DIR = ROOT / "data" / "demo"

BUNDLE = "bundle"
DATA_SOURCE = "data_source"
PROGRESS = "progress"
REVIEW = "review_items"
REVIEW_LOG = "review_log"
REVIEW_VERSION = "review_version"
LLM_CALLS = "llm_calls"

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


def get_matching_config() -> MatchingConfig:
    return MatchingConfig.from_yaml(ROOT / get_config().matching_file)


def get_candidates() -> list[Candidate]:
    return load_candidates(ROOT / get_config().candidates_file)


def get_bundle() -> InputBundle | None:
    return st.session_state.get(BUNDLE)


def get_review() -> list[ReviewItem]:
    return st.session_state.get(REVIEW, [])


def get_review_log() -> list[ReviewLogEntry]:
    return st.session_state.setdefault(REVIEW_LOG, [])


def _store(bundle: InputBundle, source: str) -> None:
    st.session_state[BUNDLE] = bundle
    st.session_state[DATA_SOURCE] = source
    st.session_state[PROGRESS] = {UPLOADED}
    st.session_state[REVIEW] = build_review(
        bundle.bom, get_candidates(), get_matching_config().top_n
    )
    st.session_state[REVIEW_LOG] = []
    st.session_state[REVIEW_VERSION] = st.session_state.get(REVIEW_VERSION, 0) + 1
    if not bundle.has_errors:
        mark_done(VALIDATED)


def load_demo() -> None:
    _store(load_inputs(get_config(), DEMO_DIR), "demo")


def load_uploads(files: MappingType[str, bytes]) -> None:
    _store(bundle_from_files(get_config(), files), "upload")


@st.cache_data(show_spinner=False)
def _calculate(input_hash: str, _bundle: InputBundle, _mappings: list[Mapping]) -> PcfResult:
    return run_with_config(get_config(), _bundle, ROOT, _mappings)


def get_result() -> PcfResult | None:
    """The result for the current inputs and matches, recalculated whenever they change."""
    bundle = get_bundle()
    if bundle is None:
        return None
    mappings = mappings_from_review(get_review(), get_candidates())
    key = bundle.model_dump_json() + "".join(m.model_dump_json() for m in mappings)
    result = _calculate(key, bundle, mappings)
    mark_done(CALCULATED)
    if review_complete(get_review()):
        mark_done(REVIEWED)
    else:
        st.session_state[PROGRESS].discard(REVIEWED)
    return result
