"""JSON stdin/file CLI. No JSON shell interpolation and no network requests."""
import argparse
import csv
import io
import json
from dataclasses import asdict
from pathlib import Path
import sqlite3
import sys
from models import FoodItem, Profile, RecommendationRequest, ValidationError, construct
from language import parse_profile, parse_request, replacement_request, more_request
from normalize import normalize_foods
from nutrition import estimate
from optimizer import recommend
from orders import prepare_order
from reporting import report
from storage import Store
from mcp_policy import authorize, failure

COMMANDS = ("parse-profile", "parse-request", "save-profile", "get-profile", "nutrition-target", "normalize-foods",
            "recommend", "smoke", "replacement-request", "more-request", "prepare-order-import", "pending", "confirm-consumption",
            "retract-consumption", "report", "export", "delete", "cache-put", "cache-get", "clear-cache", "mcp-policy", "mcp-error")


def load_foods(data):
    return [construct(FoodItem,x) for x in data]


def execute(command, data, directory=None):
    if command == "parse-profile":
        return parse_profile(data["text"],data.get("existing"))
    if command == "parse-request":
        return parse_request(data["text"],data.get("previous"))
    if command == "replacement-request":
        return replacement_request(data["previous_request"],data["candidate"],data["remove_ids"])
    if command == "more-request":
        return more_request(data["previous_request"],data["candidates"],data.get("count",2))
    if command == "normalize-foods":
        return {"foods":normalize_foods(data),"synthetic":data["synthetic"]}
    if command == "mcp-policy":
        return authorize(**data)
    if command == "mcp-error":
        return failure(**data)
    if command in ("nutrition-target", "recommend", "smoke"):
        if "profile" in data:
            profile = construct(Profile,data["profile"])
        else:
            with Store(directory) as store:
                profile = store.profile(data["user_id"])
        overrides = data.get("request",{})
        if command == "smoke":
            overrides = parse_request(data["text"],overrides)
        request = RecommendationRequest.for_profile(profile,overrides)
        if command == "nutrition-target":
            return estimate(profile,request,data.get("meal_shares"))
        return recommend(profile,request,load_foods(data["foods"]))
    with Store(directory) as store:
        uid = data.get("user_id")
        confirmed = data.get("confirmed") is True
        if command == "save-profile":
            return store.save_profile(data["profile"],confirmed)
        if command == "get-profile":
            return asdict(store.profile(uid))
        if command == "prepare-order-import":
            if data["order"]["source"] != "manual":
                authorize(data["order"]["source"],data.get("history_consent",False),data.get("detail_consent",False))
            return store.prepare(uid,prepare_order(data["order"],load_foods(data["foods"]),data.get("aliases")))
        if command == "pending":
            return store.pending(uid)
        if command == "confirm-consumption":
            return store.confirm(uid,data["pending_id"],data["selections"],data["consumed_at"],confirmed,data.get("replace",False))
        if command == "retract-consumption":
            return store.retract(uid,data["pending_id"],confirmed)
        if command == "report":
            return report(store.entries(uid),data["period"],data["anchor"])
        if command == "export":
            return store.export(uid)
        if command == "delete":
            return store.delete(uid,confirmed)
        if command == "cache-put":
            return store.cache_put(data["key"],data["foods"])
        if command == "cache-get":
            return store.cache_get(data["key"],data.get("ttl_seconds",86400))
        if command == "clear-cache":
            return store.clear_cache()
    raise ValidationError("未知命令")


def csv_export(result):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["record_type","id","data_json"])
    # CSV exports profile + pending + entries; structured snapshots stay lossless JSON.
    for kind, rows in (("profile",[result["profile"]]),("pending",result["pending"]),("entry",result["entries"])):
        for row in rows:
            writer.writerow([kind,row.get("user_id",row.get("entry_id",row.get("id",""))),json.dumps(row,ensure_ascii=False,allow_nan=False)])
    return stream.getvalue()


def main(argv=None):
    if hasattr(sys.stdout,"reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="McFit：麦当劳中国单餐营养、本地记录；JSON 输入输出")
    parser.add_argument("command",choices=COMMANDS)
    parser.add_argument("--input",default="-",help="UTF-8 JSON 文件；- 为 stdin")
    parser.add_argument("--data-dir",help="私有数据目录；默认系统用户目录或 MCFIT_DATA_DIR")
    parser.add_argument("--format",choices=("json","csv"),default="json",help="csv 仅适用于 export")
    args = parser.parse_args(argv)
    try:
        if args.format == "csv" and args.command != "export":
            raise ValidationError("CSV 只用于 export")
        raw = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8-sig")
        data = json.loads(raw,parse_constant=lambda _: (_ for _ in ()).throw(ValidationError("JSON 非有限值")))
        if not isinstance(data,dict):
            raise ValidationError("顶层输入必须是 JSON 对象")
        result = execute(args.command,data,args.data_dir)
        print(csv_export(result) if args.format == "csv" else json.dumps(result,ensure_ascii=False,allow_nan=False,indent=2))
        return 0
    except (ValidationError,KeyError,TypeError,ValueError,OSError,sqlite3.Error) as exc:
        # Never emit the supplied body, credentials, order identifiers or traceback.
        message = str(exc) if isinstance(exc,ValidationError) else "输入/数据访问失败，请核对字段、类型、路径与权限。"
        print(json.dumps({"error":message},ensure_ascii=False),file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
