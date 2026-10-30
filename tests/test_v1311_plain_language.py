"""Data-dependent explanations, honest unknowns, derived volumes and calendar safety."""
import json, subprocess, shutil
from pathlib import Path
import pytest
from psx_app.database.schema import init_db, get_connection
from psx_app.services.market_explorer import MarketExplorer
from psx_app.services.plain_language import analysis_guide, forecast_display

ROOT=Path(__file__).resolve().parents[1]

def latest(close=100):
    return dict(symbol='TEST',close=close,change_pct=-1.2,volume=1000,bars_count=300,first_date='2020-01-01',latest_date='2026-10-23',
                ema9=110,ema21=108,ema50=106,ema200=90,sma20=109,sma50=105,rsi14=39,macd_hist=-2,
                data_freshness={'status':'CURRENT'},signal={'score':-4,'combined_signal':'SELL'},daily_pivots={'classic':{'S1':95,'P':99,'R1':103,'R2':108}})

def contract(valid=False,side='LONG'):
    return dict(status='CONDITIONAL' if valid else 'NO TRADE',side=side if valid else None,
                entry_low=99.75,entry_high=100.25,stop=98 if side=='LONG' else 102,target_1=105 if side=='LONG' else 95,target_2=None,
                reason='Directional levels valid.' if valid else 'No opening-trade signal. SELL means reduce an existing holding, not open a short.')

def test_no_trade_uses_reasons_not_fabricated_levels():
    g=analysis_guide(latest(),contract(),{})
    assert not g['levels_active'] and g['action']=='WAIT — NO NEW TRADE'
    assert 'no valid entry' in g['stop_loss'] and 'no valid entry' in g['take_profit']
    assert 'No new-trade stop' in g['stop_loss']
    assert 'shares you already own' in g['sell_existing'] and 'Do not open a short' in g['short']
    assert '98.00' not in g['stop_loss']  # A rejected plan's reference is not an active stop.

def test_valid_buy_and_short_show_correct_timing_and_directions():
    buy=analysis_guide(latest(),contract(True),{})
    assert '99.75 PKR' in buy['buy'] and '100.25 PKR' in buy['buy']
    assert 'opening price' in buy['buy'] and '98.00 PKR' in buy['stop_loss']
    assert '105.00 PKR' in buy['take_profit'] and '10th trading record' in buy['take_profit']
    short=analysis_guide(latest(),contract(True,'SHORT'),{})
    assert 'broker confirms' in short['short'] and 'Buy back' in short['stop_loss']
    assert 'Do not open a new buy' in short['buy'] and '102.00 PKR' in short['stop_loss']
    assert '95.00 PKR' in short['take_profit']

@pytest.mark.parametrize('change,word',[(2.5,'rose'),(-3.5,'fell'),(0,'unchanged')])
def test_explanation_updates_from_actual_values(change,word):
    lat=latest(200);lat['change_pct']=change;lat['ema9']=190
    a={'weekly_summary':{'change_4w_pct':6.3},'trend_line':{'slope_pkr_per_day':2.2}}
    g=analysis_guide(lat,contract(),a)
    assert '200.00 PKR' in g['steps'][0]['detail'] and word in g['steps'][0]['detail']
    assert '6.30%' in g['steps'][0]['detail'] and 'upward' in g['steps'][1]['detail']
    assert 'ATRL' not in json.dumps(g)

@pytest.mark.parametrize('status',['STALE','ZERO_VOLUME'])
def test_bad_data_cannot_produce_action(status):
    lat=latest()
    if status=='STALE':lat['data_freshness']['status']='STALE'
    else:lat['volume']=0
    g=analysis_guide(lat,contract(True),{})
    assert not g['levels_active'] and g['action'].startswith('WAIT')
    assert 'No new-trade stop' in g['stop_loss']

@pytest.mark.parametrize('status',['PENDING','OPEN','NO_TRADE','NOT_TRIGGERED','AMBIGUOUS','INSUFFICIENT_DATA'])
def test_unresolved_or_no_trade_has_no_fake_profit(status):
    r=forecast_display({'status':status,'net_return_pct':0})
    assert r['return_value'] is None and r['return_note']

@pytest.mark.parametrize('status',['STOP_REACHED','TARGET_REACHED','HORIZON_CLOSED'])
@pytest.mark.parametrize('value',[-2.5,0,3.2])
def test_closed_returns_keep_sign_and_real_zero(status,value):
    assert forecast_display({'status':status,'net_return_pct':value})['return_value']==value


def test_market_volume_sums_all_cash_not_futures_or_accounts(tmp_path):
    p=tmp_path/'app.db';init_db(p)
    with get_connection(p) as c:
        for dt in ['2026-10-22','2026-10-23']:
            for sym,v in [('ATRL',10),('PRL',20),('ZERO',0)]:
                c.execute('INSERT INTO equity_ohlcv(trade_date,symbol,volume,pr_close,open,high,low,close) VALUES (?,?,?,?,?,?,?,?)',(dt,sym,v,99,100,101,98,100))
            c.execute('INSERT INTO index_ohlcv(trade_date,close,pr_close) VALUES (?,?,?)',(dt,1000,999))
            c.execute('INSERT INTO futures_ohlcv(trade_date,contract_symbol,base_symbol,contract_month,volume,close) VALUES (?,?,?,?,?,?)',(dt,'ATRL-OCT','ATRL','OCT',99999,100))
        c.commit()
    s=MarketExplorer(p);r=s.symbol('ATRL',1,'2026-10-25')
    assert r['last']=='2026-10-23' and len(r['index_rows'])==1
    assert r['index_rows'][0]['volume']==30 and r['index_rows'][0]['volume_symbols']==3
    assert s.volume('2026-10-23')['total']==30
    assert 'not verified index-constituent' in r['benchmark_note']
    # Earlier date excludes later volume; zero remains a real value, not a missing value.
    with get_connection(p) as c:c.execute('UPDATE equity_ohlcv SET volume=0');c.commit()
    assert s.symbol('ATRL',1,'2026-10-22')['index_rows'][0]['volume']==0
    assert s.symbol('ATRL',1,'2026-10-21')['status']=='NO_DATA'


@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js required for frontend helper tests')
def test_calendar_resolves_only_backward_and_invalid_is_not_latest():
    js=(ROOT/'psx_app/static/display1311.js').read_text()
    script=js+'''\nconst assert=require('node:assert/strict');
const dates=['2026-10-23','2026-10-22','2026-10-19'];
assert.equal(resolveCalendar1311('2026-10-25',dates),'2026-10-23');
assert.equal(resolveCalendar1311('2026-10-21',dates),'2026-10-19');
assert.equal(resolveCalendar1311('2026-10-18',dates),null);
assert.equal(resolveCalendar1311('2026-02-30',dates),null);
assert.equal(resolveCalendar1311('not-a-date',dates),null);
assert.equal(numericValue1311('-2,500.20%'),-2500.2);
assert.equal(numericValue1311('2026-10-23'),null);
assert.equal(numericValue1311('Not available'),null);
assert.equal(numericValue1311('0.00'),0);
'''
    subprocess.run(['node','-e',script],check=True,capture_output=True)


def test_build_has_matching_version_exact_colours_and_calendar_controls():
    import re
    html=(ROOT/'psx_app/static/index.html').read_text();css=(ROOT/'psx_app/static/styles.css').read_text()
    assert 'content="1.3.19"' in html and '/display1311.js?v=1.3.19' in html
    assert set(re.findall(r'--pos-green:\s*(#[A-Fa-f0-9]{6})',css))=={'#03D815'}
    assert set(re.findall(r'--neg-red:\s*(#[A-Fa-f0-9]{6})',css))=={'#F63131'}
    app=(ROOT/'psx_app/static/app.js').read_text();ui=(ROOT/'psx_app/static/upgrade139.js').read_text()
    assert 'accountCalendar1311' in app and 'futuresCalendar1311' in app
    assert 'id="marketAsOf1311"' not in ui
    assert 'calendar-only1312' in ui
    assert "['Check after'" not in ui or 'Horizon' in ui
    assert 'What to do now' in ui and 'Why' in ui
    assert 'p.status===\'CONDITIONAL\'?[[\'Entry\'' in ui  # No rejected execution levels on charts.


@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js required for frontend helper tests')
def test_scan_diagnostics_renderer_handles_rows_not_string_concatenation():
    js=(ROOT/'psx_app/static/upgrade139.js').read_text()
    script='''const vm=require('node:vm'),assert=require('node:assert/strict');
const context={state:{technical:{}},VIEW_TITLES:{},escapeHtml:v=>String(v??''),fmtInt:String,fmtDate:String};
vm.createContext(context);
'''+ 'vm.runInContext('+json.dumps(js)+''',context);
const out=vm.runInContext(`scanDiagnostics140({scan_counts:{analyzed:1},diagnostics:[{symbol:'TEST',bars_count:200,first_date:'2020-01-01',latest_date:'2026-10-23',score:-4,raw_signal:'SELL',status:'REJECTED',reasons:[{code:'NO_VALID_PLAN',reason:'No opening-trade signal.'}]}]})`,context);
assert(out.includes('What to do now'));assert(out.includes('Price history and indicator votes'));assert(out.includes('TEST'));
const empty=vm.runInContext('scanDiagnostics140({diagnostics:[]})',context);assert(empty.includes('No cash history matched'));
'''
    subprocess.run(['node','-e',script],check=True,capture_output=True)


def test_analyst_api_delivers_dynamic_action_guide(tmp_path,monkeypatch):
    from datetime import date,timedelta
    from fastapi.testclient import TestClient
    import psx_app.main as main
    p=tmp_path/'app.db';init_db(p)
    with get_connection(p) as c:
        for i in range(60):
            dt=(date(2026,1,1)+timedelta(days=i)).isoformat();px=100+i*.4
            c.execute('INSERT INTO equity_ohlcv(trade_date,symbol,close,high,low,open,volume,pr_close) VALUES (?,?,?,?,?,?,?,?)',(dt,'TEST',px,px+1,px-1,px,1000,px-.4))
        c.commit()
    monkeypatch.setattr(main,'DB_PATH',p);main._API_CACHE.clear()
    try:
        r=TestClient(main.app).get('/api/intelligence/automated-analyst/TEST')
        assert r.status_code==200
        a=r.json();g=a['action_guide']
        assert g['history']['records']==60 and g['as_of']==a['latest']['latest_date']
        assert f"{a['latest']['close']:,.2f} PKR" in g['steps'][0]['detail']
        assert all(k in g for k in ('buy','sell_existing','short','take_profit','stop_loss','when_not_to_buy'))
    finally:main._API_CACHE.clear()
