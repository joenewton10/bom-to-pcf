"""Built pages load with demo data, and the Start here page keeps the owner's wording."""

import re
from pathlib import Path

from state import CALCULATED, PROGRESS, UPLOADED, VALIDATED
from streamlit.testing.v1 import AppTest

from bom_to_pcf.io.inputs import BOM_FILE, load_inputs

ROOT = Path(__file__).resolve().parents[1]
HOME = str(ROOT / "app" / "Home.py")
TIMEOUT = 30


def start() -> AppTest:
    return AppTest.from_file(HOME, default_timeout=TIMEOUT).run()


def try_demo(at: AppTest) -> AppTest:
    next(b for b in at.button if b.label == "▶ Try the demo").click()
    return at.run()


def page_text(at: AppTest) -> str:
    parts = [e.value for group in (at.title, at.header, at.markdown, at.caption, at.info)
             for e in group]  # fmt: skip
    return re.sub(r"\s+", " ", " ".join(parts))


def plan_section_10_lines() -> list[str]:
    """The owner's wording from the plan: every paragraph that is not a layout note."""
    plan = (ROOT / "PROJECT_PLAN.md").read_text(encoding="utf-8")
    section = plan.split("## 10. Start here page")[1].split("## 11. CLI")[0]
    body = section.split("---", 1)[1].rsplit("---", 1)[0]
    paragraphs: list[str] = []
    for block in re.split(r"\n\s*\n", body):
        lines = [line for line in block.splitlines() if line.strip()]
        kept = [
            line
            for line in lines
            if not re.fullmatch(r"\*[^*]+\*:?", line.strip())
            and not line.startswith("#")
            and not line.startswith("*Flow")
            and not line.startswith("*Upload BOM")
            and not line.startswith("Request supplier data")
            and not line.startswith("and an `st.page_link`")
            and not line.startswith("*Draw")
            and not line.startswith("*Step cards")
            and not line.startswith("*and an")
            and not line.startswith("**▶")
            and "*link" not in line
            and "*GitHub" not in line
        ]
        if kept:
            paragraphs.append(re.sub(r"\s+", " ", " ".join(kept)))
    return paragraphs


def test_start_page_loads() -> None:
    at = start()
    assert not at.exception
    assert at.title[0].value == "From bill of materials to product carbon footprint"


def test_start_page_matches_the_owners_wording() -> None:
    text = page_text(start())
    paragraphs = plan_section_10_lines()
    assert len(paragraphs) > 10
    for paragraph in paragraphs:
        for part in re.split(r"(?=- \*\*)", paragraph):
            assert part.strip() in text, part


def test_demo_opens_a_full_breakdown_in_one_click() -> None:
    at = try_demo(start())
    assert not at.exception
    assert at.title[0].value == "Results"
    labels = [m.label for m in at.metric]
    assert "PCF per kg" in labels
    assert "Primary data share" in labels
    assert len(at.dataframe) >= 2


def test_results_show_disclaimer_and_draft_status() -> None:
    at = try_demo(start())
    assert any("not a verified PCF" in c.value for c in at.caption)
    assert any("DRAFT" in w.value for w in at.warning)


def test_sidebar_ticks_update_after_the_demo() -> None:
    # AppTest does not expose this sidebar's contents, so check the state that drives the ticks.
    at = try_demo(start())
    assert at.session_state[PROGRESS] == {UPLOADED, VALIDATED, CALCULATED}


def test_results_without_data_prompts_the_user() -> None:
    at = start()
    at.switch_page("pages/3_Results.py")
    at.run()
    assert not at.exception
    assert any("No data loaded" in i.value for i in at.info)


def test_upload_page_loads_and_validates_the_demo() -> None:
    at = start()
    at.switch_page("pages/1_Upload_and_validate.py")
    at.run()
    assert not at.exception
    next(b for b in at.button if b.label == "Use the demo files").click()
    at.run()
    assert not at.exception
    assert {m.label: m.value for m in at.metric}["BOM lines kept"] == "6"
    assert any("closes within" in s.value for s in at.success)
    assert len(at.dataframe) == 1


def test_uploaded_bytes_validate_like_files(config) -> None:
    from bom_to_pcf.io.inputs import bundle_from_files

    demo = ROOT / "data" / "demo"
    files = {p.name: p.read_bytes() for p in demo.iterdir()}
    assert bundle_from_files(config, files).bom == load_inputs(config, demo).bom
    files.pop(BOM_FILE)
    assert bundle_from_files(config, files).has_errors
