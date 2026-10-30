# Changelog

## Phase 1 — Scaffold

- Repository structure from `PROJECT_PLAN.md` §3 (folders and packages; modules arrive in their phases).
- Packaging with `pyproject.toml`, including `llm`, `openlca` and `dev` extras, and `requirements.txt`
  for Streamlit Community Cloud.
- Ruff, pytest, pre-commit and a GitHub Actions workflow testing Python 3.11 and 3.14.
- Placeholder Streamlit app and `pcf` CLI, each covered by a smoke test.
- Plotly chosen as the charting library.
