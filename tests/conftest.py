import os
from pathlib import Path

import pytest

from bom_to_pcf.models import ProductConfig

# Tests must never touch a real local database.
os.environ["BOM_TO_PCF_STORAGE"] = "session"

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config() -> ProductConfig:
    return ProductConfig.from_yaml(ROOT / "config" / "product_pet_diecut.yaml")
