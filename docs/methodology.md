# Methodology

This describes what the tool does today. All data is representative and results are illustrative.
This is not a verified PCF.

## Standards

| Document | Version | How it was used |
|---|---|---|
| PACT Methodology | 3.0 (2025) | Read directly. Sections are cited below |
| TfS PCF Guideline | 3.0 (December 2024) | Read directly. Sections are cited below |
| ISO 14067, ISO 14040/44 | 2018; 2006 | Not read, because they are paid standards. Named as the framework only, with no clauses cited |
| GHG Protocol Product Standard | 2011 | Not read directly. Named as the framework only |

The PACT Methodology was read from a third-party copy of Version 3.0, because the official page gave no
direct download. The official page is <https://www.wbcsd.org/resources/pact-methodology-version-3/>.
The TfS Guideline is at <https://www.tfs-initiative.com/pcf-guideline>.

## Goal and scope

- **Product:** die-cut PET film insulation part, from a contract converting operation.
- **Declared unit:** 1 kg of finished parts, also reported per 1,000 parts.
- **Boundary:** cradle-to-gate (PACT 3.2). Includes materials, inbound transport, converting energy, site
  overhead, scrap treatment and packaging. Excludes use, end of life, capital goods and commuting
  (PACT Table 3).
- **Geography and time:** Germany, reference year 2025.

## Calculation

Each inventory quantity per kg of product is multiplied by its emission factor.

- **Mass:** working back from 1 kg of product, the mass entering each step is the output divided by
  (1 − scrap rate).
- **Energy:** kWh per kg = power × utilisation / throughput, multiplied by the mass through the step.
- **Transport:** tonne-km from the BOM mass and leg distance, with both tank-to-wheel and upstream fuel
  factors, because PACT asks for well-to-wheel emissions (Table 3).

## Method choices

Set in `config/method.yaml`.

| Topic | What the tool does | Basis |
|---|---|---|
| Scrap to recycling | Cut-off: no burden, no credit | PACT 3.3.2.2 |
| Avoided emissions | Never in a final result. The substitution option keeps a result in draft | PACT 3.3.2.2: avoided emissions shall not be included |
| Scrap to incineration | Charged to the product | PACT 3.3.2.2. Assumes no energy recovery, see below |
| Site overhead | By mass of output, or machine hours | The tool's own choice, not taken from either document |
| Exclusions | Nothing with available data is left out | TfS 5.2.3: where quantitative data are available, they shall be included |
| Limit on exclusions | 3% of the PCF, if the rule is ever switched on | PACT 3.3.1.2, reduced from 5% in Version 2 |
| Supplier PCF age | 3 years at most | PACT Table 3; TfS 5.2.2 |
| Mass balance | Unexplained mass within 1% of inputs | The tool's own check, not taken from either document |

## Primary data share

An input is primary only if both its activity data and its emission factor are primary (PACT 4.2.2 and
Table 9; TfS 5.2.11.1). The share for the product is the impact-weighted average of its inputs.

| Input | Share counted |
|---|---|
| Site's own kWh × a database factor | 0% |
| Supplier PCF with a stated share | The supplier's share |
| Supplier PCF with no stated share | 0% (PACT 4.2.2), and reported as unknown |
| Database material factor | 0% |

So the demo scores 0% until supplier data is added. That is expected, not an error: site quantities are
primary activity data, but they use database emission factors.

The project plan defined the share as coming from "supplier or site" data. Site data still counts, but
only when its emission factor is primary too.

## Data quality

Technology, geography and time are each scored from 1 (best) to 5 (worst) using the PACT matrix (Table
12), and weighted by impact (PACT 4.2.3). Secondary data can score 3 at best on technology. A supplier PCF
with no DQR scores 5 (PACT 4.2.3). PACT requires DQR from 2027.

The scores on secondary factors are the author's reading of the matrix.

## GWP

PACT asks for 100-year GWP from the latest IPCC Assessment Report (3.3.1). The target is AR6, but the
sources do not share one basis, and values are used as published. See [data_gaps.md](data_gaps.md).
Biogenic carbon is left out of the headline where the source separates it.

## Scenarios and sensitivity

Scenarios and sliders use one set of levers in `config/scenarios/`: renewable share of electricity,
recycled share of PET resin, and a scrap multiplier. More scrap also raises product material by the
same ratio, so the mass still balances. Scenarios never change saved data. A green electricity claim
would need a contractual instrument under PACT (3.3.2.3).

## Uncertainty

Monte Carlo with 1,000 runs by default and an optional fixed seed, reporting P5, P50 and P95. Each
factor and inventory quantity gets a lognormal multiplier with a mean of 1. Lines sharing a factor
share its draw, because an error in a factor affects them together. The spreads are assumptions,
see [data_gaps.md](data_gaps.md).

## Product family

One parameterised model covers film thickness, adhesive and recycled share. Film mass follows
thickness, and part mass follows the product material. It assumes the same part area and scrap rates,
and energy per kg that does not change with thickness. Removing the adhesive also removes the liner.
Thin film may in reality run differently, so results at the ends of the range are less reliable.

## When a result is a draft

A result is a draft if it uses placeholder factors, has flows that could not be modelled, has
unreviewed material matches, fails the mass balance, has input errors, or uses a substitution credit.
If data is missing, the label also says the total is partial and the true footprint is higher.

See [data_gaps.md](data_gaps.md) for placeholders, proxies, weak factors and known differences from PACT.
