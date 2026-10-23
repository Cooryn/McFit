"""Bounded deterministic enumeration. All hard limits are applied before ranking."""
from dataclasses import asdict
from datetime import datetime, timezone
from itertools import combinations, product
import hashlib
from models import METRICS, ValidationError, timestamp
from nutrition import estimate, WEIGHTS


def signature(items):
    return hashlib.sha256("|".join(f"{k}:{v}" for k,v in sorted(items.items())).encode()).hexdigest()[:20]


def price_usable(food, at):
    return (food.price_status in ("verified", "reference") and food.price_scope == "china_reference"
            and timestamp(food.price_observed_at) <= at <= timestamp(food.price_valid_until))


def recommend(profile, request, foods, at=None):
    at = at or datetime.now(timezone.utc)
    estimated = estimate(profile, request)
    target = estimated["targets"]
    if len({f.food_id for f in foods}) != len(foods):
        raise ValidationError("重复 food_id")
    if foods and len({f.synthetic for f in foods}) > 1:
        raise ValidationError("合成与真实数据不能混用")
    excluded = set(profile.exclusions + request.excluded_foods)
    allergens = set(profile.allergens + request.allergens)
    eligible, rejected = [], {}
    for f in sorted(foods, key=lambda x: x.food_id):
        reason = None
        if f.kind != "single":
            reason = "套餐需先解析为不重叠单品，不能与组成重复计数"
        elif f.match_confidence == "uncertain":
            reason = "餐品匹配未审核"
        elif any(x == f.food_id or x in f.name or x in f.tags for x in excluded):
            reason = "命中排除项"
        elif excluded and not f.ingredients_known:
            reason = "原料/饮料标签不足，无法核实排除项"
        elif allergens and (not f.allergens_verified or allergens.intersection(f.allergens + f.cross_contact)):
            reason = "过敏原或交叉接触无法排除"
        elif f.kcal_per_serving is None:
            reason = "热量未知，无法生成可靠单餐"
        if reason:
            rejected[f.food_id] = reason
        else:
            eligible.append(f)
    if len(eligible) > 30:
        raise ValidationError("候选超过30项：请按餐次/偏好明确缩小食品表；未静默截断")
    buckets = {"recommendations": [], "over_budget_alternatives": [], "unverified_price_alternatives": []}
    weights = WEIGHTS[profile.goal_type]
    examined = 0
    for n in range(1, min(request.max_types, len(eligible)) + 1):
        for group in combinations(eligible, n):
            if any(set(c) == {f.food_id for f in group} for c in request.exclude_compositions):
                continue
            for quantities in product(range(1, request.max_quantity + 1), repeat=n):
                # Max four individual servings as well as four distinct types.
                if sum(quantities) > 4:
                    continue
                examined += 1
                counts = {f.food_id:q for f,q in zip(group, quantities)}
                if any(counts.get(k) != v for k,v in request.required_quantities.items()):
                    continue
                sig = signature(counts)
                if sig in request.exclude_signatures:
                    continue
                totals = {k: (sum(getattr(f,k)*q for f,q in zip(group,quantities))
                              if all(getattr(f,k) is not None for f in group) else None) for k in METRICS}
                if request.maximum_kcal is not None and totals["kcal_per_serving"] > request.maximum_kcal + 1e-9:
                    continue
                if request.protein_minimum_hard and request.minimum_protein_g is not None:
                    if totals["protein_g"] is None or totals["protein_g"] < request.minimum_protein_g:
                        continue
                # Prevent returning tiny drinks as a full meal, even as a closest result.
                if totals["kcal_per_serving"] < (80 if request.meal_type == "snack" else 300):
                    continue
                usable = all(price_usable(f, at) for f in group)
                # Discounts/delivery contexts must also agree across the combination.
                usable = usable and len({(f.includes_discounts, f.includes_delivery) for f in group}) == 1
                price = round(sum(f.price_cny*q for f,q in zip(group, quantities)), 2) if usable else None
                category, budget_status = "recommendations", "not_requested"
                if price is None:
                    category, budget_status = "unverified_price_alternatives", "unverifiable"
                elif request.budget_cny is not None:
                    if price <= request.budget_cny + 1e-9:
                        budget_status = "within_reference_budget"
                    elif request.budget_mode == "flexible" and price <= request.budget_cny + min(request.budget_cny*request.flexible_ratio, request.flexible_cap_cny) + 1e-9:
                        category, budget_status = "over_budget_alternatives", "over_budget"
                    else:
                        continue
                deviations = {k: None if totals[k] is None else round(totals[k]-v, 3) for k,v in target.items()}
                loss = sum(w * (abs(deviations[k])/max(target[k],1) if deviations[k] is not None else 2)
                           for k,w in zip(target,weights))
                gaps = {k: ("未知" if deviations[k] is None else deviations[k]) for k in target
                        if deviations[k] is None or abs(deviations[k]) > max(1, target[k]*.1)}
                buckets[category].append({"recommendation_id":sig, "items":[{"food":asdict(f),"quantity":q} for f,q in zip(group,quantities)],
                    "totals":{k: None if v is None else round(v,3) for k,v in totals.items()},
                    "price_cny":price, "price_status":("reference" if usable else "unavailable"),
                    "budget_status":budget_status, "over_budget_cny":round(max(0,price-request.budget_cny),2) if price is not None and request.budget_cny is not None else None,
                    "deviations":deviations, "unmet_soft_targets":gaps, "nutrition_loss":round(loss,6),
                    "reason":"在全部可验证硬限制内比较单餐营养偏差；价格仅在来源和范围可核实时参与。"})
    warnings = []
    available_price = bool(buckets["recommendations"] or buckets["over_budget_alternatives"])
    effective = request.strategy if available_price else "nutrition"
    if not available_price and request.strategy != "nutrition":
        warnings.append("价格优化不可用，降级到营养排序；不能称最便宜或预算达标。")
    if buckets["unverified_price_alternatives"]:
        warnings.append("价格未核实的营养备选单独列出，无法确认预算达标。")
    def ranked(rows, strategy):
        def key(r):
            if strategy == "price":
                return (r["price_cny"], r["nutrition_loss"], r["recommendation_id"])
            score = r["nutrition_loss"]
            if strategy == "balanced":
                score += .5*r["price_cny"]/max(request.budget_cny or 30, 1)
            return (score, r["recommendation_id"])
        selected, sets = [], []
        for r in sorted(rows, key=key):
            ids = frozenset(i["food"]["food_id"] for i in r["items"])
            # Same item set with a different quantity is not a substantively new option.
            if ids in sets:
                continue
            selected.append(r)
            sets.append(ids)
            if len(selected) >= request.recommendation_count:
                break
        return selected
    for category in buckets:
        buckets[category] = ranked(buckets[category], "nutrition" if category == "unverified_price_alternatives" else effective)
    if len(buckets["recommendations"]) < request.recommendation_count:
        warnings.append("可核实且有实质差异的合规方案不足所请求数量；未复制凑数。")
    return {**buckets, **estimated, "effective_strategy":effective, "warnings":warnings, "rejected_foods":rejected,
            "examined_combinations":examined, "synthetic":bool(foods and foods[0].synthetic),
            "status":"ok" if buckets["recommendations"] else "no_verified_feasible_result"}
