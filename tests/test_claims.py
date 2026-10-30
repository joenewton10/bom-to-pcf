from pathlib import Path

import pytest
from engine_helpers import load_case
from streamlit.testing.v1 import AppTest
from test_app_smoke import HOME, TIMEOUT, try_demo
from test_engine import run

from bom_to_pcf.claims import (
    BLOCKED,
    NEEDS_MORE,
    NOT_SUPPORTED,
    SUPPORTED,
    ClaimsRules,
    check_claim,
)
from bom_to_pcf.models import Mapping

ROOT = Path(__file__).resolve().parents[1]
RULES = ClaimsRules.from_yaml(ROOT / "config" / "claims_rules.yaml")


@pytest.fixture
def final():
    result = run(load_case())
    assert not result.is_draft
    return result


@pytest.fixture
def draft():
    case = load_case()
    case.mappings[0] = Mapping(material_number="1", factor_id="FILM", review_status="unreviewed")
    result = run(case)
    assert result.is_draft
    return result


def specific(result) -> str:
    return (
        f"{result.kg_co2e_per_kg:.2f} kg CO2e per kg, cradle-to-gate, calculated based on ISO 14067"
    )


def test_specific_matching_claim_is_supported_on_a_final_result(final) -> None:
    verdict = check_claim(specific(final), final, RULES)
    assert verdict.verdict == SUPPORTED
    assert verdict.reason
    assert "illustrative" in verdict.reason


def test_draft_blocks_the_same_claim(draft) -> None:
    verdict = check_claim(specific(draft), draft, RULES)
    assert verdict.verdict == BLOCKED
    assert "draft" in verdict.reason


@pytest.mark.parametrize(
    "claim",
    [
        "{value} kg CO₂e per kg, cradle-to-gate, per ISO 14067",
        "{value} KG CO2e/kg, Cradle to Gate, ISO14067",
        "{value} kg CO2e per kg, cradle-to-gate, based on ISO 14067",
    ],
)
def test_supported_wording_variants(final, claim: str) -> None:
    text = claim.format(value=f"{final.kg_co2e_per_kg:.2f}")
    assert check_claim(text, final, RULES).verdict == SUPPORTED


def test_per_1000_parts_figure_is_supported(final) -> None:
    text = (
        f"{final.kg_co2e_per_1000_pieces:.2f} kg CO2e per 1,000 parts, cradle-to-gate, "
        "based on ISO 14067"
    )
    assert check_claim(text, final, RULES).verdict == SUPPORTED


def test_german_decimal_comma_is_understood(final) -> None:
    value = f"{final.kg_co2e_per_kg:.2f}".replace(".", ",")
    text = f"{value} kg CO2e per kg, cradle-to-gate, ISO 14067"
    assert check_claim(text, final, RULES).verdict == SUPPORTED


@pytest.mark.parametrize(
    "claim",
    [
        "1.00 kg CO2e per kg, cradle-to-gate, ISO 14067",
        "cradle-to-gate per ISO 14067",
        "2.74 kg per kg, cradle-to-gate, ISO 14067",
    ],
)
def test_wrong_or_missing_figure_is_not_supported(final, claim: str) -> None:
    verdict = check_claim(claim, final, RULES)
    assert verdict.verdict == NEEDS_MORE
    assert verdict.rule_id == "figure_mismatch"


@pytest.mark.parametrize(
    "claim",
    [
        "Climate neutral",
        "CO2-neutral film",
        "carbon neutral part",
        "klimaneutral",
        "Net zero product",
        "Offset by certified projects",
        "Fully compensated emissions",
    ],
)
def test_offset_based_claims_are_not_supported(final, draft, claim: str) -> None:
    for result in (final, draft):
        verdict = check_claim(claim, result, RULES)
        assert verdict.verdict == NOT_SUPPORTED
        assert verdict.rule_id == "offset_based"
        assert "4c" in verdict.basis


@pytest.mark.parametrize(
    "claim",
    [
        "Eco-friendly film",
        "eco friendly",
        "Environmentally friendly insulation",
        "Green product",
        "umweltfreundlich",
        "A sustainable choice",
        "nachhaltig",
        "Climate-friendly part",
        "Biodegradable",
    ],
)
def test_generic_claims_are_not_supported(final, claim: str) -> None:
    verdict = check_claim(claim, final, RULES)
    assert verdict.verdict == NOT_SUPPORTED
    assert verdict.rule_id == "generic"
    assert "4a" in verdict.basis


def test_a_specific_figure_cannot_excuse_generic_wording(final) -> None:
    claim = f"Eco-friendly: {specific(final)}"
    assert check_claim(claim, final, RULES).verdict == NOT_SUPPORTED


def test_words_containing_green_are_not_caught(final) -> None:
    assert check_claim("Evergreen supply contract", final, RULES).rule_id == "unrecognised"


@pytest.mark.parametrize(
    "claim",
    [
        "20% lower than our previous part",
        "Lower footprint compared to the market average",
        "15 % reduction",
        "The lowest footprint available",
    ],
)
def test_comparative_claims_need_a_benchmark(final, claim: str) -> None:
    verdict = check_claim(claim, final, RULES)
    assert verdict.verdict == NEEDS_MORE
    assert verdict.rule_id == "comparative"
    assert "benchmark" in verdict.reason


@pytest.mark.parametrize("claim", ["Made with recycled PET", "Low-carbon film", "Renewable power"])
def test_claims_about_one_aspect_need_more(final, claim: str) -> None:
    verdict = check_claim(claim, final, RULES)
    assert verdict.verdict == NEEDS_MORE
    assert verdict.rule_id == "partial_aspect"
    assert "4b" in verdict.basis


def test_draft_blocks_comparative_claims_too(draft) -> None:
    assert check_claim("20% lower than before", draft, RULES).verdict == BLOCKED


def test_unknown_claim_goes_to_a_person(final) -> None:
    verdict = check_claim("Made in Germany", final, RULES)
    assert verdict.verdict == NEEDS_MORE
    assert verdict.rule_id == "unrecognised"


def test_every_verdict_has_a_one_line_reason_and_a_basis(final, draft) -> None:
    claims = [specific(final), "Green", "Climate neutral", "20% lower than x", "Made in Germany"]
    for claim in claims:
        for result in (final, draft):
            verdict = check_claim(claim, result, RULES)
            assert verdict.reason
            assert "\n" not in verdict.reason
            assert verdict.basis


def test_rules_say_they_are_not_legal_advice() -> None:
    assert "not legal advice" in RULES.legal_note


def page() -> AppTest:
    at = try_demo(AppTest.from_file(HOME, default_timeout=TIMEOUT).run())
    at.switch_page("pages/8_Export_and_claims.py")
    return at.run()


def test_page_blocks_claims_on_the_draft_demo() -> None:
    at = page()
    assert not at.exception
    assert any("Blocked" in e.value for e in at.error)
    assert any("passes the official schema" in s.value for s in at.success)


def test_page_lets_the_user_type_a_claim() -> None:
    at = page()
    at.selectbox[0].set_value("Type your own")
    at.run()
    at.text_input[0].input("Climate neutral")
    at.run()
    assert not at.exception
    assert any("Not supported" in e.value for e in at.error)


def test_page_prompts_without_data() -> None:
    at = AppTest.from_file(HOME, default_timeout=TIMEOUT).run()
    at.switch_page("pages/8_Export_and_claims.py")
    at.run()
    assert any("No data loaded" in i.value for i in at.info)
