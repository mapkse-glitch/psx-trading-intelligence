"""Explicit disposable loopback PostgreSQL only; no production database access."""
import pytest
from test_v1314_postgres import remote
from test_v1324_futures_last import seed
from psx_app.database.schema import get_connection
from psx_app.services.futures_service import FuturesService

def test_latest_report_shared_cache_invalidates_on_source_revision(remote):
 from psx_app.database.turso import revision
 with get_connection() as c:seed(c)
 before=revision();service=FuturesService();first=service.get_last_data()
 assert first['rows_count']==5 and first['latest_date']=='2026-10-16'
 assert first['rows'][1]['days']==42 and first['rows'][1]['annualized_pct']==pytest.approx(10*365/42)
 assert service.get_last_data()==first and revision()==before
 with get_connection() as c:
  assert c.execute('SELECT COUNT(*) FROM analysis_cache').fetchone()[0]>=1
  c.execute("INSERT INTO futures_ohlcv(trade_date,contract_symbol,base_symbol,contract_month,close,volume) VALUES ('2026-12-16','NEW-JAN','NEW','JAN',12,100)")
 latest=service.get_last_data();assert latest['latest_date']=='2026-12-16' and latest['rows_count']==1
 assert latest['rows'][0]['rule_date']=='2027-01-29' and latest['rows'][0]['days']==44
 assert latest['rows'][0]['annualized_pct'] is None

def test_api_latest_ignores_browser_filter_params_and_old_process_cache(remote):
 with get_connection() as c:seed(c)
 from fastapi.testclient import TestClient
 import psx_app.main as main
 with TestClient(main.app) as client:
  r=client.get('/api/futures/last-data?selected_date=1900-01-01&days=1&apply_rolling=true').json()
  assert r['latest_date']=='2026-10-16' and r['rows'][0]['days']==14
  main._API_CACHE['fut_last']={'latest_date':'1900-01-01'}
  with get_connection() as c:
   c.execute("INSERT INTO futures_ohlcv(trade_date,contract_symbol,base_symbol,contract_month,close) VALUES ('2026-10-30','NEW-NOV','NEW','NOV',12)")
  new=client.get('/api/futures/last-data').json()
  assert new['latest_date']=='2026-10-30' and new['rows'][0]['days']==28
  # Old endpoints and rolling preview remain supported; removing the UI is not deletion.
  assert client.get('/api/futures/rolling-window-preview?months=2').status_code==200
