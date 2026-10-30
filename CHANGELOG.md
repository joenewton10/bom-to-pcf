# Changelog

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
