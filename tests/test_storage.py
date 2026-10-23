from dataclasses import asdict, replace
from datetime import datetime, timezone
import pytest
from models import ValidationError
from storage import Store
from orders import prepare_order
from reporting import report


def order():
    return {"source":"order-list","source_key":"SYNTHETIC-PRIVATE-ID","ordered_at":"2026-10-23T12:00:00+08:00","status":"completed",
            "address":"MUST-NOT-PERSIST","phone":"MUST-NOT-PERSIST","items":[
                {"line_id":"1","food_id":"a","name":"合成鸡肉主食","quantity":2},
                {"line_id":"2","name":"未匹配合成食品","quantity":1}]}


def test_profile_confirm_export_delete(tmp_path,profile):
    with Store(tmp_path) as s:
        with pytest.raises(ValidationError): s.save_profile(asdict(profile))
        assert s.db.execute("select count(*) from profiles").fetchone()[0] == 0
        s.save_profile(asdict(profile),True)
        s.save_profile(asdict(replace(profile,weight_kg=66)),True)
        assert s.export(profile.user_id)["profile"]["weight_kg"] == 66
        with pytest.raises(ValidationError): s.delete(profile.user_id)
        s.delete(profile.user_id,True)
        assert s.db.execute("select count(*) from user_settings").fetchone()[0] == 0


def test_pending_confirm_dedupe_partial_replace_retract(tmp_path,profile,foods):
    with Store(tmp_path) as s:
        uid=profile.user_id
        s.save_profile(asdict(profile),True)
        p=prepare_order(order(),foods)
        pid=s.prepare(uid,p)["id"]
        assert s.prepare(uid,p)["id"] == pid
        assert not s.entries(uid)
        selections=[{"line_id":"1","consumed_quantity":.5,"amount_cny":9},{"line_id":"2","consumed_quantity":1}]
        with pytest.raises(ValidationError): s.confirm(uid,pid,selections,"2026-10-23T12:30:00+08:00")
        s.confirm(uid,pid,selections,"2026-10-23T12:30:00+08:00",True)
        with pytest.raises(ValidationError): s.confirm(uid,pid,selections,"2026-10-23T12:30:00+08:00",True)
        assert len(s.entries(uid)) == 1
        for period in ("day","week","month"):
            r=report(s.entries(uid),period,"2026-10-23")
            assert r["metrics"]["protein_g"]["known_subtotal"] == 15
            assert r["metrics"]["protein_g"]["unknown_items"] == 1
            assert r["metrics"]["amount_cny"]["known_subtotal"] == 9
            assert r["metrics"]["amount_cny"]["coverage_ratio"] == .5
        s.confirm(uid,pid,[{"line_id":"1","consumed_quantity":1}],"2026-10-23T12:30:00+08:00",True,True)
        assert report(s.entries(uid),"day","2026-10-23")["metrics"]["protein_g"]["known_subtotal"] == 30
        s.retract(uid,pid,True)
        assert not s.entries(uid)
        assert s.prepare(uid,p)["state"] == "retracted"
        assert "MUST-NOT-PERSIST" not in str(s.export(uid)) and "SYNTHETIC-PRIVATE-ID" not in str(s.export(uid))


def test_cancelled_refunded_and_rollback(tmp_path,profile,foods):
    with Store(tmp_path) as s:
        s.save_profile(asdict(profile),True)
        for state in ("cancelled","refunded"):
            d=order();d["status"]=state;d["source_key"]=state
            pid=s.prepare(profile.user_id,prepare_order(d,foods))["id"]
            with pytest.raises(ValidationError):
                s.confirm(profile.user_id,pid,[{"line_id":"1","consumed_quantity":1}],"2026-10-23T12:00:00+08:00",True)
        assert not s.entries(profile.user_id)


def test_cache_age_based_on_observation(tmp_path,foods):
    with Store(tmp_path) as s:
        s.cache_put('nutrition',[asdict(f) for f in foods])
        r=s.cache_get('nutrition',86400,datetime(2026,10,23,tzinfo=timezone.utc))
        assert r['status']=='stale'
        s.clear_cache()
        assert s.cache_get('nutrition')['status']=='missing'


def test_timezones_and_empty():
    assert report([],"day","2026-10-23")["metrics"]["protein_g"]["coverage_ratio"] is None
    e={"consumed_at":"2026-10-22T17:00:00+00:00","items":[]}
    assert report([e],"day","2026-10-23")["entry_count"]==1
