"""SQLite transactions and portable private data. No token or raw order storage."""
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import uuid
from models import Profile, FoodItem, ValidationError, construct, now, number, timestamp
from orders import consumption_snapshot


def default_data_dir():
    configured = os.environ.get("MCFIT_DATA_DIR")
    if configured:
        return Path(configured).expanduser()
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()/"AppData"/"Local"))) / "McFit"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home()/".local"/"share"))) / "mcfit"


def encode(value):
    return json.dumps(value,ensure_ascii=False,allow_nan=False)


class Store:
    def __init__(self, directory=None):
        root = Path(directory) if directory is not None else default_data_dir()
        root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(root/"mcfit.sqlite3")
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA secure_delete=ON")
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS profiles(user_id TEXT PRIMARY KEY, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS user_settings(user_id TEXT PRIMARY KEY REFERENCES profiles ON DELETE CASCADE, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS food_catalog_cache(cache_key TEXT PRIMARY KEY, body TEXT NOT NULL, cached_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS pending_consumptions(
          id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES profiles ON DELETE CASCADE,
          source_key_hash TEXT NOT NULL, body TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
          UNIQUE(user_id,source_key_hash));
        CREATE TABLE IF NOT EXISTS consumption_entries(
          id TEXT PRIMARY KEY, pending_id TEXT NOT NULL UNIQUE REFERENCES pending_consumptions ON DELETE CASCADE,
          user_id TEXT NOT NULL REFERENCES profiles ON DELETE CASCADE, body TEXT NOT NULL);
        PRAGMA user_version=1;
        ''')

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def save_profile(self, data, confirmed=False):
        if confirmed is not True:
            raise ValidationError("档案保存/更新需要用户确认")
        profile = construct(Profile,data)
        old = self.db.execute("SELECT body FROM profiles WHERE user_id=?",(profile.user_id,)).fetchone()
        if old:
            profile.created_at = json.loads(old[0])["created_at"]
        profile.updated_at = now()
        settings = {k:getattr(profile,k) for k in ("default_strategy","default_budget_cny","budget_mode","exclusions","allergens")}
        with self.transaction():
            self.db.execute("INSERT INTO profiles VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET body=excluded.body",(profile.user_id,encode(asdict(profile))))
            self.db.execute("INSERT INTO user_settings VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET body=excluded.body",(profile.user_id,encode(settings)))
        return {"user_id":profile.user_id,"saved":True}

    def profile(self, user_id):
        row = self.db.execute("SELECT body FROM profiles WHERE user_id=?",(user_id,)).fetchone()
        if not row:
            raise ValidationError("未找到已确认档案")
        return construct(Profile,json.loads(row[0]))

    def prepare(self, user_id, pending):
        self.profile(user_id)
        identifier = str(uuid.uuid4())
        with self.transaction():
            self.db.execute("INSERT OR IGNORE INTO pending_consumptions VALUES(?,?,?,?, 'pending')",(identifier,user_id,pending["source_key_hash"],encode(pending)))
            row = self.db.execute("SELECT id,state FROM pending_consumptions WHERE user_id=? AND source_key_hash=?",(user_id,pending["source_key_hash"])).fetchone()
        return dict(row)

    def pending(self, user_id):
        return [{"id":r["id"],"state":r["state"],"data":json.loads(r["body"])} for r in
                self.db.execute("SELECT id,state,body FROM pending_consumptions WHERE user_id=?",(user_id,))]

    def confirm(self, user_id, pending_id, selections, consumed_at, confirmed=False, replace=False):
        if confirmed is not True:
            raise ValidationError("摄入/修改需要用户明确确认")
        with self.transaction():
            row = self.db.execute("SELECT body,state FROM pending_consumptions WHERE id=? AND user_id=?",(pending_id,user_id)).fetchone()
            if not row:
                raise ValidationError("待确认记录不存在")
            if row["state"] != "pending" and not replace:
                raise ValidationError("已确认/撤回记录不能重复记账；修改请显式 replace")
            snapshot = consumption_snapshot(json.loads(row["body"]),selections,consumed_at)
            existing = self.db.execute("SELECT id FROM consumption_entries WHERE pending_id=?",(pending_id,)).fetchone()
            identifier = existing[0] if existing else str(uuid.uuid4())
            self.db.execute("INSERT INTO consumption_entries VALUES(?,?,?,?) ON CONFLICT(pending_id) DO UPDATE SET body=excluded.body",(identifier,pending_id,user_id,encode(snapshot)))
            self.db.execute("UPDATE pending_consumptions SET state='confirmed' WHERE id=?",(pending_id,))
        return {"entry_id":identifier,"confirmed":True}

    def retract(self,user_id,pending_id,confirmed=False):
        if confirmed is not True:
            raise ValidationError("撤回需要确认")
        with self.transaction():
            row = self.db.execute("SELECT id FROM pending_consumptions WHERE id=? AND user_id=?",(pending_id,user_id)).fetchone()
            if not row:
                raise ValidationError("记录不存在")
            self.db.execute("DELETE FROM consumption_entries WHERE pending_id=? AND user_id=?",(pending_id,user_id))
            self.db.execute("UPDATE pending_consumptions SET state='retracted' WHERE id=?",(pending_id,))
        return {"retracted":True}

    def entries(self,user_id):
        return [{"entry_id":r["id"],**json.loads(r["body"])} for r in self.db.execute("SELECT id,body FROM consumption_entries WHERE user_id=?",(user_id,))]

    def cache_put(self,key,foods):
        validated = [asdict(construct(FoodItem,f)) for f in foods]
        with self.transaction():
            self.db.execute("INSERT INTO food_catalog_cache VALUES(?,?,?) ON CONFLICT(cache_key) DO UPDATE SET body=excluded.body,cached_at=excluded.cached_at",(key,encode(validated),now()))
        return {"cached":len(validated)}

    def cache_get(self,key,ttl_seconds=86400,at=None):
        number(ttl_seconds,"缓存期限",0)
        row = self.db.execute("SELECT body,cached_at FROM food_catalog_cache WHERE cache_key=?",(key,)).fetchone()
        if not row:
            return {"foods":[],"status":"missing"}
        at = at or datetime.now(timezone.utc)
        foods = json.loads(row[0])
        oldest = min([timestamp(row[1])] + [timestamp(f["observed_at"]) for f in foods])
        age = (at-oldest).total_seconds()
        return {"foods":foods,"cached_at":row[1],"status":"stale" if age > ttl_seconds or age < 0 else "fresh"}

    def clear_cache(self):
        with self.transaction():
            self.db.execute("DELETE FROM food_catalog_cache")
        return {"cleared":True}

    def export(self,user_id):
        return {"profile":asdict(self.profile(user_id)),"pending":self.pending(user_id),"entries":self.entries(user_id)}

    def delete(self,user_id,confirmed=False):
        if confirmed is not True:
            raise ValidationError("删除个人数据需要确认")
        with self.transaction():
            self.db.execute("DELETE FROM profiles WHERE user_id=?",(user_id,))
        self.db.execute("VACUUM")
        return {"deleted":True}
