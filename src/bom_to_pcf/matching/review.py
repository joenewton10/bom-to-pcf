"""Human review of suggested matches, shared by the app and the command line."""

from datetime import UTC, datetime

import pandas as pd

from bom_to_pcf.matching.fuzzy_matcher import suggest_matches
from bom_to_pcf.models import (
    BomLine,
    Candidate,
    Mapping,
    ReviewItem,
    ReviewLogEntry,
    Suggestion,
)

PENDING = "pending"
APPROVE = "approve"
REJECT = "reject"
CHOOSE_OTHER = "choose_other"
DECISION_LABELS = {
    PENDING: "Pending",
    APPROVE: "Approve",
    REJECT: "Reject",
    CHOOSE_OTHER: "Choose other",
}
LOG_COLUMNS = list(ReviewLogEntry.model_fields)


def build_review(bom: list[BomLine], candidates: list[Candidate], top_n: int) -> list[ReviewItem]:
    """Start a review with text-matching suggestions for every BOM material."""
    return [
        ReviewItem(
            material_number=line.material_number,
            description=line.description,
            uom=line.uom,
            suggestions=suggest_matches(line.description, candidates, top_n),
        )
        for line in bom
    ]


def add_llm_suggestion(item: ReviewItem, suggestion: Suggestion) -> None:
    """Put an LLM suggestion first, without changing any decision already made."""
    others = [s for s in item.suggestions if s.candidate_id != suggestion.candidate_id]
    item.suggestions = [suggestion, *others]


def record_decision(
    item: ReviewItem,
    decision: str,
    reviewer: str,
    log: list[ReviewLogEntry],
    comment: str = "",
    chosen_id: str | None = None,
    candidates: list[Candidate] | None = None,
) -> None:
    """Apply a decision and add it to the log. Raises ValueError if it is incomplete."""
    if not reviewer.strip():
        raise ValueError("a reviewer name is needed")
    if decision == CHOOSE_OTHER and not chosen_id:
        raise ValueError(f"{item.description}: pick the other match to use")
    if decision != CHOOSE_OTHER:
        chosen_id = None
    if (decision, chosen_id, comment) == (item.decision, item.chosen_id, item.comment):
        return

    top = item.suggestions[0] if item.suggestions else None
    labels = {candidate.id: candidate.label for candidate in candidates or []}
    item.decision, item.chosen_id, item.comment = decision, chosen_id, comment
    log.append(
        ReviewLogEntry(
            timestamp=datetime.now(UTC).isoformat(timespec="seconds"),
            bom_item=f"{item.material_number} {item.description}",
            suggestion=top.label if top else "",
            source=top.source if top else "",
            confidence=top.confidence if top else None,
            decision=decision,
            chosen=labels.get(chosen_id, chosen_id or ""),
            reviewer=reviewer.strip(),
            comment=comment,
        )
    )


def mappings_from_review(items: list[ReviewItem], candidates: list[Candidate]) -> list[Mapping]:
    """Turn review state into factor mappings.

    A rejected material gets no mapping, so it is reported as a gap. A pending material uses its
    top suggestion marked unreviewed, which keeps the whole result in draft.
    """
    by_id = {candidate.id: candidate for candidate in candidates}
    mappings: list[Mapping] = []
    for item in items:
        if item.decision == REJECT:
            continue
        if item.decision == CHOOSE_OTHER:
            candidate_id = item.chosen_id
        elif item.suggestions:
            candidate_id = item.suggestions[0].candidate_id
        else:
            continue
        status = "unreviewed" if item.decision == PENDING else "approved"
        mappings.extend(
            Mapping(material_number=item.material_number, factor_id=factor_id, review_status=status)
            for factor_id in by_id[candidate_id].factor_ids
        )
    return mappings


def review_complete(items: list[ReviewItem]) -> bool:
    return bool(items) and all(item.decision != PENDING for item in items)


def review_table(items: list[ReviewItem], candidates: list[Candidate]) -> pd.DataFrame:
    """The editable review table: one row per material, with plain-English choices."""
    labels = {candidate.id: candidate.label for candidate in candidates}
    rows = []
    for item in items:
        top = item.suggestions[0] if item.suggestions else None
        rows.append(
            {
                "Material": item.material_number,
                "Description": item.description,
                "Unit": item.uom,
                "Suggested match": top.label if top else "",
                "Match score": top.confidence if top else None,
                "Source": top.source if top else "",
                "Other suggestions": "; ".join(
                    f"{s.label} ({s.confidence:.0%})" for s in item.suggestions[1:]
                ),
                "Decision": DECISION_LABELS[item.decision],
                "Use instead": labels.get(item.chosen_id, ""),
                "Comment": item.comment,
            }
        )
    return pd.DataFrame(rows)


def apply_review_table(
    items: list[ReviewItem],
    table: pd.DataFrame,
    candidates: list[Candidate],
    reviewer: str,
    log: list[ReviewLogEntry],
) -> None:
    """Record every changed row. Rows are checked first, so a bad row changes nothing."""
    ids_by_label = {candidate.label: candidate.id for candidate in candidates}
    decisions_by_label = {label: key for key, label in DECISION_LABELS.items()}
    changes = []
    for item, row in zip(items, table.to_dict("records"), strict=True):
        decision = decisions_by_label[row["Decision"]]
        chosen = row["Use instead"]
        chosen_id = ids_by_label.get(chosen) if isinstance(chosen, str) else None
        comment = row["Comment"] if isinstance(row["Comment"], str) else ""
        if decision == CHOOSE_OTHER and not chosen_id:
            raise ValueError(f"{item.description}: pick the other match to use")
        changes.append((item, decision, chosen_id, comment))
    for item, decision, chosen_id, comment in changes:
        record_decision(item, decision, reviewer, log, comment, chosen_id, candidates)


def log_table(log: list[ReviewLogEntry]) -> pd.DataFrame:
    return pd.DataFrame([entry.model_dump() for entry in log], columns=LOG_COLUMNS)
