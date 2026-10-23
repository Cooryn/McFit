"""Conservative, configurable estimates for one meal; no daily meal planning."""
from models import ValidationError, number

ACTIVITY = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725}
MEAL_SHARE = {"breakfast": .25, "lunch": .35, "dinner": .30, "snack": .10, "unspecified": .30}
ENERGY_FACTOR = {"gain_muscle": 1.05, "lose_fat": .90, "maintain": 1.0, "recomposition": 1.0}
WEIGHTS = {"gain_muscle": (1, 2, .4, .6), "lose_fat": (2, 1.5, .6, .4),
           "maintain": (1, 1, .5, .5), "recomposition": (1, 2, .5, .5)}
DISCLAIMER = "营养估算不等于医学诊断；仅对麦当劳单餐推荐，不代表全天营养均衡。"


def safety_check(profile, request):
    if profile.age_years < 18 or profile.safety_flags:
        raise ValidationError("不适用常规成人自动计算：未成年/妊娠哺乳/疾病治疗饮食/饮食障碍风险需专业评估")
    if profile.target_body_fat_pct is not None and profile.target_body_fat_pct < 10:
        raise ValidationError("低体脂目标超出本工具自动指导范围，请寻求专业评估")
    if profile.goal_type == "lose_fat" and profile.weight_kg / (profile.height_cm / 100)**2 < 18.5:
        raise ValidationError("当前身体参数下暂停自动减重指导，建议专业评估")
    if profile.target_weight_kg and profile.target_weight_kg / (profile.height_cm / 100)**2 < 18.5:
        raise ValidationError("目标体重超出本工具保守自动指导范围")
    floor = 80 if request.meal_type == "snack" else 300
    for v in (request.energy_target_kcal, request.maximum_kcal):
        if v is not None and v < floor:
            raise ValidationError("该餐热量限制超出本工具保守范围；不能作为最接近方案")


def estimate(profile, request, meal_shares=None):
    safety_check(profile, request)
    shares = MEAL_SHARE if meal_shares is None else meal_shares
    share = number(shares[request.meal_type], "餐次比例", .05, .5)
    ree = 10 * profile.weight_kg + 6.25 * profile.height_cm - 5 * profile.age_years
    ree += 5 if profile.sex_for_equation == "plus5" else -161
    tdee = ree * (profile.activity_factor or ACTIVITY[profile.activity_level])
    daily = tdee * ENERGY_FACTOR[profile.goal_type]
    protein_rate = profile.protein_g_per_kg
    if protein_rate is None:
        protein_rate = (1.8 if profile.goal_type == "recomposition" else 1.6) if profile.resistance_training else 1.0
    protein = profile.weight_kg * protein_rate
    fat = daily * .30 / 9
    carbs = (daily - protein * 4 - fat * 9) / 4
    if carbs < 0:
        raise ValidationError("宏量营养配置与能量不相容")
    target = dict(zip(("kcal_per_serving", "protein_g", "fat_g", "carbs_g"),
                      (daily * share, protein * share, fat * share, carbs * share)))
    # Timing changes meal composition only; no additional exercise calories.
    if request.workout_context == "pre":
        target["fat_g"] *= .8
        target["carbs_g"] += daily * share * .30 * .2 / 4
    notes = ["REE/TDEE 和餐次分配为粗略估算，非当日剩余额度。"]
    if request.workout_context == "post":
        notes.append("训练后可选择含蛋白质的正常餐食，无需精确补充窗口；未追加全天运动消耗。")
    for field, metric in (("energy_target_kcal","kcal_per_serving"), ("protein_target_g","protein_g"),
                          ("fat_target_g","fat_g"), ("carbs_target_g","carbs_g")):
        value = getattr(request, field)
        if value is not None:
            target[metric] = value
    if request.minimum_protein_g is not None:
        target["protein_g"] = max(target["protein_g"], request.minimum_protein_g)
    return {"targets": {k: round(v, 3) for k,v in target.items()}, "ree_kcal": round(ree, 2),
            "tdee_estimate_kcal": round(tdee, 2), "meal_share": share, "protein_g_per_kg": protein_rate,
            "notes": notes, "disclaimer": DISCLAIMER}
