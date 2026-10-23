from dataclasses import replace
from datetime import datetime, timezone
import pytest
from models import RecommendationRequest as R, ValidationError
from optimizer import recommend
from language import replacement_request, more_request

AT = datetime(2026,10,23,5,tzinfo=timezone.utc)


def all_results(result):
    return result["recommendations"]+result["over_budget_alternatives"]+result["unverified_price_alternatives"]


def test_three_distinct_deterministic(profile,foods):
    a = recommend(profile,R(meal_type="lunch"),foods,AT)
    assert a == recommend(profile,R(meal_type="lunch"),foods,AT)
    assert len(a["recommendations"]) == 3
    assert len({r["recommendation_id"] for r in a["recommendations"]}) == 3


def test_sorting(profile,foods):
    # Construct three full meals, exact nutrition vs low price tradeoff.
    a = replace(foods[0],food_id="a",kcal_per_serving=600,protein_g=40,fat_g=20,carbs_g=65,price_cny=20)
    b = replace(a,food_id="b",kcal_per_serving=400,protein_g=20,fat_g=12,carbs_g=53,price_cny=5)
    c = replace(a,food_id="c",kcal_per_serving=580,protein_g=38,fat_g=20,carbs_g=62,price_cny=10)
    args = dict(energy_target_kcal=600,protein_target_g=40,fat_target_g=20,carbs_target_g=65,max_types=1,max_quantity=1)
    first = {s:recommend(profile,R(strategy=s,**args),[a,b,c],AT)["recommendations"][0]["items"][0]["food"]["food_id"] for s in ("nutrition","price","balanced")}
    assert first == {"nutrition":"a","price":"b","balanced":"c"}


def test_hard_constraints(profile,foods):
    r = recommend(profile,R(maximum_kcal=650,minimum_protein_g=30,protein_minimum_hard=True,excluded_foods=["牛肉","薯条","含糖饮料"]),foods,AT)
    assert all_results(r)
    for row in all_results(r):
        assert row["totals"]["kcal_per_serving"] <= 650 and row["totals"]["protein_g"] >= 30
        assert not any(set(i["food"]["tags"]) & {"牛肉","薯条","含糖饮料"} for i in row["items"])


def test_allergen_unknown_and_cross_contact(profile,foods):
    unsafe = [replace(f,allergens_verified=False) for f in foods]
    assert not all_results(recommend(profile,R(allergens=["花生"]),unsafe,AT))
    unsafe = [replace(f,cross_contact=["花生"]) for f in foods]
    assert not all_results(recommend(profile,R(allergens=["花生"]),unsafe,AT))


def test_unknown_protein_cannot_pass_hard(profile,foods):
    f = replace(foods[0],protein_g=None)
    assert not all_results(recommend(profile,R(minimum_protein_g=1,protein_minimum_hard=True),[f],AT))
    soft = all_results(recommend(profile,R(),[f],AT))[0]
    assert soft["totals"]["protein_g"] is None and soft["unmet_soft_targets"]["protein_g"] == "未知"


def test_strict_unknown_and_expired_prices(profile,foods):
    f = replace(foods[0],price_status="unavailable",price_cny=None)
    r = recommend(profile,R(budget_cny=25,budget_mode="strict",strategy="price"),[f],AT)
    assert not r["recommendations"] and r["unverified_price_alternatives"]
    assert r["effective_strategy"] == "nutrition"
    assert r["unverified_price_alternatives"][0]["budget_status"] == "unverifiable"
    expired = replace(foods[0],price_valid_until="2026-10-23T00:00:00+00:00")
    assert not recommend(profile,R(),[expired],AT)["recommendations"]


def test_strict_and_flexible_overage(profile,foods):
    f = replace(foods[0],price_cny=26)
    assert not all_results(recommend(profile,R(budget_cny=25,budget_mode="strict"),[f],AT))
    r = recommend(profile,R(budget_cny=25),[f],AT)
    assert not r["recommendations"] and r["over_budget_alternatives"][0]["over_budget_cny"] == 1
    assert not all_results(recommend(profile,R(budget_cny=20),[f],AT))


def test_replacement_and_more(profile,foods):
    r = recommend(profile,R(),foods,AT)
    selected = next(x for x in r["recommendations"] if len(x["items"]) > 1)
    removed = [selected["items"][0]["food"]["food_id"]]
    update = replacement_request({"maximum_kcal":1000},selected,removed)
    result = recommend(profile,R(**update),foods,AT)
    assert all_results(result)
    for candidate in all_results(result):
        counts = {x["food"]["food_id"]:x["quantity"] for x in candidate["items"]}
        assert removed[0] not in counts
        assert all(counts[k] == v for k,v in update["required_quantities"].items())
    ids = [x["recommendation_id"] for x in r["recommendations"]]
    more = recommend(profile,R(exclude_signatures=ids,recommendation_count=2),foods,AT)
    assert not set(ids) & {x["recommendation_id"] for x in all_results(more)}


def test_small_catalog_and_duplicate(profile,foods):
    r = recommend(profile,R(),foods[:1],AT)
    assert len(all_results(r)) == 1
    with pytest.raises(ValidationError): recommend(profile,R(),foods[:1]*2,AT)
    assert not all_results(recommend(profile,R(),[replace(foods[0],kind="bundle")],AT))


def test_more_excludes_old_food_sets(profile,foods):
    prior = recommend(profile,R(),foods,AT)["recommendations"]
    update = more_request({},prior)
    following = all_results(recommend(profile,R(**update),foods,AT))
    old = {frozenset(x['food']['food_id'] for x in c['items']) for c in prior}
    assert following
    assert not old.intersection(frozenset(x['food']['food_id'] for x in c['items']) for c in following)


def test_scope_and_mixed_synthetic(profile,foods):
    scoped = replace(foods[0],price_scope='store-specific')
    assert not recommend(profile,R(),[scoped],AT)['recommendations']
    real = replace(foods[1],synthetic=False,source='list-nutrition-foods')
    with pytest.raises(ValidationError):
        recommend(profile,R(),[foods[0],real],AT)
