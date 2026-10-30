from pathlib import Path

import pytest
import yaml
from engine_helpers import bom_line
from streamlit.testing.v1 import AppTest
from test_app_smoke import HOME, TIMEOUT, try_demo

from bom_to_pcf.models import (
    EmissionFactor,
    EngagementConfig,
    PriorityRules,
    ResultLine,
    Supplier,
)
from bom_to_pcf.suppliers.priority import (
    data_quality_gap,
    priority_table,
    rank_materials,
    recommendations,
    supplier_coverage,
)

FIXTURE = Path(__file__).parent / "fixtures" / "priority_case.yaml"
ROOT = Path(__file__).resolve().parents[1]
RULES = PriorityRules(
    contribution_weight=1, quality_weight=1, dqr_best=1, dqr_worst=5, recommend_top=3
)
SUPPLIERS = [Supplier(supplier_id="S", name="Supplier A", country="DE", contact_role="R",
                      materials_supplied=[])]  # fmt: skip


def result_line(raw: dict) -> ResultLine:
    return ResultLine(
        stage=raw["stage"],
        item=raw["item"],
        description=raw["description"],
        quantity=1,
        unit="kg",
        factor_id=raw["factor"],
        impact=raw["impact"],
    )


def factor(raw: dict) -> EmissionFactor:
    tech, geo, time = raw["dqr"]
    return EmissionFactor(
        factor_id=raw["id"],
        name=raw["id"],
        value=1,
        unit="kg CO2e/kg",
        source_id="T",
        data_type=raw["type"],
        dqr_tech=tech,
        dqr_geo=geo,
        dqr_time=time,
        status="ACTIVE",
    )


@pytest.fixture
def case():
    raw = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    bom = [bom_line(item, f"Material {item}", 1.0) for item in "ABCE"]
    rows = rank_materials(
        [result_line(line) for line in raw["lines"]],
        raw["total"],
        {f["id"]: factor(f) for f in raw["factors"]},
        bom,
        SUPPLIERS,
        RULES,
    )
    return rows, raw["expected"]


def test_ranking_matches_the_hand_checked_fixture(case) -> None:
    rows, expected = case
    assert [row.material_number for row in rows] == expected["order"]
    for row in rows:
        material = row.material_number
        assert row.score == pytest.approx(expected["scores"][material], abs=1e-5)
        assert row.dqr == pytest.approx(expected["dqr"][material])
        assert row.impact_on_weak_data == pytest.approx(expected["weak"][material])
        assert row.contribution == pytest.approx(expected["contribution"][material], abs=1e-5)
        assert row.data_type == expected["data_type"][material]


def test_site_energy_is_not_ranked(case) -> None:
    assert "S1" not in {row.material_number for row in case[0]}


def test_recommendations_name_the_supplier_and_skip_strong_data(case) -> None:
    advice = recommendations(case[0], RULES)
    assert advice[0] == (
        "Ask Supplier A for Material A data first — it drives 33% of the footprint and uses "
        "database data."
    )
    assert "next" in advice[1]
    assert len(advice) == 3
    assert not any("Material E" in text for text in advice)


def test_recommendation_without_a_supplier_says_so(case) -> None:
    rows = [case[0][0].model_copy(update={"supplier_id": None, "supplier_name": None})]
    assert "Identify the supplier" in recommendations(rows, RULES)[0]


def test_unnamed_supplier_falls_back_to_its_id(case) -> None:
    rows = [case[0][0].model_copy(update={"supplier_id": "S9", "supplier_name": None})]
    assert "Ask S9" in recommendations(rows, RULES)[0]


def test_weights_change_the_ranking(case) -> None:
    raw = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    rules = RULES.model_copy(update={"contribution_weight": 0.0})
    rows = rank_materials(
        [result_line(line) for line in raw["lines"]],
        raw["total"],
        {f["id"]: factor(f) for f in raw["factors"]},
        [],
        [],
        rules,
    )
    # With contribution ignored, the weakest data comes first: C (0.80), A (0.75), B (0.50).
    assert [row.material_number for row in rows][:3] == ["C", "A", "B"]
    assert rows[0].supplier_id is None


@pytest.mark.parametrize(("dqr", "gap"), [(1, 0), (3, 0.5), (5, 1)])
def test_gap_runs_from_best_to_worst(dqr: float, gap: float) -> None:
    assert data_quality_gap(dqr, RULES) == gap


def test_missing_factor_or_score_counts_as_worst() -> None:
    line = ResultLine(stage="materials", item="X", description="X", quantity=1, unit="kg",
                      factor_id="MISSING", impact=1.0)  # fmt: skip
    rows = rank_materials([line], 1.0, {}, [], [], RULES)
    assert rows[0].dqr == 5
    no_score = EmissionFactor(factor_id="MISSING", name="M", value=1, unit="kg CO2e/kg",
                              data_type="secondary", status="ACTIVE")  # fmt: skip
    assert rank_materials([line], 1.0, {"MISSING": no_score}, [], [], RULES)[0].dqr == 5


def test_zero_total_and_placeholder_lines_are_safe() -> None:
    line = ResultLine(stage="materials", item="X", description="X", quantity=1, unit="kg",
                      factor_id=None, impact=0.0)  # fmt: skip
    assert rank_materials([line], 0.0, {}, [], [], RULES)[0].contribution == 0
    unknown = line.model_copy(update={"impact": None})
    assert rank_materials([unknown], 1.0, {}, [], [], RULES) == []


def test_table_has_the_planned_columns(case) -> None:
    columns = list(priority_table(case[0]).columns)
    assert columns[:2] == ["Material", "Supplier"]
    assert "Priority score" in columns
    assert "DQR" in columns
    assert "Data type" in columns


def test_config_loads() -> None:
    config = EngagementConfig.from_yaml(ROOT / "config" / "supplier_engagement.yaml")
    assert config.priority.recommend_top == 3


def test_demo_ranks_film_first_on_the_page() -> None:
    at = try_demo(AppTest.from_file(HOME, default_timeout=TIMEOUT).run())
    at.switch_page("pages/4_Hotspots_and_priorities.py")
    at.run()
    assert not at.exception
    advice = [m.value for m in at.markdown if m.value.startswith("- Ask")]
    assert "Fictional Films A GmbH" in advice[0]
    assert "PET-Folie" in advice[0]
    assert "Hotspots checked" in at.session_state["progress"]


def test_page_prompts_without_data() -> None:
    at = AppTest.from_file(HOME, default_timeout=TIMEOUT).run()
    at.switch_page("pages/4_Hotspots_and_priorities.py")
    at.run()
    assert not at.exception
    assert any("No data loaded" in i.value for i in at.info)


def test_coverage_counts_only_supplier_lines(case) -> None:
    from types import SimpleNamespace

    lines = [
        ResultLine(stage="materials", item="A", description="A", quantity=1, unit="kg",
                   impact=1.0, source_id="supplier_pcf:V0001"),
        ResultLine(stage="materials", item="B", description="B", quantity=1, unit="kg",
                   impact=3.0, source_id="UBA"),
    ]  # fmt: skip
    assert supplier_coverage(SimpleNamespace(lines=lines)) == 0.25
    assert supplier_coverage(SimpleNamespace(lines=[])) == 0.0
