# Changelog

## Method checked against PACT 3.0 and TfS 3.0

- Primary data share: an input is primary only if its activity data and emission factor both are. Site quantities multiplied by database factors now count as 0%.
- An unknown supplier DQR now scores 5.
- Cut-off: nothing with available data is left out by default, and the total limit is 3%, not 5%.
- Factor quality scores redone against the PACT matrix.
- The substitution credit keeps a result in draft, because PACT does not allow avoided emissions.
- `docs/methodology.md` now cites sections of both documents.

## After Phase 7

- Primary data share now uses the supplier's stated share. A PCF with no stated share is not counted as primary and is reported as unknown.
- Start fresh button; locally it archives the database instead of deleting it.
- The app re-reads saved data on every page run, so browser tabs no longer go stale.

## Phase 7 — Primary data, storage & audit

- Supplier PCFs by form or file, checked against unit, age, method, boundary and plausibility rules.
- Accepted data replaces the database value with a new version; undo returns to any earlier version exactly.
- Before-and-after comparison, append-only audit trail and rejected submissions with reasons.
- SQLite locally and session storage when hosted, chosen from the visited address; progress file to save and restore.
- Review decisions and the review log now persist too. `docs/primary_data_workflow.md`.

## Start here wording

- With the owner's approval, "Nothing is used until a person approves it" became "Nothing counts in a final result until a person approves it", because drafts use unreviewed matches provisionally.

## Phase 6 — Matching & review

- Text matching against `data/mappings/candidates.yaml`, top 3 with scores; a candidate can stand for several factors.
- Optional AI suggestions, off by default, with a session call limit and fallback to text matching.
- Match & review page with approve, reject, choose other and comments; append-only review log with download.
- Final results need a decision on every material. Rejected materials become reported gaps.
- `docs/ai_validation.md`.

## Phase 5 — Streamlit core

- App shell with sidebar progress, disclaimer and the Start here page exactly as written in the plan (a test compares it to the plan).
- Try the demo opens a full breakdown in one click. Upload & validate shows issues and the mass balance. Results shows the headline, breakdowns, draft reasons, omissions, cut-off list and a traceable inventory.
- `docs/methodology.md`, describing the method as built; clause-level citations still to come.
- Links on Start here for pages not built yet are disabled until their phases.

## Factor update after Phase 4

- `PET_FILM_CONVERSION` and `LINER_SILICONE` are now labelled proxies built from sourced values, with
  the worst technology score. No emission factor is a placeholder now; supplier PCFs still are.

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
