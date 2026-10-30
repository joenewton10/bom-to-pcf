from pathlib import Path

import pytest

from bom_to_pcf.models import ProductConfig

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config() -> ProductConfig:
    return ProductConfig.from_yaml(ROOT / "config" / "product_pet_diecut.yaml")
