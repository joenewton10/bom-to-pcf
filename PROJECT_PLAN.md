# PROJECT_PLAN.md — `bom-to-pcf`: Automated Cradle-to-Gate Product Carbon Footprint Tool

> **For Claude Code:** This file is the full brief. Read it completely before writing code.
> Work phase by phase (§12). At the end of each phase, run the tests, update `CHANGELOG.md`,
> commit with a clear message, and stop to summarise what was done and what is next.
> Do not skip the acceptance criteria. Ask before making decisions marked **[ASK]**.
> Text marked **[VERBATIM]** was written by the owner — use it exactly as written.

---

## 0. Purpose and audience

**Owner:** Joseph Newton (GitHub: `joenewton10`)
**Goal:** A portfolio project demonstrating automated, standards-aligned product carbon
footprint (PCF) calculation for an industrial converted product, aimed at LCA/PCF roles in
chemicals and materials companies (e.g. LCA Manager, Digitalization & Product Sustainability).

**Primary interface:** a Streamlit web app, deployable on Streamlit Community Cloud so
recruiters can try it from a link. All calculation logic lives in `src/bom_to_pcf/`;
the app only calls the engine. A minimal CLI exists for testing and batch runs.

**What it must demonstrate (mapped to typical job requirements):**

| Requirement | How the project shows it |
|---|---|
| ISO 14067 / ISO 14040/44 methodology | Documented goal & scope, system boundary, allocation, cut-off, data quality |
| TfS PCF Guideline, GHG Protocol Product Standard | Method choices follow and cite these; primary data share reported |
| BOM / ERP / supplier data integration | Input is a mock SAP-style BOM export + supplier PCF files |
| Supplier PCF, Scope 3.1, automated LCI data collection | Supplier priority ranking, data request templates, status tracker, primary data replacement |
| Mass & energy balance, LCI | Per-step inventory with automated mass balance check |
| Standardised, parameterised, scalable models | YAML scenarios, sensitivity runs, product-variant batch calculation |
| Python, APIs, LCA software | Pure-Python engine + optional openLCA backend via `olca-ipc` |
| AI with expert validation | LLM-assisted BOM-to-dataset matching with human approval and audit log |
| PACT / data exchange | Output and supplier requests in PACT Technical Specification JSON, schema-validated |
| ESPR / Digital Product Passport | DPP-style product sustainability data sheet per product |
| Credible environmental claims | Claims check that flags supported vs. unsupported claims before export |

**Honesty rule (non-negotiable):** All process data is *representative*, not real company data.
Every emission factor must have a cited public source. Never invent a number. If a value
is unknown, insert a clearly marked placeholder (`value: null`, `status: "PLACEHOLDER"`) and
list it in `docs/data_gaps.md`. The README and the app's Start here page must state that
results are illustrative. Do not name any real company as the data source.

---

## 1. Case study definition

**Product:** Die-cut PET film insulation part (generic industrial component, e.g. for
electronics or e-mobility), produced by a contract converting operation.

**Declared unit:** 1 kg of finished die-cut parts (also report per 1,000 pieces using a
configurable part mass).

**System boundary:** Cradle-to-gate.
- Raw material extraction and production (PET film, adhesive, release liner)
- Inbound transport of materials to the converter
- Converting processes: slitting → die-cutting/laminating → inspection → packaging
- Energy use (electricity, heating) at the converting site
- Production scrap: treatment of process waste (recycling vs. incineration scenarios)
- Packaging materials
- **Excluded:** use phase, end of life of the product, capital goods, employee commuting
  (document as per ISO 14067 / TfS cut-off rules)

**Geography / time:** Germany, reference year configurable (default 2025).

**Product family (for variant batch runs):** film thickness 25–250 µm, with/without
adhesive, virgin vs. recycled PET share.

**[ASK]** before Phase 2: confirm product choice and whether a second product
(e.g. PMMA sheet cut parts) should be added for comparison.

---

## 2. Tech stack

- Python 3.11+
- `streamlit` (primary UI; use multipage app with `st.navigation`/`st.Page` or the `pages/` convention — check current Streamlit docs)
- `pydantic` (data models + validation), `pyyaml` (config), `pandas`
- `plotly` or `altair` for charts (pick one, use it consistently); `st.graphviz_chart` for the flow diagram
- `typer` (minimal CLI), `rich`
- `jsonschema` (PACT validation)
- `rapidfuzz` (non-AI fallback matching)
- `anthropic` (optional LLM matching; key from env var or `st.secrets`, never committed)
- `olca-ipc` + `olca-schema` (optional openLCA 2.x backend)
- `jinja2` (DPP sheet, supplier request and report templates)
- `sqlite3` (standard library) for local persistence
- `pytest`, `pytest-cov`, `ruff`, `pre-commit`
- Packaging: `pyproject.toml`, installable with `pip install -e .`; `requirements.txt` for Streamlit Cloud

The core engine must run **without** openLCA and **without** an API key, so tests, CI and
the hosted app work anywhere. Optional backends are plug-ins that switch off gracefully.

---

## 3. Repository structure

```
bom-to-pcf/
├── README.md
├── PROJECT_PLAN.md
├── CLAUDE.md
├── CHANGELOG.md
├── pyproject.toml
├── requirements.txt              # for Streamlit Community Cloud
├── .streamlit/
│   ├── config.toml               # theme
│   └── secrets.toml.example      # never commit real secrets
├── .github/workflows/ci.yml      # ruff + pytest
├── app/
│   ├── Home.py                   # entry point → Start here page
│   ├── state.py                  # session state keys, progress checklist helpers
│   ├── components.py             # shared UI pieces (sidebar progress, step cards, disclaimers)
│   └── pages/
│       ├── 0_Start_here.py
│       ├── 1_Upload_and_validate.py
│       ├── 2_Match_and_review.py
│       ├── 3_Results.py
│       ├── 4_Hotspots_and_priorities.py
│       ├── 5_Supplier_requests.py
│       ├── 6_Primary_data.py
│       ├── 7_Scenarios_and_variants.py
│       └── 8_Export_and_claims.py
├── config/
│   ├── product_pet_diecut.yaml
│   ├── method.yaml               # GWP set (IPCC AR6 GWP100), allocation, cut-off
│   ├── claims_rules.yaml         # claims check rules (§9.4)
│   ├── variants_pet_family.yaml  # product family definition (§9.3)
│   └── scenarios/
│       ├── baseline.yaml
│       ├── green_electricity.yaml
│       ├── recycled_pet.yaml
│       └── high_scrap.yaml
├── data/
│   ├── input/
│   │   ├── bom_export_sap_mock.csv
│   │   ├── routing_energy_mock.csv
│   │   ├── supplier_pcf.json
│   │   ├── suppliers.csv               # supplier master data (mock)
│   │   └── transport_legs.csv
│   ├── demo/                           # complete demo set loaded by "Try the demo"
│   ├── factors/
│   │   ├── emission_factors.csv
│   │   └── SOURCES.md
│   └── mappings/
│       ├── bom_to_dataset.csv
│       └── review_log.csv
├── src/bom_to_pcf/
│   ├── models.py
│   ├── io/
│   │   ├── bom_reader.py
│   │   ├── supplier_reader.py
│   │   └── factor_store.py
│   ├── inventory/
│   │   ├── mass_balance.py
│   │   └── lci_builder.py
│   ├── matching/
│   │   ├── fuzzy_matcher.py
│   │   ├── llm_matcher.py
│   │   └── review.py               # review logic used by both app and CLI
│   ├── engine/
│   │   ├── base.py
│   │   ├── python_engine.py
│   │   └── openlca_engine.py
│   ├── methods/
│   │   ├── allocation.py
│   │   ├── data_quality.py
│   │   └── primary_share.py
│   ├── primary_data/
│   │   ├── validation.py           # checks for incoming supplier PCFs (§8)
│   │   └── replacement.py          # swap secondary → primary, before/after diff
│   ├── storage/
│   │   ├── base.py                 # StorageBackend interface
│   │   ├── sqlite_store.py         # local default
│   │   └── session_store.py        # hosted fallback (session + download/upload)
│   ├── suppliers/
│   │   ├── priority.py             # supplier priority ranking (§9.1)
│   │   └── requests.py             # data request templates + status tracker (§9.2)
│   ├── variants.py                 # product-family batch runs (§9.3)
│   ├── claims.py                   # claims check (§9.4)
│   ├── scenarios.py
│   ├── outputs/
│   │   ├── pact_export.py
│   │   ├── dpp_sheet.py
│   │   └── report.py
│   └── cli.py
├── schemas/pact/                   # official PACT JSON schema, version-pinned
├── templates/
│   ├── dpp_sheet.html.j2
│   ├── supplier_request.md.j2
│   └── report.md.j2
├── outputs/examples/
├── docs/
│   ├── goal_and_scope.md
│   ├── methodology.md
│   ├── data_gaps.md
│   ├── ai_validation.md
│   ├── primary_data_workflow.md
│   ├── claims_check.md
│   ├── regulatory_context.md
│   └── portfolio_summary.md
└── tests/
    ├── test_bom_reader.py
    ├── test_mass_balance.py
    ├── test_engine.py
    ├── test_allocation.py
    ├── test_primary_share.py
    ├── test_primary_data_validation.py
    ├── test_replacement.py
    ├── test_storage.py
    ├── test_priority.py
    ├── test_requests.py
    ├── test_variants.py
    ├── test_claims.py
    ├── test_pact_export.py
    ├── test_scenarios.py
    ├── test_app_smoke.py           # Streamlit AppTest: every page loads with demo data
    └── fixtures/
```

---

## 4. Data specifications

### 4.1 SAP-style BOM export (`bom_export_sap_mock.csv`)
Mimic a flattened SAP CS11/CS12 export. Columns:
```
material_number, material_description, parent_material, bom_level, component_qty,
uom, base_qty, base_uom, item_category, plant, valid_from, supplier_id
```
- Include realistic quirks: German decimal commas in some rows, mixed units (`KG`, `G`,
  `M2`, `ST`), one duplicate line, one component with missing supplier, one obsolete
  `valid_from`. The reader must normalise, flag and log these.
- Materials: PET film (m² → kg via density × thickness), acrylic adhesive, silicone release
  liner, cardboard box, PE bag, pallet share.

### 4.2 Routing & energy (`routing_energy_mock.csv`)
```
step_id, step_name, machine, throughput_kg_per_h, power_kw, utilisation,
scrap_rate, scrap_destination
```
Energy per kg = power × utilisation / throughput. Steps: slitting, die-cutting,
laminating, inspection, packaging, plus a site overhead line allocated per kg output.

### 4.3 Supplier PCF (`supplier_pcf.json`) and suppliers (`suppliers.csv`)
- Two suppliers provide primary PCFs (PET film, adhesive) in a simplified PACT-like structure.
  One record is deliberately incomplete or expired → falls back to secondary data, logged.
- `suppliers.csv`: `supplier_id, name (fictional), country, contact_role, materials_supplied`.
  Use clearly fictional supplier names.

### 4.4 Emission factors (`emission_factors.csv`)
```
factor_id, name, value, unit, gwp_basis, geography, reference_year, source_id,
data_type (secondary|primary), dqr_tech, dqr_geo, dqr_time, notes, status
```
- Every non-placeholder value must have a `source_id` listed in `SOURCES.md`.
- Acceptable public sources (verify current versions and values; do not rely on memory):
  German grid electricity (Umweltbundesamt), fuels and transport (UK DESNZ conversion
  factors, GLEC Framework), polymers (PlasticsEurope eco-profiles where public),
  packaging (published LCA datasets).
- Unverifiable values → `status: PLACEHOLDER`, `value: null`, listed in `docs/data_gaps.md`.
  The engine must label results `DRAFT — contains placeholders` while any are in use.

---

## 5. Methodology requirements (`docs/methodology.md`)

- **Standards:** ISO 14067:2018, ISO 14040/14044, GHG Protocol Product Standard,
  TfS PCF Guideline (latest version — check), PACT Methodology. Cite each choice.
- **GWP:** IPCC AR6 GWP100 (configurable). Report fossil, biogenic (if any) and land-use
  change separately where data allows; headline = total excluding biogenic.
- **Allocation:** Production scrap to recycling → cut-off approach (no credit), alternative
  configurable and documented. Site overheads → by mass output (configurable to machine hours).
- **Cut-off:** Exclude flows < 1% of mass or impact, total excluded < 5% (configurable),
  excluded list reported.
- **Data quality:** DQR per TfS/PACT dimensions, aggregated per result.
- **Primary data share:** % of total PCF from primary (supplier or site) data.
- **Uncertainty:** Monte Carlo (default n = 1,000, fixed seed option) or ± ranges; report P5–P95.

---

## 6. AI-assisted matching with expert validation

1. `fuzzy_matcher` proposes top-3 matches with similarity scores (always runs).
2. If an API key is available and the user enables it, `llm_matcher` sends only the BOM
   description, unit and candidate list (no prices, no supplier names) and returns a ranked
   suggestion, rationale and confidence as structured JSON.
3. On the **Match & review** page, suggestions appear in an `st.data_editor` table with
   approve / reject / choose-other columns and a comment field.
4. Every decision is written to the review log:
   `timestamp, bom_item, suggestion, source (fuzzy|llm), confidence, decision, reviewer, comment`
5. Only approved mappings are used. Unreviewed items block a final (non-draft) result.
6. On the hosted app, LLM matching is off by default; if enabled with the owner's key,
   apply a per-session call limit.

Document governance in `docs/ai_validation.md`.

---

## 7. Streamlit app specification

### 7.1 General
- Multipage app, wide layout, consistent theme in `.streamlit/config.toml`.
- **Sidebar on every page:** progress checklist driven by session state —
  Data uploaded · Inputs validated · Matches reviewed · PCF calculated · Hotspots checked ·
  Primary data added · Exported. Ticks update automatically.
- **Disclaimer banner** (small, every results-type page): "Illustrative data — not a verified PCF."
- Results cached with `st.cache_data`, keyed on input hashes; recalculation triggered by any
  change to inputs, mappings, primary data or parameters.
- Graceful degradation: openLCA backend and LLM options only appear when available, with a
  short note explaining why when they are not.

### 7.2 Pages

| Page | What it does |
|---|---|
| 0 Start here | Landing page — see §10 for full text and layout |
| 1 Upload & validate | Upload BOM, routing, supplier files (or use demo); issues table; mass balance check |
| 2 Match & review | Fuzzy/LLM suggestions in an editable table; approve/reject; review log view |
| 3 Results | Headline PCF (per kg, per 1,000 pcs), breakdown by stage and material, primary data share, DQR, draft flag |
| 4 Hotspots & priorities | Contribution chart; supplier priority ranking (§9.1) |
| 5 Supplier requests | Generate data requests; status tracker (§9.2) |
| 6 Primary data | Upload/enter supplier PCFs, validate, replace, before/after, audit history (§8) |
| 7 Scenarios & variants | Scenario comparison, sensitivity sliders, Monte Carlo, product-family batch (§9.3) |
| 8 Export & claims | Claims check (§9.4); download PACT JSON, DPP sheet, report, review log, audit log |

---

## 8. Primary data workflow

**Goal:** start with secondary (database) data and replace it with supplier primary data
as it arrives, with every change validated, traceable and reversible.

### 8.1 Input
- Upload a supplier PCF (PACT-like JSON or CSV), or enter it in a form:
  `supplier_id, material_number, pcf_value, declared_unit, reference_period_start/end,
  method (ISO 14067 | TfS | PACT | other), primary_data_share, dqr, boundary, notes`.

### 8.2 Validation (`primary_data/validation.py`)
A submission is accepted only if:
- the declared unit converts to the BOM unit (else rejected with reason),
- the reference period has not expired (configurable max age, default 3 years),
- the method is stated and the boundary is cradle-to-gate (or compatible),
- the value is within a plausibility range vs. the secondary factor (configurable, default
  0.2×–5×); outside → accepted only with a mandatory reviewer comment.
Rejected submissions keep the secondary value in use and are shown with reasons.

### 8.3 Replacement & recalculation (`primary_data/replacement.py`)
- Accepted primary data overrides the secondary factor for that material/supplier.
- Results recalculate automatically.
- **Before/after panel:** PCF, primary data share and DQR, old vs. new, with delta.
- Any replacement can be reverted to a previous version.

### 8.4 Audit trail
Every change logged: `timestamp, user, material, supplier, field, old_value, new_value,
reason, version_id`. History is never overwritten. Viewable and downloadable in the app.

### 8.5 Persistence (`storage/`)
- `StorageBackend` interface with two implementations:
  - `SQLiteStore` — default when running locally (`data/app.db`, git-ignored).
  - `SessionStore` — used on Streamlit Community Cloud: data lives in session state; the
    user downloads the updated supplier data + audit log (one ZIP or JSON) and re-uploads it
    next session. The Primary data page explains this clearly.
- Backend chosen by environment/config, so a hosted database could be added later without
  touching app code. **Do not** write back to the GitHub repo from the app.

---

## 9. Additional features

### 9.1 Supplier priority ranking (`suppliers/priority.py`)
- Priority score per material = contribution to PCF (share) × data-quality gap
  (`1 − normalised DQR`, where secondary generic data scores low quality).
- Show a ranked table: material, supplier, contribution %, current data type, DQR,
  priority score, and "potential PCF uncertainty reduced if primary data obtained".
- Highlight the top 3 with a short plain-language recommendation, e.g.
  "Ask Supplier A for PET film data first — it drives 41% of the footprint and uses generic data."
- Weighting configurable in YAML; document the logic in `docs/primary_data_workflow.md`.

### 9.2 Supplier data requests & status tracker (`suppliers/requests.py`)
- From the priority table, select suppliers and generate a data request per supplier:
  a short cover message (Markdown, from `templates/supplier_request.md.j2`) plus a
  pre-filled PACT-style JSON/CSV template listing the materials, declared unit, required
  fields, reference period and requested method.
- Downloadable individually or as a ZIP. The app does **not** send emails.
- Status tracker per supplier/material: `not requested → requested → received → validated | rejected`,
  with dates and notes. Status updates automatically to *received/validated/rejected* when
  primary data is submitted on the Primary data page.
- Summary metric: % of PCF covered by validated primary data.

### 9.3 Product variants batch (`variants.py`)
- One parameterised model, defined in `config/variants_pet_family.yaml`
  (thickness list, adhesive yes/no, recycled share list).
- Batch-calculate all combinations; table + chart of PCF per variant (per kg and per 1,000 pcs).
- Downloadable as CSV; optional PACT export per variant.
- Must run the full default family (≥ 20 variants) in under 10 seconds with the Python engine.

### 9.4 Environmental claims check (`claims.py`)
- Before export, the user picks or types the claim they want to make.
- Rules in `config/claims_rules.yaml`, e.g.:
  - ✅ Supported: "X kg CO₂e per kg, cradle-to-gate, calculated per ISO 14067" (when result is non-draft).
  - ⚠️ Needs more: comparative claims ("20% lower than…") → require a documented benchmark
    with the same boundary and method.
  - ❌ Not supported: "climate neutral", "CO₂-neutral", "eco-friendly", "green" and similar
    generic or offset-based claims.
  - ❌ Blocked whenever the result is a draft (placeholders or unreviewed mappings).
- Each verdict shows a one-line reason.
- **Verify the current EU legal basis before writing rules** — the Empowering Consumers for the
  Green Transition Directive (EU) 2024/825 and the status of the proposed Green Claims
  Directive. Cite in `docs/claims_check.md`, and state that this is a guidance aid, not legal advice.

---

## 10. Start here page — content **[VERBATIM]**

Use this text exactly. Layout notes are in *italics* and are instructions, not text to display.

---

*Title*
# From bill of materials to product carbon footprint

*Intro paragraph (first person, owner's voice)*

I built this tool to show how a product carbon footprint can be calculated automatically
from the data a manufacturer already has: a bill of materials, production steps and energy
use. It follows ISO 14067 and the TfS PCF Guideline, and it's designed to get better over
time. You start with database values, and as suppliers send their real data, the footprint
becomes more accurate and more trustworthy.

The example is a die-cut PET film part, based on the kind of precision converting work I
see every day. All numbers are illustrative, but the method is the real thing.

*Primary button, prominent*
**▶ Try the demo** — *loads `data/demo/` into session state and opens the Results page*

*Caption under the button*
No files needed. The demo loads a complete example so you can explore every step.

*Section heading*
## How it works

*Flow diagram with `st.graphviz_chart`, left to right, nine boxes:*
*Upload BOM → Validate → Match materials → Review → Calculate PCF → Find hotspots →
Request supplier data → Add primary data → Export*
*Draw a looping arrow from "Add primary data" back to "Calculate PCF", labelled "recalculate".*

*Section heading*
## The steps

*Step cards in a 3-column grid. Each card: number + title, description, "In" and "Out" lines,
and an `st.page_link` button to the page.*

**1. Upload & validate**
Upload a BOM export, production routing and any supplier data. The tool cleans up units,
spots duplicates and checks that the mass balance adds up.
*In:* BOM, routing, supplier files · *Out:* a clean, checked inventory

**2. Match & review**
Each material is matched to an emission factor. Suggestions come from text matching and,
optionally, AI. Nothing counts in a final result until a person approves it.
*In:* material descriptions · *Out:* approved matches with an audit log

**3. Results**
See the carbon footprint per kg and per 1,000 parts, broken down by material and process
step, with the share of primary data and a data quality rating.
*In:* approved inventory · *Out:* the PCF and its breakdown

**4. Hotspots & priorities**
Find out what drives the footprint and which supplier to ask for data first. The ranking
weighs each material's impact against how weak its current data is.
*In:* results · *Out:* a ranked list of where better data matters most

**5. Supplier requests**
Create ready-to-send data requests in a standard format and track each one, from requested
to validated.
*In:* priority list · *Out:* request templates and a status tracker

**6. Primary data**
Add real supplier data when it arrives. It's checked before use, replaces the database
value and recalculates the footprint, with a before-and-after comparison. Every change is
logged and can be undone.
*In:* supplier PCFs · *Out:* an updated, more accurate PCF

**7. Scenarios & variants**
Test what-ifs, like green electricity, recycled PET or higher scrap rates, and calculate a
whole product family in one run.
*In:* model parameters · *Out:* comparisons and sensitivity results

**8. Export & claims**
Check which environmental claims the result can support, then download the PCF in PACT
format, a Digital Product Passport-style data sheet and a full methods report.
*In:* final results · *Out:* PACT JSON, DPP sheet, report

*Section heading*
## How to read the results

*Info box (`st.info`), four short definitions:*

- **Product carbon footprint (PCF):** the greenhouse gas emissions linked to making one unit
  of product, in kg CO₂e.
- **Cradle-to-gate:** everything from raw material extraction up to the product leaving the
  factory. Use and disposal are not included.
- **Primary data share:** how much of the footprint is based on real data from suppliers or
  the site, rather than database averages. Higher is better.
- **Data quality rating (DQR):** a score for how well the data fits the product in terms of
  technology, location and time.

*Expander, collapsed by default*
### Method & limitations

- Standards: ISO 14067, ISO 14040/44, GHG Protocol Product Standard, TfS PCF Guideline, PACT.
- Boundary: cradle-to-gate, declared unit 1 kg of finished parts.
- GWP: IPCC AR6, 100-year.
- All data is representative and illustrative. This is not a verified PCF and should not be
  used for real claims.
- Full details: *link to `docs/methodology.md` on GitHub*

*Footer, small*
Built by Joseph Newton · *GitHub link* · *portfolio site link: joenewton10.github.io*

---

## 11. CLI (minimal)

```
pcf validate-inputs --product config/product_pet_diecut.yaml
pcf run             --product ... --scenario baseline [--backend python|openlca]
pcf variants        --config config/variants_pet_family.yaml
pcf export-pact     --run-id ...
```
Every run writes `outputs/<run_id>/` with input snapshot, config hash, results and logs.

---

## 12. Phases and acceptance criteria

### Phase 1 — Scaffold (½ day)
Repo structure, `pyproject.toml`, `requirements.txt`, ruff, pytest, pre-commit, CI, `CLAUDE.md`,
empty Streamlit app that launches.
✅ `pip install -e .` works; `streamlit run app/Home.py` opens; CI green.

### Phase 2 — Data models & input readers (1 day)
Pydantic models; BOM reader (units, m² → kg, German decimals, duplicates); supplier reader;
all mock inputs (§4) and the `data/demo/` set.
✅ Tests cover every quirk; validation returns a clean issues table.

### Phase 3 — Emission factors & sources (1 day)
Fill `emission_factors.csv` + `SOURCES.md` from public sources only; placeholder mechanism;
`data_gaps.md`.
✅ Test fails if any non-placeholder factor lacks a source.
**[ASK]** Show the factor table to the owner for review before Phase 4.

### Phase 4 — Inventory & calculation engine (1–2 days)
Mass balance, LCI, Python engine, allocation, cut-off, primary data share, DQR.
✅ Hand-calculated reference case in `tests/fixtures/` matches within 0.1%.
✅ Mass balance test fails on deliberately broken input.

### Phase 5 — Streamlit core: Start here, Upload, Results (1–2 days)
App shell, sidebar progress, disclaimer, Start here page exactly as §10, Upload & validate,
Results page, "Try the demo".
✅ A first-time user can click "Try the demo" and see a full PCF breakdown within 3 clicks.
✅ `test_app_smoke.py` (Streamlit `AppTest`) loads every built page with demo data.

### Phase 6 — Matching & review (1 day)
Fuzzy + optional LLM matcher, review table in the app, review log.
✅ Works without an API key; LLM mocked in tests; unreviewed items keep the result in draft.

### Phase 7 — Primary data, storage & audit (1–2 days)
§8 in full: validation, replacement, before/after, revert, audit trail, SQLite + session storage.
✅ Adding a valid supplier PCF changes the result and primary data share; reverting restores
the previous values exactly; an invalid submission is rejected with a reason.
✅ Session export → re-upload restores the same state.

### Phase 8 — Hotspots, priority ranking & supplier requests (1 day)
§9.1 and §9.2.
✅ Ranking matches a hand-checked fixture; status moves to *validated* automatically when
primary data is accepted.

### Phase 9 — Scenarios, sensitivity, variants (1 day)
Scenario comparison, sliders, Monte Carlo, product-family batch (§9.3).
✅ Results reproducible with fixed seed; ≥ 20 variants in < 10 s.

### Phase 10 — Outputs & claims check (1–2 days)
PACT export validated against the pinned official schema; DPP sheet; report; claims check (§9.4).
✅ Example outputs in `outputs/examples/`; schema validation in tests; draft results block
supported claims.
**[ASK]** Show the claims rules to the owner before finalising.

### Phase 11 — Deployment & portfolio polish (1 day)
Deploy to Streamlit Community Cloud (LLM off by default, openLCA hidden, session storage).
README: problem → approach → architecture diagram (Mermaid) → screenshots → standards
mapping table (§0) → live app link → limitations → how to run.
`docs/portfolio_summary.md` (½ page) for the owner's website and applications.
✅ Live link works; a fresh clone runs locally from README instructions in under 5 minutes.

### Phase 12 — openLCA backend (optional, 1–2 days)
`openlca_engine.py` via `olca-ipc` (openLCA 2.x desktop with IPC server, default port 8080),
free database (e.g. from openLCA Nexus); compare with Python engine and document.
✅ Skipped gracefully when openLCA is unreachable; local app shows the backend option only when connected.
**[ASK]** before starting: is openLCA installed, and which database?

---

## 13. Quality bar

- Type hints everywhere; docstrings on public functions; no notebooks in `src/`.
- No calculation logic in `app/` — pages only call `src/`.
- Test coverage ≥ 80% for `inventory/`, `engine/`, `methods/`, `primary_data/`, `suppliers/`, `outputs/`.
- No hardcoded paths or numbers: parameters in YAML, factors in CSV.
- Every result traceable: result → LCI line → factor_id → source_id (or primary data version_id).
- Plain-English messages in the app and logs; written for an LCA reviewer, not only developers.

---

## 14. `CLAUDE.md` content (create in Phase 1)

```
# Conventions
- Follow PROJECT_PLAN.md phase by phase; stop and summarise after each phase.
- Never invent emission factors, legal rules or standard field names; verify from official
  sources, otherwise use PLACEHOLDER and log in docs/data_gaps.md.
- Text marked [VERBATIM] in the plan is the owner's — use it unchanged.
- Calculation logic lives in src/; Streamlit pages only call it.
- Keep the core dependency-light; openLCA and LLM are optional plug-ins.
- Config in YAML, factors in CSV, no magic numbers in code.
- Run `ruff check . && pytest` before every commit.
- Never commit secrets; keys only via environment variables or st.secrets.
- Use fictional supplier names; never name a real company as a data source.
```

---

## 15. Out of scope (state in README limitations)

- Real company data, third-party verification, or certified EPD/PCF claims
- Full ISO 14044 critical review
- Sending emails to suppliers, user accounts/logins, multiple languages
- Product-specific ESPR delegated act requirements (not yet defined for this product group)
- Legal advice on environmental claims

---

## 16. Definition of done

- Phases 1–11 complete (12 optional), CI green, live app link working.
- Start here page matches §10 exactly.
- Primary data can be added, validated, replaced, compared, reverted and audited.
- README, methodology, AI validation, primary data workflow, claims and regulatory docs written.
- Example PACT JSON, DPP sheet, supplier request and report in `outputs/examples/`.
- Data gaps honestly listed; results clearly labelled as illustrative.
- Owner can explain every method choice in an interview in two minutes.
