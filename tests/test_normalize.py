from dataclasses import asdict
import pytest
from models import ValidationError
from normalize import normalize_foods, match_food


def bridge():
    return {"bridge_version":1,"mapping_reviewed":True,"synthetic":True,"foods":[{
        "food_id":"unit-test","name":"合成单位测试","source":"synthetic-fixture","observed_at":"2026-10-23T12:00:00+08:00",
        "basis":"per_100g","serving_mass_g":200,"energy_unit":"kJ","energy":836.8,
        "protein_g":20,"fat_g":8,"carbs_g":12,"sodium_mg":None}]}


def test_conversion_unknown():
    f = normalize_foods(bridge())[0]
    assert f["kcal_per_serving"] == pytest.approx(400)
    assert f["protein_g"] == 40 and f["sodium_mg"] is None


@pytest.mark.parametrize("mutation",["unit","mass","energy","duplicate","schema"])
def test_bad_normalization(mutation):
    d = bridge()
    if mutation == "unit": d["foods"][0]["energy_unit"] = "cal"
    if mutation == "mass": d["foods"][0].pop("serving_mass_g")
    if mutation == "energy": d["foods"][0]["energy"] = 10000
    if mutation == "duplicate": d["foods"] *= 2
    if mutation == "schema": d["mapping_reviewed"] = False
    with pytest.raises(ValidationError): normalize_foods(d)


def test_matching_not_fuzzy(foods):
    assert match_food({"food_id":foods[0].food_id},foods)[1] == "exact"
    assert match_food({"name":foods[0].name},foods) == (None,"uncertain")
    assert match_food({"name":"别名"},foods,{"别名|":foods[0].food_id})[1] == "reviewed"
