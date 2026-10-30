# Changelog

## Phase 4 — Inventory & calculation engine

- Mass balance check, inventory builder and Python engine, with results per kg and per 1,000 pieces.
- Allocation: recycling cut-off or substitution; site overhead by mass or machine hours.
- Cut-off rule with a reported exclusion list and share, data quality aggregation, primary data share.
- Results with missing data are labelled as a partial total, so they cannot be read as complete.
- Hand-calculated reference case in `tests/fixtures/reference_case.yaml`.
- Factor mappings in `data/mappings/bom_to_dataset.csv`, all unreviewed until Phase 6.
- `pcf run` command.

## Phase 3 — Emission factors & sources

- `emission_factors.csv` with 13 sourced factors and 2 placeholders; `SOURCES.md` says where each
  value was read.
- `io/factor_store.py` rejects any non-placeholder factor without a value and a listed source.
- `docs/data_gaps.md` lists placeholders, weak factors and the mixed GWP basis.

## Phase 2 — Data models & input readers

- Owner decision: PET die-cut part only; no second product for now.
- Pydantic models, product config, and readers for the BOM, routing, suppliers, supplier PCFs and
  transport legs, plus checks across files and a clean issues table.
- BOM reader handles German decimals, mixed units (including m² → kg), duplicates, missing suppliers
  and obsolete dates. Every change or doubt is logged as an issue.
- Mock inputs and a matching `data/demo/` set. Supplier PCF values are marked placeholders and
  logged in `docs/data_gaps.md`, so no carbon numbers were invented.
- `pcf validate-inputs` command.

## Phase 1 — Scaffold

- Repository structure from `PROJECT_PLAN.md` §3 (folders and packages; modules arrive in their phases).
- Packaging with `pyproject.toml`, including `llm`, `openlca` and `dev` extras, and `requirements.txt`
  for Streamlit Community Cloud.
- Ruff, pytest, pre-commit and a GitHub Actions workflow testing Python 3.11 and 3.14.
- Placeholder Streamlit app and `pcf` CLI, each covered by a smoke test.
- Plotly chosen as the charting library.
