import json

from bom_to_pcf.io.supplier_reader import read_supplier_pcfs, read_suppliers, read_transport


def pcf_file(**overrides: object) -> bytes:
    # Numbers here are test inputs for the reader, not emission data.
    record = {
        "supplier_id": "SUP-001",
        "material_number": "100001",
        "pcf_value": 1.0,
        "declared_unit": "kg",
        "reference_period_start": "2024-01-01",
        "reference_period_end": "2024-12-31",
        "method": "ISO 14067",
        "boundary": "cradle-to-gate",
    }
    return json.dumps({"records": [record | overrides]}).encode()


def test_complete_record_is_usable(config) -> None:
    pcfs, issues = read_supplier_pcfs(pcf_file(), config)
    assert pcfs[0].usable
    assert issues == []


def test_placeholder_record_falls_back(config) -> None:
    pcfs, issues = read_supplier_pcfs(pcf_file(pcf_value=None, status="PLACEHOLDER"), config)
    assert not pcfs[0].usable
    assert issues[0].code == "supplier_pcf_placeholder"
    assert "secondary data" in issues[0].message


def test_incomplete_record_falls_back_and_names_the_field(config) -> None:
    pcfs, issues = read_supplier_pcfs(pcf_file(method=None), config)
    assert not pcfs[0].usable
    assert issues[0].code == "supplier_pcf_incomplete"
    assert "method" in issues[0].message


def test_expired_record_falls_back(config) -> None:
    pcfs, issues = read_supplier_pcfs(pcf_file(reference_period_end="2021-12-31"), config)
    assert not pcfs[0].usable
    assert issues[0].code == "supplier_pcf_expired"


def test_malformed_record_and_file_are_errors(config) -> None:
    assert read_supplier_pcfs(pcf_file(pcf_value="lots"), config)[1][0].code == "invalid_record"
    assert read_supplier_pcfs(b"not json", config)[1][0].code == "invalid_file"
    assert read_supplier_pcfs(b"{}", config)[1][0].code == "invalid_file"


def test_suppliers_split_material_list() -> None:
    text = b"supplier_id,name,country,contact_role,materials_supplied\nS,N,DE,R,1|2\n"
    assert read_suppliers(text)[0][0].materials_supplied == ["1", "2"]
    assert read_suppliers(b"supplier_id\nS\n")[1][0].code == "missing_columns"


def test_transport_reads_legs_and_rejects_bad_distance() -> None:
    header = b"leg_id,material_number,supplier_id,origin,destination,mode,distance_km\n"
    legs, issues = read_transport(header + b'T1,1,,DE,DE01,ROAD,"1,5"\nT2,1,,DE,DE01,road,-4\n')
    assert legs[0].distance_km == 1.5
    assert legs[0].mode == "road"
    assert legs[0].supplier_id is None
    assert issues[0].code == "invalid_row"
    assert read_transport(b"leg_id\nT\n")[1][0].code == "missing_columns"
