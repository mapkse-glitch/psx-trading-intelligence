"""Synthetic-only symbol identity, full-history price windows and volume deltas."""
from pathlib import Path
import pytest
from psx_app.database.schema import init_db, get_connection
from psx_app.services.market_explorer import MarketExplorer

@pytest.fixture
def market_db(tmp_path):
    p=tmp_path/'market.db';init_db(p)
    samples=[('2024-12-31',1000,1,100),('2025-01-01',900,2,110),
             ('2025-05-16',800,3,120),('2025-05-17',700,4,130),
             ('2025-08-14',600,5,140),('2025-08-15',500,6,150),
             ('2025-09-13',400,7,160),('2025-09-14',300,8,170),
             ('2025-10-13',200,9,180),('2025-10-14',100,10,200),
             ('2025-11-11',90,11,100),('2025-11-12',80,12,150)]
    with get_connection(p) as c:
        c.executemany('INSERT INTO equity_ohlcv(trade_date,symbol,high,low,volume,close,pr_close) VALUES (?,?,?,?,?,?,?)',[(d,'TEST',hi,lo,vol,50,40) for d,hi,lo,vol in samples])
        c.execute("INSERT INTO company_reference(list_name,symbol,company,sector) VALUES ('COMP_LIST','TEST','Fallback company','Fallback sector')")
        c.execute("INSERT INTO company_reference(list_name,symbol,company,sector) VALUES ('Sector Wise','TEST','Authentic Test Industries Limited','Industrial')")
    return p

def test_company_name_uses_imported_sector_wise_and_latest_prices(market_db):
    r=MarketExplorer(market_db).symbol('test',1)
    assert r['symbol']=='TEST' and r['company']['name']=='Authentic Test Industries Limited'
    assert r['company']['sector']=='Industrial' and 'Sector Wise' in r['company']['source']
    assert r['latest_symbol']['close']==50 and r['latest_symbol']['change']==10
    assert r['latest_symbol']['pct']==pytest.approx(25)
    assert r['latest_symbol']['trade_date']=='2025-11-12'
    assert r['latest_index'] is None

def test_ranges_include_boundaries_and_do_not_depend_on_records_filter(market_db):
    r=MarketExplorer(market_db).symbol('TEST',1)
    assert r['count']==1
    ranges=r['ranges']
    assert [w['high'] for w in ranges]==[80,100,300,500,700,900]
    assert [w['low'] for w in ranges]==[12,10,8,6,4,2]
    assert [w['start'] for w in ranges]==['2025-11-12','2025-10-14','2025-09-14','2025-08-15','2025-05-17','2025-01-01']
    assert ranges==MarketExplorer(market_db).symbol('TEST',6000)['ranges']
    assert ranges[0]['records']==1 and ranges[-1]['records']==11

def test_volume_change_fetches_previous_record_outside_display_limit(market_db):
    r=MarketExplorer(market_db).symbol('TEST',1)
    row=r['rows'][0]
    assert row['volume_pct']==50 and row['previous_volume']==100
    assert row['volume_baseline_date']=='2025-11-11'
    oldest=MarketExplorer(market_db).symbol('TEST',6000)['rows'][-1]
    assert oldest['volume_pct'] is None and oldest['volume_baseline_date'] is None

def test_index_volume_uses_previous_index_date_not_previous_displayed_symbol_date(market_db):
    with get_connection(market_db) as c:
        # No TEST stock record on Nov 10, but there is an index record that day.
        c.execute("INSERT INTO equity_ohlcv(trade_date,symbol,volume,close) VALUES ('2025-11-10','OTHER',50,10)")
        c.execute("INSERT INTO equity_ohlcv(trade_date,symbol,volume,close) VALUES ('2025-11-12','OTHER',50,10)")
        for dt,close,prior in [('2025-11-10',1000,900),('2025-11-12',1200,1000)]:
            c.execute('INSERT INTO index_ohlcv(trade_date,close,pr_close) VALUES (?,?,?)',(dt,close,prior))
        c.execute("INSERT INTO futures_ohlcv(trade_date,contract_symbol,base_symbol,contract_month,volume,close) VALUES ('2025-11-12','TEST-NOV','TEST','NOV',999999,999)")
    r=MarketExplorer(market_db).symbol('TEST',1)
    row=r['index_rows'][0]
    assert row['volume']==200 and row['volume_pct']==300
    assert row['previous_volume']==50 and row['volume_baseline_date']=='2025-11-10'
    assert r['latest_index']['close']==1200 and r['latest_index']['change']==200
    assert r['latest_index']['pct']==pytest.approx(20)

@pytest.mark.parametrize('current,previous,expected',[(0,100,-100),(100,0,None),(0,0,None),(100,-1,None)])
def test_zero_missing_and_invalid_prior_volumes_are_not_fabricated(market_db,current,previous,expected):
    with get_connection(market_db) as c:
        c.execute("UPDATE equity_ohlcv SET volume=? WHERE symbol='TEST' AND trade_date='2025-11-11'",(previous,))
        c.execute("UPDATE equity_ohlcv SET volume=? WHERE symbol='TEST' AND trade_date='2025-11-12'",(current,))
        for dt in ['2025-11-11','2025-11-12']:c.execute('INSERT INTO index_ohlcv(trade_date,close,pr_close) VALUES (?,1000,1000)',(dt,))
    r=MarketExplorer(market_db).symbol('TEST',1)
    assert r['rows'][0]['volume_pct']==expected
    assert r['index_rows'][0]['volume_pct']==expected

def test_latest_index_has_own_date_and_does_not_use_future_benchmark(market_db):
    with get_connection(market_db) as c:
        c.execute("INSERT INTO index_ohlcv(trade_date,close,pr_close) VALUES ('2025-11-10',2000,1990)")
        c.execute("INSERT INTO index_ohlcv(trade_date,close,pr_close) VALUES ('2025-11-13',9999,2000)")
    r=MarketExplorer(market_db).symbol('TEST',1)
    assert r['latest_index']['trade_date']=='2025-11-10' and r['latest_index']['close']==2000
    assert r['index_rows']==[] and r['missing_index_dates']==['2025-11-12']
    earlier=MarketExplorer(market_db).symbol('TEST',1,end='2025-10-14')
    assert earlier['latest_index'] is None and earlier['ranges'][0]['end']=='2025-10-14'

def test_no_data_and_fallback_company_name(market_db):
    assert MarketExplorer(market_db).symbol('MISSING',1)['status']=='NO_DATA'
    with get_connection(market_db) as c:
        c.execute("INSERT INTO equity_ohlcv(trade_date,symbol,high,low,volume,close) VALUES ('2025-11-12','ATRL',NULL,NULL,0,100)")
    r=MarketExplorer(market_db).symbol('ATRL',1)
    assert 'Attock' in r['company']['name']
    assert r['ranges'][0]['high'] is None and r['ranges'][0]['low'] is None

def test_frontend_symbol_and_index_headers_have_nine_and_eight_columns():
    js=(Path(__file__).resolve().parents[1]/'psx_app/static/upgrade139.js').read_text()
    assert "['Date','High','Low','Average','Close','Change','Change %','Volume','Volume (% Change)']" in js
    assert "['Date','Close','High','Low','Change','Change %','Volume','Volume (% Change)']" in js
    assert 'company-card1317' in js and 'latestMarketCard1317' in js and 'price-ranges1317' in js


def test_missing_cash_volume_on_previous_index_date_is_not_zero_filled(market_db):
    with get_connection(market_db) as c:
        for dt in ['2025-11-10','2025-11-12']:
            c.execute('INSERT INTO index_ohlcv(trade_date,close,pr_close) VALUES (?,1000,990)',(dt,))
    r=MarketExplorer(market_db).symbol('TEST',1)['index_rows'][0]
    assert r['volume']==150 and r['previous_volume'] is None and r['volume_pct'] is None
