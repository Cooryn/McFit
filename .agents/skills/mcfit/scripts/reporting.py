from datetime import date, datetime, timedelta, timezone
from models import METRICS, ValidationError, timestamp

CHINA_TZ = timezone(timedelta(hours=8))


def report(entries, period, anchor):
    day = date.fromisoformat(anchor)
    if period == "day":
        start, end = day, day + timedelta(days=1)
    elif period == "week":
        start = day - timedelta(days=day.weekday())
        end = start + timedelta(days=7)
    elif period == "month":
        start = day.replace(day=1)
        end = date(day.year + (day.month == 12),day.month % 12 + 1,1)
    else:
        raise ValidationError("统计周期必须是 day/week/month")
    selected = [e for e in entries if start <= timestamp(e["consumed_at"]).astimezone(CHINA_TZ).date() < end]
    metrics = {k:{"known_subtotal":0,"unknown_items":0,"known_items":0} for k in METRICS + ("amount_cny",)}
    items = [i for e in selected for i in e["items"]]
    for item in items:
        for key, m in metrics.items():
            v = item.get("amount_cny") if key == "amount_cny" else item["nutrition"].get(key)
            if v is None:
                m["unknown_items"] += 1
            else:
                m["known_subtotal"] += v
                m["known_items"] += 1
    for m in metrics.values():
        m["known_subtotal"] = round(m["known_subtotal"],3)
        m["coverage_ratio"] = m["known_items"]/len(items) if items else None
    return {"scope":"仅已确认、已记录的麦当劳摄入，非全天摄入或完整消费", "timezone":"Asia/Shanghai",
            "start":str(start),"end_exclusive":str(end),"entry_count":len(selected),"item_count":len(items),
            "synthetic_entries":sum(bool(e.get("synthetic")) for e in selected),"metrics":metrics}
