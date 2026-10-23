"""Small deterministic Chinese parser. AI 助手 handles open language via reviewed JSON.

This parser only proposes drafts. It never saves data or asserts user consent.
"""
import re
from models import ValidationError

GOAL_WORDS = {"增肌":"gain_muscle", "减脂":"lose_fat", "减重":"lose_fat", "维持":"maintain", "重塑":"recomposition"}
MEAL_WORDS = {"早餐":"breakfast", "早饭":"breakfast", "午餐":"lunch", "午饭":"lunch", "晚餐":"dinner", "晚饭":"dinner", "加餐":"snack"}
CN_COUNTS = {"一":1,"两":2,"二":2,"三":3,"四":4,"五":5}


def workout(text):
    if re.search(r"休息|不训练", text):
        return "rest"
    if re.search(r"刚.*(?:练完|跑完)|训练后|练后", text):
        return "post"
    if re.search(r"训练前|练前|后.*(?:跑步|训练|健身)", text):
        return "pre"
    return "unknown"


def reject_extreme(text):
    if re.search(r"[-−]\s*\d+(?:\.\d+)?\s*(?:kg|公斤|斤|cm|厘米|米|kcal|千卡|岁)", text, re.I):
        raise ValidationError("身体参数/热量不能为负数，请核对输入")
    if re.search(r"惩罚.*(?:断食|不吃)|(?:断食|不吃).*(?:惩罚)|饿死|催吐", text):
        raise ValidationError("不支持惩罚性断食或危险限制；建议寻求支持及专业评估")


def parse_profile(text, existing=None):
    reject_extreme(text)
    data = dict(existing or {})
    notes = []
    match = re.search(r"(\d+)\s*岁",text)
    if match:
        data["age_years"] = int(match[1])
    match = re.search(r"(\d+(?:\.\d+)?)\s*(cm|厘米|米|m)(?![a-z])",text,re.I)
    if match:
        data["height_cm"] = float(match[1]) * (100 if match[2].lower() in ("m","米") else 1)
    # A target weight must never be mistaken for current weight.
    weights = list(re.finditer(r"(\d+(?:\.\d+)?)\s*(kg|公斤|千克|斤)",text,re.I))
    for match in weights:
        context = text[max(0,match.start()-8):match.start()]
        key = "target_weight_kg" if re.search(r"目标|(?:增肌|减脂|减重|到)\s*(?:到)?\s*$",context) else "weight_kg"
        data[key] = float(match[1]) * (.5 if match[2] == "斤" else 1)
    for word, goal in GOAL_WORDS.items():
        if word in text:
            data["goal_type"] = goal
    # Identity alone never selects the equation parameter.
    if re.search(r"(?:公式|参数).*(?:\+5|plus5|男性)",text):
        data["sex_for_equation"] = "plus5"
    elif re.search(r"(?:公式|参数).*(?:-161|minus161|女性)",text):
        data["sex_for_equation"] = "minus161"
    elif "男" in text or "女" in text:
        notes.append("身份表述不会自动决定代谢公式参数；请选择 +5 或 -161。")
    for word, activity in {"久坐":"sedentary", "轻体力":"light", "经常步行":"light", "中等活动":"moderate", "重体力":"active"}.items():
        if word in text:
            data["activity_level"] = activity
    match = re.search(r"每周[^，。；]*?(?:\d+|[一二三四五六七])\s*次",text)
    if match:
        data["training_pattern"] = match[0]
    if "力量训练" in text:
        data["resistance_training"] = True
    for match in re.finditer(r"(目标)?体脂(?:率)?\s*(\d+(?:\.\d+)?)\s*%",text):
        data["target_body_fat_pct" if match[1] else "current_body_fat_pct"] = float(match[2])
    match = re.search(r"默认预算(?:改成|为)?\s*(\d+(?:\.\d+)?)\s*元",text)
    if match:
        data["default_budget_cny"] = float(match[1])
    for word, strategy in {"营养优先":"nutrition", "价格优先":"price", "均衡推荐":"balanced"}.items():
        if word in text:
            data["default_strategy"] = strategy
    if "严格预算" in text:
        data["budget_mode"] = "strict"
    if "弹性预算" in text:
        data["budget_mode"] = "flexible"
    exclusions = re.findall(r"(?:不吃|不要|排除)(牛肉|薯条|含糖饮料)",text)
    if exclusions:
        data["exclusions"] = sorted(set(data.get("exclusions",[]) + exclusions))
    flags = {"pregnancy":"怀孕|妊娠", "lactation":"哺乳", "eating_disorder":"饮食障碍|厌食症", "therapeutic_diet":"肾病|糖尿病|治疗饮食"}
    for flag, pattern in flags.items():
        if re.search(pattern,text):
            data["safety_flags"] = sorted(set(data.get("safety_flags",[]) + [flag]))
    required = ("age_years", "height_cm", "weight_kg", "sex_for_equation", "goal_type", "activity_level")
    missing = [k for k in required if k not in data]
    return {"draft":data, "missing":missing, "next_question":missing[0] if missing else "请核对换算后的资料并明确确认保存。",
            "notes":notes, "requires_confirmation":True}


def parse_request(text, previous=None):
    reject_extreme(text)
    result = dict(previous or {})
    context = workout(text)
    if context != "unknown":
        result["workout_context"] = context
    for word, meal in MEAL_WORDS.items():
        if word in text:
            result["meal_type"] = meal
    for word, strategy in {"营养优先":"nutrition", "价格优先":"price", "便宜":"price", "均衡推荐":"balanced"}.items():
        if word in text:
            result["strategy"] = strategy
    match = re.search(r"预算\s*(\d+(?:\.\d+)?)\s*元",text)
    if match:
        result["budget_cny"] = float(match[1])
    if "严格" in text:
        result["budget_mode"] = "strict"
    elif "弹性" in text:
        result["budget_mode"] = "flexible"
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:kcal|千卡|大卡)",text,re.I)
    if match:
        clause = re.split(r"[，,。；]",text[:match.start()])[-1] + text[match.start():match.end()+3]
        hard = bool(re.search(r"≤|<=|不得超过|不超过|以内|内|控制|最多",clause))
        result["maximum_kcal" if hard else "energy_target_kcal"] = float(match[1])
    match = re.search(r"(?:蛋白质\s*(?:≥|>=|至少|不低于|约)?\s*(\d+(?:\.\d+)?)\s*g)|(\d+(?:\.\d+)?)\s*g\s*蛋白质",text,re.I)
    if match:
        value = float(match[1] or match[2])
        clause = re.split(r"[，,。；]",text[:match.start()])[-1] + match[0]
        hard = bool(re.search(r"≥|>=|至少|不低于|必须",clause))
        result["minimum_protein_g" if hard else "protein_target_g"] = value
        if hard:
            result["protein_minimum_hard"] = True
    match = re.search(r"([一两二三四五]|\d+)套",text)
    if match:
        result["recommendation_count"] = CN_COUNTS.get(match[1], int(match[1]) if match[1].isdigit() else 3)
    excluded = re.findall(r"(?:不吃|不要|去掉|排除)(牛肉|薯条|含糖饮料)",text)
    if excluded:
        result["excluded_foods"] = sorted(set(result.get("excluded_foods",[]) + excluded))
    if "高蛋白" in text and "protein_target_g" not in result:
        result["protein_target_g"] = 30  # explicit heuristic, soft and overridable
    return result


def replacement_request(previous_request, candidate, remove_ids):
    """Preserve the selected option's other food quantities and all old constraints."""
    result = dict(previous_request)
    result["previous_recommendation_id"] = candidate["recommendation_id"]
    result["required_quantities"] = {i["food"]["food_id"]:i["quantity"] for i in candidate["items"] if i["food"]["food_id"] not in remove_ids}
    result["excluded_foods"] = sorted(set(result.get("excluded_foods",[]) + list(remove_ids)))
    return result


def more_request(previous_request, candidates, count=2):
    result = dict(previous_request)
    result["recommendation_count"] = count
    result["exclude_signatures"] = sorted(set(result.get("exclude_signatures", []) + [c["recommendation_id"] for c in candidates]))
    compositions = list(result.get("exclude_compositions", []))
    for candidate in candidates:
        ids = sorted(i["food"]["food_id"] for i in candidate["items"])
        if ids not in compositions:
            compositions.append(ids)
    result["exclude_compositions"] = compositions
    return result
