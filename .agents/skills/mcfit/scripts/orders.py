"""Privacy-minimizing order-to-pending conversion. No account tools are called."""
from dataclasses import asdict
import hashlib
from models import METRICS, ValidationError, number, timestamp
from normalize import match_food


def prepare_order(order, foods, aliases=None):
    if not isinstance(order.get("source_key"), str) or not order["source_key"]:
        raise ValidationError("需要稳定来源键；手动记录使用随机 UUID")
    if order.get("source") not in ("order-list", "query-order", "manual"):
        raise ValidationError("不支持的记录来源")
    timestamp(order["ordered_at"])
    if order.get("status") not in ("paid", "completed", "cancelled", "refunded", "manual"):
        raise ValidationError("需明确订单状态")
    lines, seen = [], set()
    for row in order["items"]:
        line = row.get("line_id")
        if not isinstance(line,str) or not line or line in seen:
            raise ValidationError("订单行 ID 缺失或重复")
        if row.get("kind", "single") != "single":
            raise ValidationError("套餐必须先人工核对组成，不能与内部单品重复录入")
        seen.add(line)
        qty = number(row["quantity"], "订单数量", .001, 100)
        food, confidence = match_food(row, foods, aliases)
        # Do not retain addresses, contact info, raw order IDs or arbitrary raw fields.
        price = row.get("paid_unit_price_cny")
        if price is not None:
            number(price,"已付单价")
            if not row.get("price_source"):
                raise ValidationError("订单价格需要来源")
        lines.append({"line_id":line, "quantity":qty, "name":row["name"], "variant":row.get("variant", ""),
                      "match_confidence":confidence, "food":asdict(food) if food else None,
                      "paid_unit_price_cny":price, "price_source":row.get("price_source")})
    if not lines:
        raise ValidationError("订单条目为空")
    return {"source_key_hash":hashlib.sha256((order["source"]+":"+order["source_key"]).encode()).hexdigest(),
            "source":order["source"], "ordered_at":order["ordered_at"], "status":order["status"],
            "items":lines, "state":"pending", "synthetic":bool(foods and all(f.synthetic for f in foods))}


def consumption_snapshot(pending, selections, consumed_at):
    timestamp(consumed_at)
    if pending["status"] in ("cancelled", "refunded"):
        raise ValidationError("取消/退款订单不能直接确认摄入；如确实吃过，请手动补录并核实金额")
    rows = {i["line_id"]:i for i in pending["items"]}
    items, seen = [], set()
    for selection in selections:
        key = selection["line_id"]
        if key not in rows or key in seen:
            raise ValidationError("选中的订单行不存在或重复")
        seen.add(key)
        row = rows[key]
        qty = number(selection["consumed_quantity"],"实际食用份数",0,row["quantity"])
        if qty == 0:
            continue
        food = row["food"]
        reliable = food is not None and row["match_confidence"] in ("exact","reviewed") and food["match_confidence"] in ("exact","reviewed")
        nutrients = {k:food[k]*qty if reliable and food[k] is not None else None for k in METRICS}
        # Paid amount is explicitly confirmed, not inferred from fraction eaten.
        amount = selection.get("amount_cny")
        if amount is not None:
            number(amount,"归属于本记录的实际金额")
        items.append({"line_id":key,"name":row["name"],"variant":row["variant"],"quantity":qty,
                      "nutrition":nutrients,"amount_cny":amount,"price_source":"user_confirmed" if amount is not None else None,
                      "nutrition_source":food["source"] if reliable else None,
                      "nutrition_observed_at":food["observed_at"] if reliable else None,
                      "match_confidence":row["match_confidence"]})
    if not items:
        raise ValidationError("未确认任何实际食用份数；可撤回待确认记录")
    return {"consumed_at":consumed_at,"items":items,"synthetic":pending["synthetic"],"source":pending["source"]}
