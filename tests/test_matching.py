import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from test_app_smoke import HOME, TIMEOUT, try_demo

from bom_to_pcf.engine.python_engine import LABEL_FINAL, run_with_config
from bom_to_pcf.io.factor_store import load_factors, read_mappings
from bom_to_pcf.io.inputs import load_inputs
from bom_to_pcf.matching import llm_matcher
from bom_to_pcf.matching.fuzzy_matcher import load_candidates, suggest_matches
from bom_to_pcf.matching.llm_matcher import build_request, make_client, rank_with_llm
from bom_to_pcf.matching.review import (
    APPROVE,
    CHOOSE_OTHER,
    LOG_COLUMNS,
    REJECT,
    add_llm_suggestion,
    apply_review_table,
    build_review,
    log_table,
    mappings_from_review,
    record_decision,
    review_complete,
    review_table,
)
from bom_to_pcf.models import MatchingConfig, ProductConfig, ReviewItem, Suggestion

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "data" / "demo"
CANDIDATES = ROOT / "data" / "mappings" / "candidates.yaml"
LLM_CONFIG = MatchingConfig(
    top_n=3,
    llm_default_on=False,
    llm_model="test-model",
    llm_effort="low",
    llm_max_tokens=100,
    llm_session_call_limit=5,
)


@pytest.fixture
def candidates():
    return load_candidates(CANDIDATES)


@pytest.fixture
def review(config, candidates):
    return build_review(load_inputs(config, DEMO).bom, candidates, 3)


def llm_response(payload: object, stop_reason: str = "end_turn") -> SimpleNamespace:
    block = SimpleNamespace(type="text", text=json.dumps(payload))
    return SimpleNamespace(stop_reason=stop_reason, content=[block])


def llm_client(response: SimpleNamespace) -> MagicMock:
    client = MagicMock()
    client.beta.messages.create.return_value = response
    return client


def test_candidates_only_use_factors_that_exist(candidates) -> None:
    factors, _ = load_factors(ROOT / "data/factors/emission_factors.csv",
                              ROOT / "data/factors/SOURCES.md")  # fmt: skip
    known = {factor.factor_id for factor in factors}
    for candidate in candidates:
        assert set(candidate.factor_ids) <= known


def test_top_suggestion_is_right_for_every_demo_material(review, candidates) -> None:
    """Text matching on its own must reach the mapping in bom_to_dataset.csv."""
    expected, _ = read_mappings(ROOT / "data/mappings/bom_to_dataset.csv")
    actual = mappings_from_review(review, candidates)
    pairs = {(m.material_number, m.factor_id) for m in actual}
    assert pairs == {(m.material_number, m.factor_id) for m in expected}


def test_three_suggestions_are_ranked(review) -> None:
    for item in review:
        scores = [s.confidence for s in item.suggestions]
        assert len(scores) == 3
        assert scores == sorted(scores, reverse=True)


def test_an_unrelated_description_scores_low(candidates) -> None:
    assert suggest_matches("Stahlschraube M4", candidates, 1)[0].confidence < 0.7


def test_pending_items_are_provisional(review, candidates) -> None:
    assert {m.review_status for m in mappings_from_review(review, candidates)} == {"unreviewed"}
    assert not review_complete(review)


def test_approval_is_logged_and_marks_mapping_approved(review, candidates) -> None:
    log = []
    record_decision(review[0], APPROVE, "A Reviewer", log, "Looks right")
    entry = log[0]
    assert entry.reviewer == "A Reviewer"
    assert entry.decision == APPROVE
    assert entry.source == "fuzzy"
    assert entry.comment == "Looks right"
    assert entry.bom_item.startswith(review[0].material_number)
    mappings = mappings_from_review(review[:1], candidates)
    assert {m.review_status for m in mappings} == {"approved"}


def test_rejected_material_has_no_mapping(review, candidates) -> None:
    record_decision(review[0], REJECT, "A Reviewer", [])
    assert mappings_from_review(review[:1], candidates) == []


def test_choose_other_uses_the_chosen_candidate(review, candidates) -> None:
    log = []
    record_decision(review[0], CHOOSE_OTHER, "A", log, chosen_id="pet_film_recycled",
                    candidates=candidates)  # fmt: skip
    factor_ids = {m.factor_id for m in mappings_from_review(review[:1], candidates)}
    assert "PET_RESIN_RECYCLED" in factor_ids
    assert log[0].chosen == "PET film, recycled (resin + film making)"


def test_decision_needs_a_reviewer(review) -> None:
    with pytest.raises(ValueError, match="reviewer"):
        record_decision(review[0], APPROVE, "  ", [])


def test_choose_other_needs_a_choice(review) -> None:
    with pytest.raises(ValueError, match="pick the other"):
        record_decision(review[0], CHOOSE_OTHER, "A", [])


def test_unchanged_decision_adds_no_log_entry(review) -> None:
    log = []
    record_decision(review[0], APPROVE, "A", log)
    record_decision(review[0], APPROVE, "A", log)
    assert len(log) == 1


def test_changed_decision_adds_to_the_log_and_keeps_history(review) -> None:
    log = []
    record_decision(review[0], APPROVE, "A", log)
    record_decision(review[0], REJECT, "B", log)
    assert [entry.decision for entry in log] == [APPROVE, REJECT]


def test_table_round_trip_records_only_changes(review, candidates) -> None:
    table = review_table(review, candidates)
    table.loc[0, "Decision"] = "Approve"
    log = []
    apply_review_table(review, table, candidates, "A", log)
    assert len(log) == 1
    assert review[0].decision == APPROVE
    assert review[1].decision == "pending"


def test_table_with_a_bad_row_saves_nothing(review, candidates) -> None:
    table = review_table(review, candidates)
    table.loc[0, "Decision"] = "Approve"
    table.loc[1, "Decision"] = "Choose other"
    log = []
    with pytest.raises(ValueError):
        apply_review_table(review, table, candidates, "A", log)
    assert log == []
    assert review[0].decision == "pending"


def test_table_choose_other_maps_label_to_id(review, candidates) -> None:
    table = review_table(review, candidates)
    table.loc[0, ["Decision", "Use instead"]] = ["Choose other", "Wooden pallet"]
    table["Comment"] = pd.NA
    apply_review_table(review, table, candidates, "A", [])
    assert review[0].chosen_id == "pallet_wood"


def test_item_without_suggestions_is_handled(candidates) -> None:
    item = ReviewItem(material_number="1", description="x", uom="KG", suggestions=[])
    assert mappings_from_review([item], candidates) == []
    assert review_table([item], candidates).loc[0, "Suggested match"] == ""
    log = []
    record_decision(item, APPROVE, "A", log)
    assert log[0].suggestion == ""


def test_review_is_not_complete_when_empty() -> None:
    assert not review_complete([])


def test_log_table_has_the_planned_columns(review) -> None:
    assert list(log_table([]).columns) == LOG_COLUMNS
    header = (ROOT / "data/mappings/review_log.csv").read_text(encoding="utf-8").strip()
    assert header.split(",") == LOG_COLUMNS
    for column in ["timestamp", "bom_item", "suggestion", "source", "confidence", "decision",
                   "reviewer", "comment"]:  # fmt: skip
        assert column in LOG_COLUMNS


def test_full_approval_gives_a_final_result(config: ProductConfig, review, candidates) -> None:
    bundle = load_inputs(config, DEMO)
    draft = run_with_config(config, bundle, ROOT, mappings_from_review(review, candidates))
    assert draft.is_draft
    for item in review:
        record_decision(item, APPROVE, "A", [])
    final = run_with_config(config, bundle, ROOT, mappings_from_review(review, candidates))
    assert not final.is_draft
    assert final.status_label == LABEL_FINAL
    assert final.kg_co2e_per_kg == pytest.approx(draft.kg_co2e_per_kg)


def test_rejection_leaves_a_partial_draft(config: ProductConfig, review, candidates) -> None:
    for item in review:
        record_decision(item, APPROVE, "A", [])
    record_decision(review[0], REJECT, "A", [])
    result = run_with_config(
        config, load_inputs(config, DEMO), ROOT, mappings_from_review(review, candidates)
    )
    assert result.is_draft
    assert result.is_partial


def test_llm_request_sends_only_description_unit_and_candidates(candidates) -> None:
    request = build_request("PET-Folie", "M2", candidates, LLM_CONFIG)
    sent = json.loads(request["messages"][0]["content"])
    assert set(sent) == {"description", "unit", "candidates"}
    assert all(set(c) == {"id", "label"} for c in sent["candidates"])
    assert "factor" not in request["messages"][0]["content"].lower()


def test_llm_answer_becomes_a_suggestion(candidates) -> None:
    answer = {"candidate_id": "pet_film_virgin", "rationale": "Same film.", "confidence": 0.9}
    client = llm_client(llm_response(answer))
    suggestion = rank_with_llm("PET-Folie", "M2", candidates, client, LLM_CONFIG)
    assert suggestion.source == "llm"
    assert suggestion.rationale == "Same film."
    assert client.beta.messages.create.call_count == 1


@pytest.mark.parametrize(
    "response",
    [
        llm_response({"candidate_id": "made_up", "rationale": "x", "confidence": 1}),
        llm_response({"rationale": "x"}),
        llm_response({"candidate_id": "pet_film_virgin"}, stop_reason="refusal"),
        SimpleNamespace(
            stop_reason="end_turn", content=[SimpleNamespace(type="text", text="not json")]
        ),
    ],
)
def test_bad_llm_answers_are_ignored(candidates, response) -> None:
    assert rank_with_llm("x", "KG", candidates, llm_client(response), LLM_CONFIG) is None


def test_llm_api_error_is_ignored(candidates, monkeypatch) -> None:
    monkeypatch.setattr(llm_matcher, "_API_ERRORS", (RuntimeError,))
    client = MagicMock()
    client.beta.messages.create.side_effect = RuntimeError("down")
    assert rank_with_llm("x", "KG", candidates, client, LLM_CONFIG) is None


def test_llm_confidence_is_kept_in_range(candidates) -> None:
    answer = {"candidate_id": "pet_film_virgin", "rationale": "x", "confidence": 7}
    suggestion = rank_with_llm("x", "KG", candidates, llm_client(llm_response(answer)), LLM_CONFIG)
    assert suggestion.confidence == 1.0


def test_llm_suggestion_goes_first_without_duplicates(review) -> None:
    item = review[0]
    top = item.suggestions[0]
    add_llm_suggestion(
        item,
        Suggestion(candidate_id=top.candidate_id, label=top.label, source="llm", confidence=0.5),
    )
    assert item.suggestions[0].source == "llm"
    assert len({s.candidate_id for s in item.suggestions}) == len(item.suggestions)


def test_no_key_or_no_package_means_no_client(monkeypatch) -> None:
    monkeypatch.delenv(llm_matcher.API_KEY_VARIABLE, raising=False)
    assert make_client() is None
    monkeypatch.setattr(llm_matcher, "anthropic", None)
    assert make_client("a-test-value") is None


def test_client_is_made_when_key_and_package_exist(monkeypatch) -> None:
    fake = MagicMock()
    monkeypatch.setattr(llm_matcher, "anthropic", fake)
    assert make_client("a-test-value") is fake.Anthropic.return_value


def test_review_page_loads_without_an_api_key(monkeypatch) -> None:
    monkeypatch.delenv(llm_matcher.API_KEY_VARIABLE, raising=False)
    at = try_demo(AppTest.from_file(HOME, default_timeout=TIMEOUT).run())
    at.switch_page("pages/2_Match_and_review.py")
    at.run()
    assert not at.exception
    assert at.title[0].value == "Match & review"
    assert any("switched off" in c.value for c in at.caption)
    assert any("still need a decision" in w.value for w in at.warning)


def test_review_page_prompts_without_data() -> None:
    at = AppTest.from_file(HOME, default_timeout=TIMEOUT).run()
    at.switch_page("pages/2_Match_and_review.py")
    at.run()
    assert not at.exception
    assert any("No data loaded" in i.value for i in at.info)


def test_results_stop_being_draft_after_review_in_the_app() -> None:
    at = try_demo(AppTest.from_file(HOME, default_timeout=TIMEOUT).run())
    assert any("DRAFT" in w.value for w in at.warning)
    project = at.session_state["project_state"]
    for item in project.review_items:
        record_decision(item, APPROVE, "A", [])
    at.session_state["saved_project_state"] = project.model_dump_json()
    at.run()
    assert not at.exception
    assert not at.warning
    assert any("Calculated" in s.value for s in at.success)
    assert "Matches reviewed" in at.session_state["progress"]
