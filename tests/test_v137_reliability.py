"""Portable reliability regressions; all inputs are synthetic and no live database is used."""
import copy
from datetime import date,timedelta
import pytest
from psx_app.config import DEFAULT_SETTINGS
from psx_app.services.technical_service import TechnicalService
from psx_app.services.signal_reliability import build_trade_plan,annotate_freshness
from psx_app.services.historical_validation import validate_bars


def bars(n=300, beginning='2024-01-01'):
    out=[];d=date.fromisoformat(beginning)
    while len(out)<n:
        if d.weekday()<5:
            c=100+len(out)*0.04
            out.append(dict(trade_date=d.isoformat(),open=c,close=c,high=c+10,low=c-0.5,pr_close=c-0.04,volume=100000))
        d+=timedelta(days=1)
    return out


def test_strict_ema_vote_is_excluded_and_breakdown_reconciles():
    r=TechnicalService().calculate_series_for_bars('TEST',bars(70),settings=DEFAULT_SETTINGS)
    lat=r['latest'];sig=lat['signal']
    assert lat['ema200'] is None
    assert next(x for x in sig['indicator_breakdown'] if x['indicator']=='EMA 200')['vote']==0
    assert sig['score']==sum(x['vote'] for x in sig['indicator_breakdown'])
    assert sig['valid_indicators']==8
    assert r['series'][0]['ema9'] is None


def test_legacy_mode_explicitly_allows_warmup():
    cfg={**DEFAULT_SETTINGS,'strict_indicator_sufficiency':False}
    r=TechnicalService().calculate_series_for_bars('TEST',bars(70),settings=cfg)
    assert r['latest']['ema200'] is not None
    assert r['latest']['signal']['score']==sum(x['vote'] for x in r['latest']['signal']['indicator_breakdown'])


def test_full_history_calculated_before_chart_tail_and_ytd_is_current_year(tmp_path):
    from psx_app.database.schema import init_db,get_connection
    db=tmp_path/'x.db';init_db(db)
    data=bars(330,'2023-08-01')
    with get_connection(db) as c:
        c.executemany('INSERT INTO equity_ohlcv(symbol,trade_date,open,high,low,close,pr_close,volume) VALUES (?,?,?,?,?,?,?,?)', [('TEST',x['trade_date'],x['open'],x['high'],x['low'],x['close'],x['pr_close'],x['volume']) for x in data])
    r=TechnicalService(db).get_ticker_analysis('TEST',tail_bars=20)
    assert len(r['series'])==20 and r['latest']['bars_count']==330
    assert r['latest']['first_date']==data[0]['trade_date']
    assert r['latest']['rsi_ytd_high']['date'][:4]==data[-1]['trade_date'][:4]
    assert r['latest']['ema200_sufficient']


def test_no_completed_week_is_not_invented():
    assert TechnicalService.compute_weekly_pivots(bars(3))['pivots'] is None
    assert TechnicalService.compute_weekly_pivots(bars(5))['status']=='OK'


def test_strict_warning_uses_actual_history_start():
    r=TechnicalService().calculate_series_for_bars('TEST',bars(50,'2022-05-02'),settings=DEFAULT_SETTINGS)
    assert '2022-05-02' in r['latest']['warnings'][0]
    assert '01-Jan-2026' not in r['latest']['warnings'][0]


def test_structural_plan_never_fabricates_rr_and_measures_from_entry():
    b={'close':100,'ema21':97};p={'S1':96,'R1':107,'R2':110,'R3':113,'S2':94,'S3':90}
    r=build_trade_plan(b,p,'LONG');assert r['status']=='VALID' and r['risk_reward']==1.75
    r=build_trade_plan(b,p,'LONG',entry=105)
    assert r['status']=='NO TRADE' and r['target_1']==107
    assert r['risk_reward']==pytest.approx(2/9,abs=0.0001)
    assert build_trade_plan(b,p,None)['status']=='NO TRADE'
    assert build_trade_plan(b,{**p,'R1':99,'R2':99,'R3':99},'LONG')['status']=='NO TRADE'


def test_stale_data_preserves_historical_signal_but_blocks_opening_trade():
    item={'latest_date':'2026-10-21','signal':{'action':'BUY','trade_plan':{'status':'VALID'}}}
    annotate_freshness(item,'2026-10-22')
    assert item['data_freshness']['status']=='STALE'
    assert item['signal']['action']=='BUY' and item['signal']['trade_plan']['status']=='NO TRADE'


def test_indicator_series_is_prefix_invariant():
    data=bars(260);svc=TechnicalService()
    a=svc.calculate_series_for_bars('TEST',data[:210],settings=DEFAULT_SETTINGS)['series']
    b=svc.calculate_series_for_bars('TEST',data,settings=DEFAULT_SETTINGS)['series']
    assert a==b[:210]


def test_historical_audit_is_next_session_costed_and_nonoverlapping():
    r=validate_bars('TEST',bars(),DEFAULT_SETTINGS,fees_bps=10,slippage_bps=10)
    assert r['summary']['closed_trades']>0
    for t in r['trades']:
        assert t['signal_date']<t['entry_date']<=t['exit_date']
        raw=next(b for b in bars() if b['trade_date']==t['entry_date'])['open']
        assert t['entry']==pytest.approx(raw*1.001,abs=0.0001)
        check=(t['exit']*.999)/(t['entry']*1.001)-1
        assert t['net_return_pct']==pytest.approx(check*100,abs=0.0002)
    for a,b in zip(r['trades'],r['trades'][1:]):assert a['exit_date']<b['entry_date']
    free=validate_bars('TEST',bars(),DEFAULT_SETTINGS,fees_bps=0,slippage_bps=0)
    assert free['summary']['mean_net_return_pct']>r['summary']['mean_net_return_pct']


def test_end_date_audit_does_not_see_future_bars():
    data=bars();cut=data[200]['trade_date']
    a=validate_bars('TEST',data,DEFAULT_SETTINGS,end=cut)
    b=validate_bars('TEST',data[:201],DEFAULT_SETTINGS,end=cut)
    assert a==b


def test_stop_first_when_daily_candle_is_ambiguous(monkeypatch):
    data=bars(28)
    series=[{**b,'action':'HOLD','ema21':97} for b in data]
    series[25].update(action='BUY',close=100,high=110,low=99.5,ema21=97)
    series[26].update(open=100,high=120,low=90)
    monkeypatch.setattr(TechnicalService,'calculate_series_for_bars',lambda *a,**k:{'series':series})
    r=validate_bars('TEST',data,DEFAULT_SETTINGS,fees_bps=0,slippage_bps=0)
    assert r['trades'][0]['exit_reason']=='STOP' and r['trades'][0]['ambiguous_stop_target_bar']
    assert r['trades'][0]['net_return_pct']<0


def test_gap_stop_is_not_filled_at_an_unreachable_stop(monkeypatch):
    data=bars(29);series=[{**b,'action':'HOLD','ema21':97} for b in data]
    series[25].update(action='BUY',close=100,high=110,low=99.5,ema21=97)
    series[26].update(open=100,high=101,low=99)
    series[27].update(open=90,high=94,low=89)
    monkeypatch.setattr(TechnicalService,'calculate_series_for_bars',lambda *a,**k:{'series':series})
    r=validate_bars('TEST',data,DEFAULT_SETTINGS,fees_bps=0,slippage_bps=0)
    assert r['trades'][0]['exit_reason']=='GAP_STOP' and r['trades'][0]['exit']==90


def test_validation_empty_and_invalid_inputs_are_explicit():
    assert validate_bars('TEST',[],DEFAULT_SETTINGS)['summary']['win_rate_pct'] is None
    with pytest.raises(ValueError):validate_bars('TEST',bars(),DEFAULT_SETTINGS,start='2025-01-01',end='2024-01-01')
    with pytest.raises(ValueError):validate_bars('TEST',bars(),DEFAULT_SETTINGS,horizon=0)
    with pytest.raises(ValueError):validate_bars('TEST',bars()+bars(),DEFAULT_SETTINGS)


def test_old_futures_history_does_not_grant_current_eligibility(tmp_path):
    from psx_app.database.schema import init_db,get_connection
    db=tmp_path/'x.db';init_db(db);data=bars(60)
    with get_connection(db) as c:
        c.executemany('INSERT INTO equity_ohlcv(symbol,trade_date,open,high,low,close,volume) VALUES (?,?,?,?,?,?,?)',[('TEST',b['trade_date'],b['open'],b['high'],b['low'],b['close'],b['volume']) for b in data])
        c.execute('INSERT INTO futures_ohlcv(trade_date,contract_symbol,base_symbol,contract_month,close,volume) VALUES (?,?,?,?,?,?)',(data[0]['trade_date'],'TEST-JAN','TEST','JAN',100,1000))
    assert not TechnicalService(db).get_ticker_analysis('TEST')['latest']['is_futures_eligible']


def test_analyst_uses_full_history_and_excludes_incomplete_week(tmp_path):
    from psx_app.database.schema import init_db,get_connection
    from psx_app.services.intelligence_service import IntelligenceService
    db=tmp_path/'x.db';init_db(db);data=bars(403,'2024-01-01')
    with get_connection(db) as c:
        c.executemany('INSERT INTO equity_ohlcv(symbol,trade_date,open,high,low,close,volume) VALUES (?,?,?,?,?,?,?)',[('TEST',b['trade_date'],b['open'],b['high'],b['low'],b['close'],b['volume']) for b in data])
    r=IntelligenceService(db).run_automated_technical_analyst('TEST')
    assert r['latest']['bars_count']==403 and r['weekly_summary']['weeks_count']>40
    assert r['weekly_summary']['unfinished_week_excluded']
    assert r['weekly_summary']['recent_weeks'][-1]['end_date']<data[-1]['trade_date']


def test_old_indicator_cache_is_recomputed_after_engine_upgrade(tmp_path):
    import json
    from psx_app.database.schema import init_db,get_connection
    db=tmp_path/'x.db';init_db(db);data=bars(70)
    with get_connection(db) as c:
        c.executemany('INSERT INTO equity_ohlcv(symbol,trade_date,open,high,low,close,volume) VALUES (?,?,?,?,?,?,?)',[('ATRL',b['trade_date'],b['open'],b['high'],b['low'],b['close'],b['volume']) for b in data])
        c.execute('INSERT INTO indicator_cache(symbol,trade_date,rule_version,payload_json,updated_at) VALUES (?,?,?,?,?)',('ATRL',data[-1]['trade_date'],1,json.dumps({'engine_version':'1.3.6','symbol':'ATRL','close':9999}),'old'))
    items=TechnicalService(db).get_universe_summary(scope='all')['items']
    assert items[0]['close']==data[-1]['close'] and items[0]['engine_version']=='1.3.7'


def test_history_quality_flags_do_not_remove_or_adjust_rows():
    data=bars(260);data[50]['close']=300;data[40]['volume']=0
    r=TechnicalService().calculate_series_for_bars('TEST',data,settings=DEFAULT_SETTINGS)
    assert r['latest']['bars_count']==260 and r['series'][50]['close']==300
    assert r['latest']['history_quality']['large_close_changes_over_30pct']>=2
    assert r['latest']['history_quality']['zero_volume_sessions']==1


def test_validation_api_is_read_only_and_rejects_invalid_dates(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    import psx_app.main as main
    from psx_app.database.schema import init_db,get_connection
    db=tmp_path/'x.db';init_db(db);monkeypatch.setattr(main,'DB_PATH',db)
    client=TestClient(main.app)
    assert client.get('/api/technical/validation/ATRL?start=not-a-date').status_code==400
    assert client.get('/api/technical/validation/ATRL?horizon=0').status_code==422
    with get_connection(db) as c:before=c.execute('SELECT COUNT(*) FROM audit_events').fetchone()[0]
    r=client.get('/api/technical/validation/ATRL')
    assert r.status_code==200 and r.json()['summary']['closed_trades']==0
    with get_connection(db) as c:assert c.execute('SELECT COUNT(*) FROM audit_events').fetchone()[0]==before


def test_macd_signal_warmup_does_not_cast_a_hidden_vote():
    r=TechnicalService().calculate_series_for_bars('TEST',bars(28),settings=DEFAULT_SETTINGS)
    assert r['latest']['macd_hist'] is None
    macd=next(x for x in r['latest']['signal']['indicator_breakdown'] if x['indicator'].startswith('MACD'))
    assert macd['vote']==0 and 'N/A' in macd['value']
    assert r['latest']['signal']['score']==sum(x['vote'] for x in r['latest']['signal']['indicator_breakdown'])
