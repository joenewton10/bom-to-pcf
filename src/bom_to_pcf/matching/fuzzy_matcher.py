"""Propose matches between BOM descriptions and candidates by text similarity."""

import re
from pathlib import Path

import yaml
from rapidfuzz import fuzz

from bom_to_pcf.models import Candidate, Suggestion

MAX_SCORE = 100


def load_candidates(path: Path | str) -> list[Candidate]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return [Candidate.model_validate(candidate) for candidate in raw["candidates"]]


def _normalise(text: str) -> str:
    return re.sub(r"[^\w]+", " ", text.lower()).strip()


def suggest_matches(description: str, candidates: list[Candidate], top_n: int) -> list[Suggestion]:
    """Return the best candidates, highest score first. Ties keep the candidate file's order."""
    target = _normalise(description)
    scored = [
        (
            max(fuzz.partial_ratio(_normalise(term), target) for term in candidate.terms),
            candidate,
        )
        for candidate in candidates
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [
        Suggestion(
            candidate_id=candidate.id,
            label=candidate.label,
            source="fuzzy",
            confidence=score / MAX_SCORE,
        )
        for score, candidate in scored[:top_n]
    ]
