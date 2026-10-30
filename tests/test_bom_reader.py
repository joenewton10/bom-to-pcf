import pytest

from bom_to_pcf.io.bom_reader import read_bom, read_routing
from bom_to_pcf.io.parsing import parse_date, parse_decimal
from bom_to_pcf.models import Severity, issues_table

HEADER = (
    "material_number,material_description,parent_material,bom_level,component_qty,uom,"
    "base_qty,base_uom,item_category,plant,valid_from,supplier_id\n"
)
ROUTING_HEADER = (
    "step_id,step_name,machine,throughput_kg_per_h,power_kw,utilisation,scrap_rate,"
    "scrap_destination\n"
)


def bom(*rows: str) -> bytes:
    return (HEADER + "\n".join(rows) + "\n").encode("utf-8")


def row(
    material: str = "100002",
    qty: str = "1",
    uom: str = "KG",
    base: str = "1000",
    base_uom: str = "ST",
    valid_from: str = "2023-03-01",
    supplier: str = "SUP-002",
) -> str:
    return f"{material},Desc,500100,1,{qty},{uom},{base},{base_uom},L,DE01,{valid_from},{supplier}"


def codes(issues: list) -> set[str]:
    return {issue.code for issue in issues}


@pytest.mark.parametrize(
    ("text", "value", "german"),
    [
        ("11,4", 11.4, True),
        ("1.234,5", 1234.5, True),
        ("0.002", 0.002, False),
        ("1,234.5", 1234.5, False),
        ("1000", 1000.0, False),
    ],
)
def test_parse_decimal(text: str, value: float, german: bool) -> None:
    assert parse_decimal(text) == (value, german)


@pytest.mark.parametrize("text", ["", "abc", "1,2,3", "nan"])
def test_parse_decimal_rejects_bad_values(text: str) -> None:
    with pytest.raises(ValueError):
        parse_decimal(text)


def test_parse_date_reads_iso_and_german() -> None:
    assert parse_date("31.01.2024") == parse_date("2024-01-31")


def test_german_decimal_is_normalised_and_logged(config) -> None:
    lines, issues = read_bom(bom(row(qty='"0,18"')), config)
    assert lines[0].qty_kg == pytest.approx(0.18)
    assert "decimal_comma_normalised" in codes(issues)


def test_grams_convert_to_kg(config) -> None:
    lines, _ = read_bom(bom(row(qty="285", uom="G")), config)
    assert lines[0].qty_kg == pytest.approx(0.285)


def test_lowercase_unit_is_accepted(config) -> None:
    lines, _ = read_bom(bom(row(qty="2", uom="kg")), config)
    assert lines[0].uom == "KG"


def test_film_area_converts_by_density_and_thickness(config) -> None:
    lines, _ = read_bom(bom(row(material="100001", qty="10", uom="M2")), config)
    assert lines[0].qty_kg == pytest.approx(10 * 1390 * 125e-6)


def test_liner_area_converts_by_grammage(config) -> None:
    lines, _ = read_bom(bom(row(material="100003", qty="10", uom="M2")), config)
    assert lines[0].qty_kg == pytest.approx(0.6)


def test_pieces_convert_by_mass_per_piece(config) -> None:
    lines, _ = read_bom(bom(row(material="100006", qty="0.002", uom="ST")), config)
    assert lines[0].qty_kg == pytest.approx(0.04)


def test_quantity_per_kg_uses_part_mass_for_base(config) -> None:
    lines, _ = read_bom(bom(row(qty="1")), config)
    assert lines[0].qty_kg_per_kg_product == pytest.approx(1 / 2.5)


def test_mass_base_unit_needs_no_part_mass(config) -> None:
    lines, _ = read_bom(bom(row(qty="1", base="10", base_uom="KG")), config)
    assert lines[0].qty_kg_per_kg_product == pytest.approx(0.1)


@pytest.mark.parametrize(
    ("material", "uom", "fragment"),
    [
        ("100002", "M2", "grammage"),
        ("100002", "ST", "mass per piece"),
        ("100002", "LTR", "not recognised"),
    ],
)
def test_unconvertible_units_are_errors(config, material: str, uom: str, fragment: str) -> None:
    lines, issues = read_bom(bom(row(material=material, uom=uom)), config)
    assert lines == []
    assert issues[0].severity is Severity.ERROR
    assert fragment in issues[0].message


def test_exact_duplicate_is_dropped_with_warning(config) -> None:
    lines, issues = read_bom(bom(row(), row()), config)
    assert len(lines) == 1
    duplicate = next(issue for issue in issues if issue.code == "duplicate_line")
    assert duplicate.severity is Severity.WARNING
    assert duplicate.row == 3


def test_conflicting_duplicate_is_an_error(config) -> None:
    lines, issues = read_bom(bom(row(qty="1"), row(qty="2")), config)
    assert lines[0].qty_kg == 1
    assert "conflicting_duplicate" in codes(issues)


def test_missing_supplier_is_kept_and_flagged(config) -> None:
    lines, issues = read_bom(bom(row(supplier="")), config)
    assert lines[0].supplier_id is None
    assert "missing_supplier" in codes(issues)


def test_obsolete_valid_from_is_flagged(config) -> None:
    lines, issues = read_bom(bom(row(valid_from="15.06.2009")), config)
    assert len(lines) == 1
    assert "obsolete_valid_from" in codes(issues)


def test_future_and_unreadable_dates_are_flagged(config) -> None:
    _, future = read_bom(bom(row(valid_from="2030-01-01")), config)
    _, unreadable = read_bom(bom(row(valid_from="soon")), config)
    assert "future_valid_from" in codes(future)
    assert "invalid_valid_from" in codes(unreadable)


@pytest.mark.parametrize("qty", ["abc", "0", "-1"])
def test_bad_quantity_drops_row(config, qty: str) -> None:
    lines, issues = read_bom(bom(row(qty=qty)), config)
    assert lines == []
    assert "invalid_row" in codes(issues)


def test_missing_material_number_drops_row(config) -> None:
    lines, issues = read_bom(bom(row(material="")), config)
    assert lines == []
    assert "missing_material" in codes(issues)


def test_missing_columns_are_reported(config) -> None:
    lines, issues = read_bom(b"material_number,uom\n100001,KG\n", config)
    assert lines == []
    assert issues[0].code == "missing_columns"
    assert "base_qty" in issues[0].message


def test_empty_file_is_reported(config) -> None:
    assert read_bom(b"", config)[1][0].code == "missing_columns"


def test_semicolon_delimiter_and_cp1252_are_read(config) -> None:
    text = (HEADER + row(qty="1") + "\n").replace(",", ";").replace("Desc", "PET-Folie 125 µm")
    lines, _ = read_bom(text.encode("cp1252"), config)
    assert lines[0].description == "PET-Folie 125 µm"


def test_issues_table_has_stable_columns_and_sorts_by_severity(config) -> None:
    _, issues = read_bom(bom(row(qty='"1,5"', supplier=""), row(material="", qty="1")), config)
    table = issues_table(issues)
    assert list(table.columns) == ["severity", "source", "row", "material", "code", "message"]
    assert table["severity"].tolist()[0] == "error"
    assert issues_table([]).empty


def routing(*rows: str) -> bytes:
    return (ROUTING_HEADER + "\n".join(rows) + "\n").encode("utf-8")


def test_routing_energy_per_kg(config) -> None:
    steps, issues = read_routing(routing("S1,Slit,M1,400,15,0.7,0.02,recycling"), config)
    assert issues == []
    assert steps[0].kwh_per_kg == pytest.approx(15 * 0.7 / 400)


@pytest.mark.parametrize(
    "line",
    [
        "S1,Slit,M1,0,15,0.7,0.02,none",
        "S1,Slit,M1,400,15,1.7,0.02,none",
        "S1,Slit,M1,x,15,0.7,0,none",
    ],
)
def test_routing_rejects_impossible_values(config, line: str) -> None:
    steps, issues = read_routing(routing(line), config)
    assert steps == []
    assert issues[0].code == "invalid_row"


def test_routing_flags_unknown_scrap_destination(config) -> None:
    _, issues = read_routing(routing("S1,Slit,M1,400,15,0.7,0.02,landfill"), config)
    assert issues[0].code == "unknown_scrap_destination"


def test_routing_missing_columns(config) -> None:
    assert read_routing(b"step_id\nS1\n", config)[1][0].code == "missing_columns"
