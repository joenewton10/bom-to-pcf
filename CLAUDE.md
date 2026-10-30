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
