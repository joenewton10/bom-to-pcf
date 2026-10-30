# Regulatory context

Background for this project, checked on 2026-10-30. **This is not legal advice.**

## Digital Product Passport

Regulation (EU) 2024/1781, the Ecodesign for Sustainable Products Regulation (ESPR), defines a digital
product passport as product data that includes the information specified in the applicable delegated act,
accessible through a data carrier ([Article 2](https://eur-lex.europa.eu/eli/reg/2024/1781/oj/eng)).

So what a passport must contain depends on a delegated act for the product group. The project plan treats
requirements for this product group as not yet defined, and that has not been independently confirmed
against the current list of delegated acts.

The data sheet here shows the style of a passport. It has no data carrier and follows no delegated act, so
it is not a passport under the ESPR.

## Environmental claims

See [claims_check.md](claims_check.md) for Directive (EU) 2024/825 and the Green Claims Directive proposal.

## Data exchange

The export follows the PACT Technical Specification, version 3.0.3, and is validated against the official
schema pinned in `schemas/pact/`. The schema comes from the
[WBCSD data-exchange-protocol repository](https://github.com/wbcsd/data-exchange-protocol), tag `v3.0.3`.
Passing the schema shows the file's structure is right. It does not show the PCF is correct or verified.
