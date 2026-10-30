"""Session state keys, progress checklist and calls into the engine."""

import os
from collections.abc import Mapping as MappingType
from datetime import date
from pathlib import Path

import streamlit as st

from bom_to_pcf.engine.python_engine import run_with_config
from bom_to_pcf.inventory.lci_builder import supplier_factor
from bom_to_pcf.io.factor_store import load_factors
from bom_to_pcf.io.inputs import InputBundle, bundle_from_files, load_inputs
from bom_to_pcf.matching.fuzzy_matcher import load_candidates
from bom_to_pcf.matching.review import build_review, mappings_from_review, review_complete
from bom_to_pcf.models import (
    AnalysisConfig,
    Candidate,
    EmissionFactor,
    EngagementConfig,
    Mapping,
    MatchingConfig,
    MethodConfig,
    PcfResult,
    PriorityRow,
    PriorityRules,
    ProductConfig,
    ProjectState,
    ReviewItem,
    ReviewLogEntry,
    SupplierPcf,
)
from bom_to_pcf.primary_data.replacement import (
    FILE_IMPORT_USER,
    already_seen,
    apply_primary,
    record_submission,
)
from bom_to_pcf.primary_data.validation import check_submission, secondary_per_kg
from bom_to_pcf.storage.base import SQLITE, STORAGE_VARIABLE, StorageBackend, choose_backend
from bom_to_pcf.storage.session_store import SessionStore
from bom_to_pcf.storage.sqlite_store import SQLiteStore
from bom_to_pcf.suppliers.priority import rank_materials
from bom_to_pcf.suppliers.requests import on_revert, on_submission
from bom_to_pcf.variants import FamilyConfig

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_CONFIG = ROOT / "config" / "product_pet_diecut.yaml"
DEMO_DIR = ROOT / "data" / "demo"
SQLITE_PATH = ROOT / "data" / "app.db"
SCENARIOS_DIR = ROOT / "config" / "scenarios"
FAMILY_CONFIG = ROOT / "config" / "variants_pet_family.yaml"

BUNDLE = "bundle"
DATA_SOURCE = "data_source"
PROGRESS = "progress"
PROJECT = "project_state"
REVIEW_VERSION = "review_version"
LLM_CALLS = "llm_calls"
LAST_BEFORE = "result_before_last_change"

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


def get_method() -> MethodConfig:
    return MethodConfig.from_yaml(ROOT / get_config().method_file)


def get_factors() -> list[EmissionFactor]:
    config = get_config()
    return load_factors(ROOT / config.factors_file, ROOT / config.sources_file)[0]


def get_matching_config() -> MatchingConfig:
    return MatchingConfig.from_yaml(ROOT / get_config().matching_file)


def get_engagement() -> EngagementConfig:
    return EngagementConfig.from_yaml(ROOT / get_config().engagement_file)


def get_analysis() -> AnalysisConfig:
    return AnalysisConfig.from_yaml(ROOT / get_config().analysis_file)


def get_family() -> FamilyConfig:
    return FamilyConfig.from_yaml(FAMILY_CONFIG)


def get_effective_bundle() -> InputBundle:
    """The inputs with accepted supplier data applied."""
    return apply_primary(get_bundle(), get_project())


def known_factors() -> dict[str, EmissionFactor]:
    """Every factor in the current result, including those from supplier data."""
    known = {factor.factor_id: factor for factor in get_factors()}
    known |= {
        factor.factor_id: factor
        for factor in (supplier_factor(pcf) for pcf in get_effective_bundle().supplier_pcfs)
    }
    return known


def templates_dir() -> Path:
    return ROOT / "templates"


def get_priorities() -> tuple[list[PriorityRow], PriorityRules]:
    """The supplier ranking for the current result, with the rules that produced it."""
    bundle = get_bundle()
    result = get_result()
    rules = get_engagement().priority
    rows = rank_materials(
        result.lines, result.kg_co2e_per_kg, known_factors(), bundle.bom, bundle.suppliers, rules
    )
    return rows, rules


def get_candidates() -> list[Candidate]:
    return load_candidates(ROOT / get_config().candidates_file)


def get_bundle() -> InputBundle | None:
    return st.session_state.get(BUNDLE)


def backend_name() -> str:
    host = None
    if not os.environ.get(STORAGE_VARIABLE):
        host = st.context.headers.get("host")
    return choose_backend(os.environ.get(STORAGE_VARIABLE), host)


def get_store() -> StorageBackend:
    if backend_name() == SQLITE:
        return SQLiteStore(SQLITE_PATH)
    return SessionStore(st.session_state)


def get_project() -> ProjectState:
    """The working state, read from storage the first time it is needed in a session."""
    if PROJECT not in st.session_state:
        st.session_state[PROJECT] = get_store().load()
    return st.session_state[PROJECT]


def refresh_project() -> None:
    """Forget the working copy, so the next read sees what any other tab has saved."""
    st.session_state.pop(PROJECT, None)


def start_fresh() -> None:
    """Begin again with no data, review decisions or supplier data."""
    get_store().start_fresh()
    for key in (PROJECT, BUNDLE, DATA_SOURCE, PROGRESS, LAST_BEFORE):
        st.session_state.pop(key, None)


def note_revert(material: str) -> None:
    on_revert(get_project(), material, date.today())


def set_project(state: ProjectState) -> None:
    """Replace the state, saving first so that a refused save changes nothing."""
    get_store().save(state)
    st.session_state[PROJECT] = state


def save_project() -> None:
    get_store().save(get_project())


def get_review() -> list[ReviewItem]:
    """Review items, rebuilt if they do not fit the loaded BOM (new data, or another tab reset)."""
    project = get_project()
    bundle = get_bundle()
    if bundle is not None:
        materials = [line.material_number for line in bundle.bom]
        if [item.material_number for item in project.review_items] != materials:
            project.review_items = build_review(
                bundle.bom, get_candidates(), get_matching_config().top_n
            )
            save_project()
    return project.review_items


def get_review_log() -> list[ReviewLogEntry]:
    return get_project().review_log


def current_mappings() -> list[Mapping]:
    return mappings_from_review(get_review(), get_candidates())


def submit_pcf(pcf: SupplierPcf, user: str, comment: str = ""):
    """Check a supplier PCF and record the outcome. Returns the check."""
    config = get_config()
    secondary = secondary_per_kg(pcf.material_number, current_mappings(), get_factors(), config)
    check = check_submission(
        pcf, config, get_method().primary_data, get_bundle().bom, secondary, comment
    )
    project = get_project()
    record_submission(project, pcf, check, user, comment)
    on_submission(project, pcf, check.accepted, get_bundle().bom, date.today())
    save_project()
    return check


def _store(bundle: InputBundle, source: str) -> None:
    st.session_state[BUNDLE] = bundle
    st.session_state[DATA_SOURCE] = source
    st.session_state[PROGRESS] = {UPLOADED}
    project = get_project()
    get_review()
    st.session_state[REVIEW_VERSION] = st.session_state.get(REVIEW_VERSION, 0) + 1
    save_project()
    for pcf in bundle.supplier_pcfs:
        if pcf.usable and not already_seen(project, pcf):
            submit_pcf(pcf, FILE_IMPORT_USER)
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
    """The result for the current inputs, matches and primary data, recalculated on any change."""
    bundle = get_bundle()
    if bundle is None:
        return None
    project = get_project()
    effective = apply_primary(bundle, project)
    mappings = current_mappings()
    key = effective.model_dump_json() + "".join(m.model_dump_json() for m in mappings)
    result = _calculate(key, effective, mappings)
    mark_done(CALCULATED)
    progress = st.session_state[PROGRESS]
    if review_complete(get_review()):
        progress.add(REVIEWED)
    else:
        progress.discard(REVIEWED)
    if project.active:
        progress.add(PRIMARY)
    else:
        progress.discard(PRIMARY)
    return result
