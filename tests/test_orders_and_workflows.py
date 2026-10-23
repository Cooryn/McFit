from dataclasses import asdict
from pathlib import Path
import json
import subprocess
import sys
import pytest
from cli import execute, csv_export
from mcp_policy import authorize, failure, ALLOWED
from models import ValidationError


@pytest.mark.parametrize('text',[
    '推荐一顿麦当劳午餐',
    '刚练完胸，午餐热量控制在650 kcal内，蛋白质至少30g，不要牛肉',
    '预算25元，价格优先，不要薯条，只看一套',
])
def test_natural_language_to_output_smoke(text,fixture_data):
    result=execute('smoke',{**fixture_data,'text':text})
    assert result['synthetic'] is True
    rows=result['recommendations']+result['over_budget_alternatives']+result['unverified_price_alternatives']
    assert rows
    assert all(r['totals']['kcal_per_serving'] is not None for r in rows)
    if '650' in text:
        assert all(r['totals']['kcal_per_serving']<=650 and r['totals']['protein_g']>=30 for r in rows)


def test_policy_and_simulated_call_log():
    log=[]
    for tool in ('list-nutrition-foods','order-list','query-order'):
        with_consent=tool != 'list-nutrition-foods'
        assert authorize(tool,with_consent,with_consent)['allowed']
        log.append(tool)
    assert set(log)<=ALLOWED
    for tool in ('create-order','cancel-order','calculate-price','query-meals','auto-bind-coupons','draw-lottery'):
        with pytest.raises(ValidationError):authorize(tool,True,True)
    with pytest.raises(ValidationError):authorize('order-list')
    with pytest.raises(ValidationError):authorize('query-order',True)


@pytest.mark.parametrize('status',[401,'missing_token',429,'timeout'])
def test_mcp_failures(status):
    result=failure(status)
    assert result['message']
    if status==429:
        assert failure(status,1,30)['wait_seconds']==30
        assert not failure(status,3)['retry']
    else:assert not result['retry']


def test_cli_subprocess_smoke_and_errors(fixture_data,tmp_path):
    cli=Path(__file__).resolve().parents[1]/'.agents/skills/mcfit/scripts/cli.py'
    def run(body):
        return subprocess.run([sys.executable,str(cli),'smoke','--data-dir',str(tmp_path)],input=body,text=True,encoding='utf-8',capture_output=True)
    p=run(json.dumps(fixture_data,ensure_ascii=False))
    assert p.returncode==0,p.stderr
    assert json.loads(p.stdout)['synthetic']
    p=run('{"profile":{"secret":"DO-NOT-ECHO"}}')
    assert p.returncode==2 and 'DO-NOT-ECHO' not in p.stderr


def test_manual_workflow_export_and_delete(tmp_path,fixture_data):
    uid=execute('save-profile',{'profile':fixture_data['profile'],'confirmed':True},tmp_path)['user_id']
    order={'source':'manual','source_key':'SYNTHETIC-MANUAL','status':'manual','ordered_at':'2026-10-23T12:00:00+08:00',
           'items':[{'line_id':'1','food_id':'a','name':'合成鸡肉主食','quantity':1}]}
    pid=execute('prepare-order-import',{'user_id':uid,'order':order,'foods':fixture_data['foods']},tmp_path)['id']
    execute('confirm-consumption',{'user_id':uid,'pending_id':pid,'confirmed':True,'consumed_at':'2026-10-23T12:30:00+08:00',
                                  'selections':[{'line_id':'1','consumed_quantity':1,'amount_cny':18}]},tmp_path)
    result=execute('export',{'user_id':uid},tmp_path)
    assert len(result['entries'])==1 and 'profile' in csv_export(result)
    execute('delete',{'user_id':uid,'confirmed':True},tmp_path)
    assert not execute('pending',{'user_id':uid},tmp_path)
