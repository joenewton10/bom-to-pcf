# bom-to-pcf

Automated cradle-to-gate product carbon footprint (PCF) calculation from a bill of materials.

> **Work in progress.** All data in this project is representative and results are illustrative.
> They are not a verified PCF and should not be used for real claims.

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows; on macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
streamlit run app/Home.py
```

## Check

```bash
ruff check . && pytest
```

See [PROJECT_PLAN.md](PROJECT_PLAN.md) for the full brief.
