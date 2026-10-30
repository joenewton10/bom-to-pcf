# Data gaps

Every placeholder and representative value in the project is listed here.

## Placeholders (no value yet)

| Item | Where | Status |
|---|---|---|
| Supplier PCF for PET film (SUP-001) | `data/input/supplier_pcf.json` | `pcf_value`, `primary_data_share` and `dqr` are null |
| Supplier PCF for adhesive (SUP-002) | `data/input/supplier_pcf.json` | Same. This record is also deliberately expired, to exercise the fallback |

While these are placeholders, both materials fall back to secondary data, and the reader logs it.

| Emission factor | Why it is empty | What would fill it |
|---|---|---|
| `PET_FILM_CONVERSION` | No public source found for PET film extrusion and biaxial stretching | A licensed LCA database or a published film study |
| `LINER_SILICONE` | No public source found for a silicone-coated release liner | A licensed LCA database, supplier data or an industry study |

While either factor is a placeholder, results must be labelled `DRAFT — contains placeholders`.

## Weak factors (sourced, but a poor fit)

| Factor | Weakness |
|---|---|
| `PET_RESIN_VIRGIN`, `PET_RESIN_RECYCLED` | US data. The European PET eco-profile's server refused the connection when checked on 2026-10-30 |
| `ADHESIVE_ACRYLIC` | Midpoint of a 1-3 kg CO2e/kg range from 2014, not a published value |
| `BOX_CORRUGATED` | Source boundary is cradle-to-grave, while this study is cradle-to-gate |
| `PE_LDPE` | Resin only; making the bag is missing |
| `PALLET_WOOD` | Chilean case study; biogenic treatment not stated |
| `NG_*`, `HGV_*` | UK factors used as a proxy for Germany |
| `EL_DE_WIND` | Value read from a report of the UBA study, not the study itself |
| `WASTE_INCIN_PET` | Own calculation for pure PET, used for mixed laminate scrap |

## GWP basis

The plan's target is IPCC AR6 GWP100, but the sources do not share one basis: DESNZ uses AR4/AR5,
Plastics Europe uses IPCC 2021, and several sources do not state a basis or were not verified. Values
are used as published and not converted, because the gas-by-gas data needed is not available for all.

DQR scores in `emission_factors.csv` are the author's judgement, not values from the sources.

## Representative values (mock, not measured)

These describe a plausible converting operation. They do not come from a real company or a
published source, and they are not emission factors.

- BOM quantities and part mass (`bom_export_sap_mock.csv`, `product_pet_diecut.yaml`)
- Material properties: film density and thickness, liner grammage, mass per piece (`product_pet_diecut.yaml`)
- Machine power, throughput, utilisation and scrap rates (`routing_energy_mock.csv`)
- Transport distances (`transport_legs.csv`)
- Supplier names, which are fictional (`suppliers.csv`)
