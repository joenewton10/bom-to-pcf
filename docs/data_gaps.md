# Data gaps

Every placeholder and representative value in the project is listed here.

## Placeholders (no value yet)

| Item | Where | Status |
|---|---|---|
| Supplier PCF for PET film (SUP-001) | `data/input/supplier_pcf.json` | `pcf_value`, `primary_data_share` and `dqr` are null |
| Supplier PCF for adhesive (SUP-002) | `data/input/supplier_pcf.json` | Same. This record is also deliberately expired, to exercise the fallback |

While these are placeholders, both materials fall back to secondary data, and the reader logs it.

No emission factor is currently a placeholder. Any factor that becomes one must be listed here, and
results using it are labelled `DRAFT — contains placeholders`.

## Proxies (built from sourced values, not published factors)

No public factor was found for these two materials, so each is calculated. See `SOURCES.md`.

| Factor | How it is built | Why it is weak | What would replace it |
|---|---|---|---|
| `PET_FILM_CONVERSION` | Generic extrusion electricity × German grid | Leaves out stretching and heat-setting, and any heat use, so it is likely too low | Film supplier data or a licensed LCA database |
| `LINER_SILICONE` | Sack kraft paper plus an assumed silicone coat | Different paper grade, no coating energy, and the coat weight is an assumption | Liner supplier data or a licensed LCA database |

## Inside the boundary but not modelled

- Site heating: the routing data has no heating use.
- Making the PE bag: only the LDPE resin is counted.

These are listed in `config/method.yaml` and reported with every result.

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

## Differences from PACT Methodology 3.0

- **Electricity:** PACT requires the market-based method, allowing location-based only where no
  contractual instruments exist (section 3.3.2.3). `EL_DE_GRID` is a national average mix, because no
  German residual mix factor has been sourced.
- **Waste with energy recovery:** under the cut-off approach, those emissions go to the energy user
  (section 3.3.2.2). `WASTE_INCIN_PET` assumes no energy recovery, so it may overstate scrap treatment.
- **Packaging:** PACT wants packaging reported separately. It is shown as its own stage, but the
  headline includes it.

## Uncertainty ranges (assumed)

The sources do not publish uncertainty ranges. The spreads in `config/analysis.yaml` are the author's
assumptions: a coefficient of variation from 5% at DQR 1 to 50% at DQR 5, and 5% on inventory
quantities. The P5 to P95 range shows how much weak data could matter. It is not a statistical
confidence interval.

## PACT export

- `pcfIncludingBiogenicUptake` equals the value excluding it, because biogenic carbon is not modelled
  separately. The cardboard, liner paper and pallet do contain biogenic carbon.
- `fossilCarbonContent` covers PET film only, from its chemical formula. Adhesive and liner silicone are
  left out, so it is too low.
- `fossilGhgEmissions` is the whole PCF, because sources do not separate fossil from other emissions.
- `ipccCharacterizationFactors` lists AR6, AR5 and AR4, the reports the sources are known or likely to
  use. Several sources do not state a basis.
- `companyIds` and `productIds` use example URNs for a fictional company.

## GWP basis

The plan's target is IPCC AR6 GWP100, but the sources do not share one basis: DESNZ uses AR4/AR5,
Plastics Europe uses IPCC 2021, and several sources do not state a basis or were not verified. Values
are used as published and not converted, because the gas-by-gas data needed is not available for all.

DQR scores in `emission_factors.csv` are the author's reading of the PACT Methodology 3.0 quality
matrix (Table 12) for a 2025 reference year, not values from the sources.

## Representative values (mock, not measured)

These describe a plausible converting operation. They do not come from a real company or a
published source, and they are not emission factors.

- BOM quantities and part mass (`bom_export_sap_mock.csv`, `product_pet_diecut.yaml`)
- Material properties: film density and thickness, liner grammage, mass per piece (`product_pet_diecut.yaml`)
- Machine power, throughput, utilisation and scrap rates (`routing_energy_mock.csv`)
- Transport distances (`transport_legs.csv`)
- Machine count for machine-hours overhead allocation (`config/method.yaml`)
- Silicone coat weight in the liner proxy (`data/factors/SOURCES.md`)
- Supplier names, which are fictional (`suppliers.csv`)
