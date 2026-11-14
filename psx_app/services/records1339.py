"""New records and estimated cap touches from imported market history."""
from psx_app.database.schema import get_connection
from psx_app.services.result_cache import persisted_result
from psx_app.services.volume_index1339 import _date
from psx_app.services.daily_summary import DailySummary, standard_band

class Records:
 def __init__(self,db_path=None): self.db_path=db_path
 @persisted_result
 def highs(self,date):
  date=_date(date)
  with get_connection(self.db_path) as c:
   rows=c.execute('''SELECT e.symbol,e.high,e.close,
       (SELECT MAX(p.high) FROM equity_ohlcv p WHERE p.symbol=e.symbol AND p.trade_date<e.trade_date AND p.high>0) previous_high,
       (SELECT MAX(p.close) FROM equity_ohlcv p WHERE p.symbol=e.symbol AND p.trade_date<e.trade_date AND p.close>0) previous_close
       FROM equity_ohlcv e WHERE e.trade_date=? ORDER BY e.symbol''',(date,))
   out=[]
   for r in rows:
    for field,prior,label in [('high','previous_high','New All-Time High'),('close','previous_close','New Closing High')]:
     if r[field] is not None and r[prior] is not None and r[field]>r[prior]:out.append({'symbol':r['symbol'],'price':r[field],'previous':r[prior],'record_type':label,'date':date})
  return {'date':date,'rows':out}

def new_highs(db_path,date): return Records(db_path).highs(date)

def estimated_caps(db_path,date):
 date=_date(date); report=DailySummary(db_path).report(date); upper=[]; lower=[]
 for r in report.get('rows',[]):
  base=r['pr_close'] if r['pr_close'] is not None and r['pr_close']>0 else r['previous_session_close']
  band=standard_band(date,base)
  if not band: continue
  for target,flag,rate in [(upper,'upper_touch',band[0]),(lower,'lower_touch',band[1])]:
   if r['limits'][flag] is True: target.append({'symbol':r['symbol'],'company':r['company'],'rate':float(rate)})
 return {'date':date,'upper':upper,'lower':lower,'basis':'standard_estimate',
         'status':report.get('status','NO_DATA'), 'coverage':{
          'upper': report.get('caps',{}).get('upper_touch',{}),
          'lower': report.get('caps',{}).get('lower_touch',{})}}
