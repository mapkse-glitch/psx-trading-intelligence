"""PostgreSQL adapter parity and revision-cache tests on guarded loopback only."""
import pytest
from test_v1314_postgres import remote
from test_v1325_performance import seed
from psx_app.database.schema import get_connection
from psx_app.services.market_performance import MarketPerformance

def test_weekday_sql_shared_cache_and_canonical_revision(remote):
 from psx_app.database.turso import revision
 with get_connection() as c:seed(c)
 before=revision();service=MarketPerformance();r=service.report('weekly','2026-W44')
 assert r['index']['change']==50 and r['coverage']['volume']==230
 assert r['coverage']['eligible']==3 and len(r['combo']['buckets'])==5
 assert r['combo']['buckets'][0]['index_change']==10
 assert service.report('weekly','2026-W44')==r and revision()==before
 with get_connection() as c:
  assert c.execute('SELECT COUNT(*) FROM analysis_cache').fetchone()[0]>=1
  c.execute("UPDATE equity_ohlcv SET close=120 WHERE trade_date='2026-10-30' AND symbol='AAA'")
 changed=service.report('weekly','2026-W44')
 chart=next(x for x in changed['charts'] if x['id']=='scrip_PKR_gainers')
 assert chart['rows'][0]['value']==20 and revision()!=before

@pytest.mark.parametrize('kind',['daily','monthly','quarterly','halfyear','ninemonth','yearly'])
def test_all_periods_on_postgres(remote,kind):
 with get_connection() as c:seed(c)
 r=MarketPerformance().report(kind)
 assert r['status']=='OK' and len(r['charts'])==8
 assert MarketPerformance().report(kind)==r
