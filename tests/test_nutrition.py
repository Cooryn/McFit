from dataclasses import replace
import math
import pytest
from models import Profile, RecommendationRequest as R, ValidationError
from language import parse_profile, parse_request, workout
from nutrition import estimate


def test_profile_draft_units_and_no_sex_guess():
    d = parse_profile("我21岁，男，1.75m，120斤，想增肌到65kg，每周练4次")
    assert d["draft"]["weight_kg"] == 60
    assert d["draft"]["height_cm"] == 175
    assert d["draft"]["target_weight_kg"] == 65
    assert "activity_level" in d["missing"]
    assert "sex_for_equation" in d["missing"]
    assert d["requires_confirmation"]


def test_ambiguous_and_target_body_fat():
    d = parse_profile("身高175，体重60，目标体脂15%")
    assert "weight_kg" in d["missing"]
    assert "current_body_fat_pct" not in d["draft"]
    assert d["draft"]["target_body_fat_pct"] == 15


@pytest.mark.parametrize("text,result",[("刚练完腿","post"),("两小时后跑步","pre"),("今天休息","rest"),("吃午饭","unknown")])
def test_workout(text,result):
    assert workout(text) == result


def test_goals_energy_balance_and_no_double_training(profile):
    estimates = {g:estimate(replace(profile,goal_type=g),R(meal_type="lunch")) for g in ("gain_muscle","lose_fat","maintain","recomposition")}
    assert estimates["gain_muscle"]["targets"]["kcal_per_serving"] > estimates["maintain"]["targets"]["kcal_per_serving"] > estimates["lose_fat"]["targets"]["kcal_per_serving"]
    assert estimates["recomposition"]["protein_g_per_kg"] > estimates["maintain"]["protein_g_per_kg"]
    for value in estimates.values():
        t = value["targets"]
        assert t["kcal_per_serving"] == pytest.approx(t["protein_g"]*4+t["fat_g"]*9+t["carbs_g"]*4,abs=.01)
    assert estimate(profile,R(workout_context="post"))["tdee_estimate_kcal"] == estimate(profile,R())["tdee_estimate_kcal"]


def test_hard_soft_language():
    hard = parse_request("午餐热量控制在650 kcal内，蛋白质至少30g")
    assert hard["maximum_kcal"] == 650 and hard["protein_minimum_hard"]
    soft = parse_request("大约650 kcal，蛋白质约30g")
    assert soft["energy_target_kcal"] == 650 and "maximum_kcal" not in soft


@pytest.mark.parametrize("changes",[{"age_years":17},{"safety_flags":["pregnancy"]},{"target_body_fat_pct":5}])
def test_unsafe_profiles(profile,changes):
    with pytest.raises(ValidationError):
        estimate(replace(profile,**changes),R())


def test_extreme_requests(profile):
    with pytest.raises(ValidationError):
        estimate(profile,R(maximum_kcal=100))
    with pytest.raises(ValidationError):
        parse_request("我要惩罚自己断食")


@pytest.mark.parametrize("value",[float("nan"),float("inf"),-1,True])
def test_invalid_numeric(profile,value):
    with pytest.raises(ValidationError):
        replace(profile,weight_kg=value)


def test_update_draft(profile):
    from dataclasses import asdict
    draft = parse_profile("我现在61kg了，默认预算改成28元",asdict(profile))["draft"]
    assert draft["weight_kg"] == 61 and draft["default_budget_cny"] == 28
    assert draft["user_id"] == profile.user_id


def test_negative_units_rejected():
    with pytest.raises(ValidationError):
        parse_profile("现在-60kg")
