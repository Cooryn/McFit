"""Validated local interchange models, NOT a claim about the remote MCP schema."""
from dataclasses import dataclass, field, asdict, fields
from datetime import datetime, timezone
import math
import uuid


class ValidationError(ValueError):
    pass


def number(value, name, low=0, high=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValidationError(f"{name}: 需要有限数值")
    if value < low or (high is not None and value > high):
        raise ValidationError(f"{name}: 超出允许范围")
    return value


def choice(value, options, name):
    if value not in options:
        raise ValidationError(f"{name}: 无效选项")


def strings(value, name):
    if not isinstance(value, list) or any(not isinstance(s, str) or not s.strip() for s in value):
        raise ValidationError(f"{name}: 需要非空字符串列表")


def timestamp(value):
    try:
        t = datetime.fromisoformat(value)
        if t.tzinfo is None:
            raise ValueError()
        return t
    except (ValueError, TypeError):
        raise ValidationError("时间必须为含时区的 ISO 8601") from None


def now():
    return datetime.now(timezone.utc).isoformat()


def construct(cls, data):
    if not isinstance(data, dict) or set(data) - {f.name for f in fields(cls)}:
        raise ValidationError(f"{cls.__name__}: 非法字段或输入类型")
    try:
        return cls(**data)
    except TypeError:
        raise ValidationError(f"{cls.__name__}: 缺少必要字段或字段类型错误") from None


GOALS = ("gain_muscle", "lose_fat", "maintain", "recomposition")
MEALS = ("breakfast", "lunch", "dinner", "snack", "unspecified")
STRATEGIES = ("nutrition", "price", "balanced")
METRICS = ("kcal_per_serving", "protein_g", "fat_g", "carbs_g", "sodium_mg", "sugar_g")


@dataclass
class Profile:
    age_years: int
    height_cm: float
    weight_kg: float
    sex_for_equation: str
    goal_type: str
    activity_level: str
    user_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    target_weight_kg: float | None = None
    current_body_fat_pct: float | None = None
    target_body_fat_pct: float | None = None
    body_fat_method: str | None = None
    training_pattern: str | None = None
    resistance_training: bool = False
    activity_factor: float | None = None
    protein_g_per_kg: float | None = None
    default_meal_type: str = "unspecified"
    default_strategy: str = "balanced"
    default_budget_cny: float | None = None
    budget_mode: str = "flexible"
    exclusions: list[str] = field(default_factory=list)
    allergens: list[str] = field(default_factory=list)
    safety_flags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=now)
    updated_at: str = field(default_factory=now)

    def __post_init__(self):
        number(self.age_years, "年龄", 1, 120)
        if type(self.age_years) is not int:
            raise ValidationError("年龄需为整数周岁")
        number(self.height_cm, "身高 cm", 100, 230)
        number(self.weight_kg, "体重 kg", 25, 300)
        try:
            uuid.UUID(self.user_id)
        except (ValueError, TypeError, AttributeError):
            raise ValidationError("user_id 必须是本地 UUID") from None
        choice(self.sex_for_equation, ("plus5", "minus161"), "公式参数")
        choice(self.goal_type, GOALS, "目标")
        choice(self.activity_level, ("sedentary", "light", "moderate", "active"), "日常活动")
        choice(self.default_meal_type, MEALS, "餐次")
        choice(self.default_strategy, STRATEGIES, "策略")
        choice(self.budget_mode, ("strict", "flexible"), "预算模式")
        for key, lo, hi in [("target_weight_kg",25,300), ("current_body_fat_pct",1,70),
                            ("target_body_fat_pct",1,70), ("activity_factor",1.1,2.2),
                            ("protein_g_per_kg",0.8,2.0), ("default_budget_cny",0,10000)]:
            if getattr(self, key) is not None:
                number(getattr(self, key), key, lo, hi)
        for key in ("exclusions", "allergens", "safety_flags"):
            strings(getattr(self, key), key)
        if type(self.resistance_training) is not bool:
            raise ValidationError("resistance_training 必须是布尔值")
        timestamp(self.created_at)
        timestamp(self.updated_at)


@dataclass
class FoodItem:
    food_id: str
    name: str
    source: str
    observed_at: str
    kcal_per_serving: float | None = None
    protein_g: float | None = None
    fat_g: float | None = None
    carbs_g: float | None = None
    sodium_mg: float | None = None
    sugar_g: float | None = None
    variant: str = ""
    serving_qty: float = 1
    serving_unit: str = "份"
    match_confidence: str = "exact"
    price_cny: float | None = None
    price_status: str = "unavailable"
    price_scope: str | None = None
    price_source: str | None = None
    price_observed_at: str | None = None
    price_valid_until: str | None = None
    includes_discounts: bool | None = None
    includes_delivery: bool | None = None
    tags: list[str] = field(default_factory=list)
    ingredients_known: bool = False
    allergens: list[str] = field(default_factory=list)
    cross_contact: list[str] = field(default_factory=list)
    allergens_verified: bool = False
    kind: str = "single"
    synthetic: bool = False
    conversion: str = "每份原值"

    def __post_init__(self):
        if not all(isinstance(s, str) and s.strip() for s in (self.food_id, self.name, self.source)):
            raise ValidationError("餐品 ID、名称、来源不可为空")
        timestamp(self.observed_at)
        if self.source != "list-nutrition-foods" and not (self.synthetic and self.source == "synthetic-fixture"):
            raise ValidationError("仅接受官方营养来源或明确合成 fixture")
        for key in METRICS + ("price_cny",):
            if getattr(self, key) is not None:
                number(getattr(self, key), key)
        number(self.serving_qty, "每份数量", 0.001, 10000)
        choice(self.serving_unit, ("份", "g", "ml"), "份量单位")
        choice(self.match_confidence, ("exact", "reviewed", "uncertain"), "匹配置信度")
        choice(self.price_status, ("verified", "reference", "unavailable", "store_required"), "价格状态")
        choice(self.kind, ("single", "bundle"), "餐品类型")
        for key in ("tags", "allergens", "cross_contact"):
            strings(getattr(self, key), key)
        for key in ("synthetic", "ingredients_known", "allergens_verified"):
            if type(getattr(self, key)) is not bool:
                raise ValidationError(f"{key}: 需要布尔值")
        if self.price_status in ("verified", "reference"):
            if self.price_cny is None or not all((self.price_scope, self.price_source, self.price_observed_at, self.price_valid_until)):
                raise ValidationError("可用价格必须有金额、来源、范围、采样和失效时间")
            if type(self.includes_discounts) is not bool or type(self.includes_delivery) is not bool:
                raise ValidationError("必须说明优惠和配送费是否计入")
            if timestamp(self.price_valid_until) < timestamp(self.price_observed_at):
                raise ValidationError("价格时间区间错误")
        elif self.price_cny is not None:
            raise ValidationError("不可用价格必须为 null")
        if all(getattr(self, k) is not None for k in METRICS[:4]):
            energy = self.protein_g * 4 + self.carbs_g * 4 + self.fat_g * 9
            if abs(energy - self.kcal_per_serving) > max(30, self.kcal_per_serving * .25):
                raise ValidationError("能量与宏量营养明显矛盾，请核对单位/份量")
        if self.sugar_g is not None and self.carbs_g is not None and self.sugar_g > self.carbs_g + 1:
            raise ValidationError("糖不能明显高于总碳水")


@dataclass
class RecommendationRequest:
    meal_type: str = "unspecified"
    workout_context: str = "unknown"
    strategy: str = "balanced"
    energy_target_kcal: float | None = None
    protein_target_g: float | None = None
    fat_target_g: float | None = None
    carbs_target_g: float | None = None
    maximum_kcal: float | None = None
    minimum_protein_g: float | None = None
    protein_minimum_hard: bool = False
    excluded_foods: list[str] = field(default_factory=list)
    allergens: list[str] = field(default_factory=list)
    budget_cny: float | None = None
    budget_mode: str = "flexible"
    recommendation_count: int = 3
    max_types: int = 4
    max_quantity: int = 2
    flexible_ratio: float = .10
    flexible_cap_cny: float = 5
    previous_recommendation_id: str | None = None
    required_quantities: dict[str, int] = field(default_factory=dict)
    exclude_signatures: list[str] = field(default_factory=list)
    exclude_compositions: list[list[str]] = field(default_factory=list)

    def __post_init__(self):
        choice(self.meal_type, MEALS, "餐次")
        choice(self.workout_context, ("pre", "post", "rest", "unknown"), "训练场景")
        choice(self.strategy, STRATEGIES, "策略")
        choice(self.budget_mode, ("strict", "flexible"), "预算模式")
        for k in ("energy_target_kcal", "protein_target_g", "fat_target_g", "carbs_target_g", "maximum_kcal", "minimum_protein_g", "budget_cny", "flexible_ratio", "flexible_cap_cny"):
            if getattr(self, k) is not None:
                number(getattr(self, k), k)
        for k, hi in (("recommendation_count",10), ("max_types",4), ("max_quantity",2)):
            if type(getattr(self, k)) is not int:
                raise ValidationError(f"{k}: 需要整数")
            number(getattr(self, k), k, 1, hi)
        for k in ("excluded_foods", "allergens", "exclude_signatures"):
            strings(getattr(self, k), k)
        if not isinstance(self.exclude_compositions,list):
            raise ValidationError("exclude_compositions 需要列表")
        for composition in self.exclude_compositions:
            strings(composition,"食品组合")
        if type(self.protein_minimum_hard) is not bool:
            raise ValidationError("protein_minimum_hard 需要布尔值")
        if not isinstance(self.required_quantities, dict):
            raise ValidationError("required_quantities 需要对象")
        for k, v in self.required_quantities.items():
            if not isinstance(k, str) or type(v) is not int:
                raise ValidationError("保留餐品数量格式错误")
            number(v, "保留数量", 1, self.max_quantity)

    @classmethod
    def for_profile(cls, profile, overrides):
        return construct(cls, {"meal_type": profile.default_meal_type, "strategy": profile.default_strategy,
                               "budget_cny": profile.default_budget_cny, "budget_mode": profile.budget_mode, **overrides})
