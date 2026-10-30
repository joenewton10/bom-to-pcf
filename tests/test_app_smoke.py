"""Every built page must load without raising an exception."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def test_home_loads() -> None:
    at = AppTest.from_file(str(APP_DIR / "Home.py")).run()
    assert not at.exception
