"""Strict historical new highs from the imported daily records."""
from psx_app.database.schema import get_connection
from psx_app.services.market_analytics1335 import refs
from psx_app.services.volume_index1339 import _date


def new_highs(db_path, date):
 date=_date(date)
 with get_connection(db_path) as c:
  source=refs(c)
  rows=c.execute('''SELECT e.symbol,e.trade_date,e.high,e.close,
      (SELECT MAX(p.high) FROM equity_ohlcv p WHERE p.symbol=e.symbol AND p.trade_date<e.trade_date AND p.high>0) previous_high,
      (SELECT MAX(p.close) FROM equity_ohlcv p WHERE p.symbol=e.symbol AND p.trade_date<e.trade_date AND p.close>0) previous_close,
      (SELECT MAX(p.close) FROM equity_ohlcv p WHERE p.symbol=e.symbol AND p.close>0) highest_close,
      (SELECT r.company FROM company_reference r WHERE r.list_name=? AND r.symbol=e.symbol) company
      FROM equity_ohlcv e WHERE e.trade_date=? ORDER BY e.symbol''',(source,date))
  out=[]
  for r in rows:
   symbol=r['symbol'];company=r['company'] or None
   if r['high'] is not None and r['previous_high'] is not None and r['high']>r['previous_high']:
    out.append({'symbol':symbol,'company':company,'price':r['high'],'previous':r['previous_high'],'record_type':'New All-Time High','date':date,'closing_ath':False})
   if r['close'] is not None and r['previous_close'] is not None and r['close']>r['previous_close']:
    out.append({'symbol':symbol,'company':company,'price':r['close'],'previous':r['previous_close'],'record_type':'New Closing High','date':date,'closing_ath':r['close']==r['highest_close']})
 return {'date':date,'rows':out}
