"""Strict local bridge v1; Codex maps inspected tool output to this contract."""
from dataclasses import asdict
from models import FoodItem, ValidationError, METRICS, construct, number


def normalize_foods(envelope):
    if envelope.get("bridge_version") != 1 or envelope.get("mapping_reviewed") is not True:
        raise ValidationError("需要经 schema 核对的 bridge_version=1 本地桥接输入")
    if type(envelope.get("synthetic")) is not bool:
        raise ValidationError("必须明确 synthetic 布尔标记")
    if not isinstance(envelope.get("foods"), list):
        raise ValidationError("foods 必须是列表")
    result, seen = [], set()
    for original in envelope["foods"]:
        row = dict(original)
        basis = row.pop("basis", None)
        unit = row.pop("energy_unit", None)
        weight = row.pop("serving_mass_g", None)
        energy = row.pop("energy", None)
        if basis not in ("per_serving", "per_100g") or unit not in ("kcal", "kJ"):
            raise ValidationError("必须明确每份/每100g及能量单位 kcal/kJ")
        factor = 1
        if basis == "per_100g":
            factor = number(weight, "每份克数", .001, 10000) / 100
        if energy is not None:
            number(energy, "能量")
        if "kcal_per_serving" in row:
            raise ValidationError("桥接输入不能同时包含 energy 和 kcal_per_serving")
        row["kcal_per_serving"] = None if energy is None else energy / (4.184 if unit == "kJ" else 1)
        for k in METRICS:
            v = row.get(k)
            if v is not None:
                row[k] = number(v, k) * factor
        row["synthetic"] = envelope["synthetic"]
        row["conversion"] = f"{basis}, {unit}; 营养乘 {factor:g}, 能量除 {4.184 if unit == 'kJ' else 1}"
        food = construct(FoodItem, row)
        if food.food_id in seen:
            raise ValidationError("重复 food_id，请先核对分页/规格，不能重复累加")
        seen.add(food.food_id)
        result.append(asdict(food))
    return result


def match_food(item, foods, aliases=None):
    by_id = {f.food_id: f for f in foods}
    if item.get("food_id") in by_id:
        return by_id[item["food_id"]], "exact"
    # Alias key includes variant: similar names are not sufficient evidence.
    key = item.get("name", "") + "|" + item.get("variant", "")
    target = (aliases or {}).get(key)
    if target in by_id:
        return by_id[target], "reviewed"
    return None, "uncertain"
