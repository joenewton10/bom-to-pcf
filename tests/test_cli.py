from typer.testing import CliRunner

from bom_to_pcf import __version__
from bom_to_pcf.cli import app


def test_version_prints_package_version() -> None:
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__
