"""Load emission factors and enforce the rule that every number has a cited source."""

import re
from pathlib import Path

from pydantic import ValidationError

from bom_to_pcf.io.parsing import missing_columns, parse_decimal, read_bytes, read_rows
from bom_to_pcf.models import EmissionFactor, Issue, Severity

FACTOR_COLUMNS = [
    "factor_id",
    "name",
    "value",
    "unit",
    "gwp_basis",
    "geography",
    "reference_year",
    "source_id",
    "data_type",
    "dqr_tech",
    "dqr_geo",
    "dqr_time",
    "notes",
    "status",
]
OPTIONAL_NUMBERS = ["value", "reference_year", "dqr_tech", "dqr_geo", "dqr_time"]


def read_source_ids(source: Path | str | bytes) -> set[str]:
    """Return the source IDs documented as `## ID` headings in SOURCES.md."""
    text = read_bytes(source).decode("utf-8")
    return set(re.findall(r"^## (\S+)\s*$", text, flags=re.MULTILINE))


def load_factors(
    factors: Path | str | bytes, sources: Path | str | bytes
) -> tuple[list[EmissionFactor], list[Issue]]:
    """Read factors. A factor that breaks a sourcing rule is an error and is left out."""
    rows = read_rows(factors)
    missing = missing_columns(rows, FACTOR_COLUMNS)
    if missing:
        return [], [
            _issue(
                Severity.ERROR,
                "missing_columns",
                f"The factor file is empty or lacks columns: {', '.join(missing)}.",
            )
        ]

    known_sources = read_source_ids(sources)
    loaded: list[EmissionFactor] = []
    issues: list[Issue] = []
    seen: set[str] = set()
    for row_number, row in rows:
        factor_id = row["factor_id"]
        try:
            numbers = {
                key: parse_decimal(row[key])[0] if row[key] else None for key in OPTIONAL_NUMBERS
            }
            factor = EmissionFactor(**(row | numbers))
        except (ValueError, ValidationError) as error:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "invalid_factor",
                    f"Factor {factor_id or '(no id)'} dropped: {error}.",
                    row_number,
                )
            )
            continue

        problem = _sourcing_problem(factor, known_sources)
        if factor_id in seen:
            problem = "the factor ID is used twice"
        if problem:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "unsourced_factor",
                    f"Factor {factor_id} dropped: {problem}.",
                    row_number,
                )
            )
            continue
        seen.add(factor_id)
        if factor.is_placeholder:
            issues.append(
                _issue(
                    Severity.WARNING,
                    "placeholder_factor",
                    f"Factor {factor_id} has no value yet; results using it stay in draft.",
                    row_number,
                )
            )
        loaded.append(factor)
    return loaded, issues


def _sourcing_problem(factor: EmissionFactor, known_sources: set[str]) -> str | None:
    if factor.is_placeholder:
        return "a placeholder must not have a value" if factor.value is not None else None
    if factor.status != "ACTIVE":
        return f"status '{factor.status}' is not ACTIVE or PLACEHOLDER"
    if factor.value is None:
        return "it has no value and is not marked PLACEHOLDER"
    if not factor.source_id:
        return "it has a value but no source_id"
    if factor.source_id not in known_sources:
        return f"source_id {factor.source_id} is not listed in SOURCES.md"
    return None


def _issue(severity: Severity, code: str, message: str, row: int | None = None) -> Issue:
    return Issue(severity=severity, code=code, source="factors", message=message, row=row)
