import copy
import json
from pathlib import Path
import pytest
from models import FoodItem, Profile, construct


@pytest.fixture
def fixture_data():
    return json.loads((Path(__file__).parent/"fixtures"/"synthetic.json").read_text(encoding="utf-8"))


@pytest.fixture
def profile(fixture_data):
    return construct(Profile,fixture_data["profile"])


@pytest.fixture
def foods(fixture_data):
    return [construct(FoodItem,x) for x in fixture_data["foods"]]
