# Methodology

This describes what the tool does today. All data is representative and results are illustrative.
This is not a verified PCF. Clause-level citations of each standard, and a check of the latest TfS
and PACT versions, are still to be added.

## Standards

The method is designed around ISO 14067, ISO 14040/44, the GHG Protocol Product Standard, the TfS PCF
Guideline and the PACT Methodology.

## Goal and scope

- **Product:** die-cut PET film insulation part, from a contract converting operation.
- **Declared unit:** 1 kg of finished parts, also reported per 1,000 parts.
- **Boundary:** cradle-to-gate. Includes materials, inbound transport, converting energy, site
  overhead, scrap treatment and packaging. Excludes use, end of life, capital goods and commuting.
- **Geography and time:** Germany, reference year 2025.

## Calculation

Each inventory quantity per kg of product is multiplied by its emission factor.

- **Mass:** working back from 1 kg of product, the mass entering each step is the output divided by
  (1 − scrap rate).
- **Energy:** kWh per kg = power × utilisation / throughput, multiplied by the mass through the step.
- **Transport:** tonne-km from the BOM mass and leg distance. Both the tank-to-wheel and upstream fuel
  factors are used.

## Method choices

Set in `config/method.yaml`.

| Topic | Default | Alternative |
|---|---|---|
| Scrap to recycling | Cut-off: no burden, no credit | Substitution of virgin material |
| Scrap to incineration | Charged to the product, no energy credit | None |
| Site overhead | By mass of output | By machine hours |
| Cut-off | Leave out an item below 1% of both mass and impact, up to 5% of impact in total; always listed | Configurable |
| Mass balance | Unexplained mass must be within 1% of inputs | Configurable |

## Data quality and primary data

- **DQR:** technology, geography and time, each from 1 (best) to 5 (worst), weighted by impact. Scores
  on secondary factors are the author's judgement.
- **Primary data share:** the share of impact from supplier PCFs or quantities from the site.

## GWP

The target is IPCC AR6 GWP100, but sources do not share one basis, and values are used as published.
Biogenic carbon is left out of the headline where the source separates it.

## When a result is a draft

A result is a draft if it uses placeholder factors, has flows that could not be modelled, has
unreviewed material matches, fails the mass balance, or has input errors. If data is missing, the
label also says the total is partial and the true footprint is higher.

See [data_gaps.md](data_gaps.md) for placeholders, proxies and weak factors.
