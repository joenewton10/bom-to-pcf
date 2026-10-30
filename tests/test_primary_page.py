"""The Primary data page, driven through the real app with session storage."""

from streamlit.testing.v1 import AppTest
from test_app_smoke import HOME, TIMEOUT, try_demo

PAGE = "pages/6_Primary_data.py"


def open_page() -> AppTest:
    at = try_demo(AppTest.from_file(HOME, default_timeout=TIMEOUT).run())
    at.switch_page(PAGE)
    return at.run()


def button(at: AppTest, label: str):
    return next(b for b in at.button if b.label == label)


def add_example(at: AppTest) -> AppTest:
    at.text_input(key="primary_user").input("Test Reviewer")
    at.run()
    button(at, "Fill with a test example").click()
    at.run()
    button(at, "Check and add").click()
    return at.run()


def test_page_prompts_without_data() -> None:
    at = AppTest.from_file(HOME, default_timeout=TIMEOUT).run()
    at.switch_page(PAGE)
    at.run()
    assert not at.exception
    assert any("No data loaded" in i.value for i in at.info)


def test_page_loads_and_explains_hosted_storage() -> None:
    at = open_page()
    assert not at.exception
    assert any("does not keep your work" in i.value for i in at.info)


def test_example_is_accepted_labelled_and_marks_progress() -> None:
    at = add_example(open_page())
    assert not at.exception
    assert any("Accepted" in s.value for s in at.success)
    project = at.session_state["project_state"]
    assert list(project.active) == ["100001"]
    version = project.versions[0]
    assert "TEST RECORD" in version.submission.notes
    assert version.user == "Test Reviewer"
    assert "Primary data added" in at.session_state["progress"]


def test_undo_returns_to_the_database_value() -> None:
    at = add_example(open_page())
    at.text_input(key="undo_reason").input("Test")
    at.run()
    button(at, "Undo").click()
    at.run()
    assert not at.exception
    project = at.session_state["project_state"]
    assert project.active == {}
    assert project.audit[-1].field == "active_version"
    assert "Primary data added" not in at.session_state["progress"]


def test_invalid_submission_is_rejected_on_the_page() -> None:
    at = open_page()
    at.text_input(key="primary_user").input("Test Reviewer")
    at.run()
    button(at, "Check and add").click()
    at.run()
    assert not at.exception
    assert any("Rejected" in e.value for e in at.error)
    project = at.session_state["project_state"]
    assert project.active == {}
    assert project.rejections


def test_submitting_without_a_name_adds_nothing() -> None:
    at = open_page()
    button(at, "Check and add").click()
    at.run()
    assert any("Nothing was added" in e.value for e in at.error)
    assert not at.session_state["project_state"].audit
