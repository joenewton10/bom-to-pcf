"""Check an environmental claim against the result. A guidance aid, not legal advice."""

import re
from pathlib import Path

import yaml
from pydantic import BaseModel

from bom_to_pcf.models import PcfResult

SUPPORTED = "supported"
NEEDS_MORE = "needs_more"
NOT_SUPPORTED = "not_supported"
BLOCKED = "blocked"
VERDICT_LABELS = {
    SUPPORTED: "✅ Supported",
    NEEDS_MORE: "⚠️ Needs more",
    NOT_SUPPORTED: "❌ Not supported",
    BLOCKED: "❌ Blocked",
}
NUMBER_THEN_UNIT = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*kg\s*co2\s*e?\s*(?:per|/)\s*(1[,.]?000\s*(?:parts|pieces|pcs)|kg)"
)


class PatternRule(BaseModel):
    id: str
    patterns: list[str]
    reason: str
    basis: str


class SimpleRule(BaseModel):
    reason: str
    basis: str


class SupportedRule(BaseModel):
    required: list[str]
    value_tolerance: float
    reason: str
    mismatch_reason: str
    basis: str


class ClaimsRules(BaseModel):
    """The claims rules, loaded from YAML."""

    legal_note: str
    examples: list[str]
    not_supported: list[PatternRule]
    draft_block: SimpleRule
    needs_more: list[PatternRule]
    supported: SupportedRule
    unrecognised: SimpleRule

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ClaimsRules":
        return cls.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


class ClaimVerdict(BaseModel):
    verdict: str
    label: str
    reason: str
    basis: str
    rule_id: str


def _normalise(claim: str) -> str:
    return " ".join(claim.lower().replace("₂", "2").replace("co 2", "co2").split())


def _match(rules: list[PatternRule], text: str) -> PatternRule | None:
    return next((r for r in rules if any(re.search(p, text) for p in r.patterns)), None)


def _verdict(verdict: str, reason: str, basis: str, rule_id: str) -> ClaimVerdict:
    return ClaimVerdict(
        verdict=verdict,
        label=VERDICT_LABELS[verdict],
        reason=reason,
        basis=basis,
        rule_id=rule_id,
    )


def _figure_matches(text: str, result: PcfResult, tolerance: float) -> bool:
    found = NUMBER_THEN_UNIT.search(text)
    if found is None:
        return False
    value = float(found.group(1).replace(",", "."))
    target = result.kg_co2e_per_kg if found.group(2) == "kg" else result.kg_co2e_per_1000_pieces
    return abs(value - target) <= tolerance


def check_claim(claim: str, result: PcfResult, rules: ClaimsRules) -> ClaimVerdict:
    """Give one verdict with a one-line reason. Banned wording is reported ahead of draft status."""
    text = _normalise(claim)
    banned = _match(rules.not_supported, text)
    if banned:
        return _verdict(NOT_SUPPORTED, banned.reason, banned.basis, banned.id)
    if result.is_draft:
        return _verdict(BLOCKED, rules.draft_block.reason, rules.draft_block.basis, "draft")
    needs = _match(rules.needs_more, text)
    if needs:
        return _verdict(NEEDS_MORE, needs.reason, needs.basis, needs.id)
    supported = rules.supported
    if all(re.search(p, text) for p in supported.required):
        if _figure_matches(text, result, supported.value_tolerance):
            return _verdict(SUPPORTED, supported.reason, supported.basis, "specific")
        return _verdict(NEEDS_MORE, supported.mismatch_reason, supported.basis, "figure_mismatch")
    return _verdict(NEEDS_MORE, rules.unrecognised.reason, rules.unrecognised.basis, "unrecognised")
