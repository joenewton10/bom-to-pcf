# Data gaps

Every placeholder and representative value in the project is listed here.

## Placeholders (no value yet)

| Item | Where | Status |
|---|---|---|
| Supplier PCF for PET film (SUP-001) | `data/input/supplier_pcf.json` | `pcf_value`, `primary_data_share` and `dqr` are null |
| Supplier PCF for adhesive (SUP-002) | `data/input/supplier_pcf.json` | Same. This record is also deliberately expired, to exercise the fallback |

While these are placeholders, both materials fall back to secondary data, and the reader logs it.

## Representative values (mock, not measured)

These describe a plausible converting operation. They do not come from a real company or a
published source, and they are not emission factors.

- BOM quantities and part mass (`bom_export_sap_mock.csv`, `product_pet_diecut.yaml`)
- Material properties: film density and thickness, liner grammage, mass per piece (`product_pet_diecut.yaml`)
- Machine power, throughput, utilisation and scrap rates (`routing_energy_mock.csv`)
- Transport distances (`transport_legs.csv`)
- Supplier names, which are fictional (`suppliers.csv`)
