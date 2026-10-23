"""Host-side policy helpers; deliberately no network client or credential handling."""
from models import ValidationError, number

ALLOWED = frozenset(("list-nutrition-foods", "order-list", "query-order"))


def authorize(tool, history_consent=False, detail_consent=False):
    if tool not in ALLOWED:
        raise ValidationError("工具不在 McFit 只读白名单")
    if tool in ("order-list", "query-order") and history_consent is not True:
        raise ValidationError("读取历史订单需用户明确授权")
    if tool == "query-order" and detail_consent is not True:
        raise ValidationError("补齐订单明细需用户同意")
    return {"allowed":True, "tool":tool}


def failure(status, attempt=0, retry_after=None):
    if type(attempt) is not int or attempt < 0:
        raise ValidationError("重试次数无效")
    if status in (401, "missing_token"):
        return {"retry":False, "message":"请检查AI 宿主的凭据配置或进程环境变量 MCD_MCP_TOKEN，勿粘贴 Token 到聊天或仓库。"}
    if status == 429:
        if retry_after is not None:
            number(retry_after,"Retry-After")
        delay = max(2**min(attempt,6), retry_after or 0)
        return {"retry":attempt < 3, "wait_seconds":delay, "message":"限流：遵守 Retry-After，最多重试三次；等待过长则结束本次查询。"}
    return {"retry":False, "message":"服务超时/不可用；使用明确标注时间的缓存或停止真实推荐，不伪造实时数据。"}
