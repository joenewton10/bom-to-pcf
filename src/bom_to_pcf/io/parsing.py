"""Low-level parsing shared by the readers: decimals, dates and delimited text."""

import csv
import io
import math
from datetime import date, datetime
from pathlib import Path

DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y")


def read_bytes(source: Path | str | bytes) -> bytes:
    """Accept a path or the raw bytes of an uploaded file."""
    return source if isinstance(source, bytes) else Path(source).read_bytes()


def decode(raw: bytes) -> str:
    """Decode UTF-8 (with or without BOM), falling back to the Windows code page SAP often uses."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def read_rows(source: Path | str | bytes) -> list[tuple[int, dict[str, str]]]:
    """Return (file line number, row) pairs. Headers are lower-cased; `,` or `;` delimited."""
    text = decode(read_bytes(source))
    header = text.splitlines()[0] if text.strip() else ""
    delimiter = ";" if ";" in header and "," not in header else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if reader.fieldnames:
        reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]
    return [
        (reader.line_num, {key: (value or "").strip() for key, value in row.items() if key})
        for row in reader
    ]


def missing_columns(rows: list[tuple[int, dict[str, str]]], required: list[str]) -> list[str]:
    """Columns absent from the file. An empty file is missing all of them."""
    present = rows[0][1].keys() if rows else ()
    return [column for column in required if column not in present]


def parse_decimal(text: str) -> tuple[float, bool]:
    """Parse a number in English or German notation; the flag is True for German notation.

    With both separators the last one is the decimal mark. A lone comma is a decimal mark,
    because SAP's German number format is the reason commas appear in these exports.
    """
    value = text.replace(" ", "")
    if not value:
        raise ValueError("empty value")
    has_comma, has_dot = "," in value, "." in value
    german = has_comma and (not has_dot or value.rfind(",") > value.rfind("."))
    if german:
        if value.count(",") > 1:
            raise ValueError(f"cannot read number '{text}'")
        value = value.replace(".", "").replace(",", ".")
    elif has_comma:
        value = value.replace(",", "")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"cannot read number '{text}'")
    return number, german


def parse_date(text: str) -> date:
    """Parse an ISO (2024-01-31) or German (31.01.2024) date."""
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue
    raise ValueError(f"cannot read date '{text}'")
