"""Aligned, read-only imported closing-price comparisons."""
from datetime import date
import math
from psx_app.database.schema import get_connection
from psx_app.services.result_cache import persisted_result


def valid(v):
    return isinstance(v,(int,float)) and math.isfinite(v) and v>0


def compare(dates, left, right, labels):
    # Begin and end on common observations, never synthesize missing values.
    common=[d for d in dates if valid(left.get(d)) and valid(right.get(d))]
    if not common:return {'status':'NO_OVERLAP','labels':labels,'rows':[]}
    begin,end=common[0],common[-1]; window=[d for d in dates if begin<=d<=end]
    baseline=[left[begin],right[begin]]; rows=[]; values=[left,right]
    for day in window:
        vals=[v.get(day) if valid(v.get(day)) else None for v in values]
        rows.append({'date':day,'values':vals,'percent':[(v/base-1)*100 if v is not None else None for v,base in zip(vals,baseline)]})
    stats=[]
    for i in range(2):
        observed=[(r['date'],r['values'][i],r['percent'][i]) for r in rows if r['values'][i] is not None]
        peak=observed[0][1];drawdown=0.0
        for _,v,_ in observed:
            peak=max(peak,v);drawdown=min(drawdown,(v/peak-1)*100)
        stats.append({'name':labels[i],'start':baseline[i],'latest':values[i][end],
            'change':values[i][end]-baseline[i],'pct':(values[i][end]/baseline[i]-1)*100,
            'high_pct':max(x[2] for x in observed),'low_pct':min(x[2] for x in observed),
            'max_drawdown_pct':drawdown,'observations':len(observed)})
    return {'status':'OK','labels':labels,'start':begin,'end':end,'rows':rows,'stats':stats,
            'difference_pp':stats[0]['pct']-stats[1]['pct']}

class PerformanceComparison:
    def __init__(self,db_path=None):self.db_path=db_path
    @persisted_result
    def report(self,start,end,first,second,stock):
        try:
            for v in (start,end):
                if len(v)!=10 or date.fromisoformat(v).isoformat()!=v:raise ValueError()
            if start>end:raise ValueError()
        except (ValueError,TypeError):raise ValueError('Choose valid start and end dates in order.')
        symbols=[x.strip().upper() for x in (first,second,stock)]
        if any(not x or len(x)>24 for x in symbols):raise ValueError('Choose valid symbols.')
        with get_connection(self.db_path) as c:
            # One indexed read for selected symbols and one for the single imported index.
            rs=c.execute('SELECT trade_date,symbol,close FROM equity_ohlcv WHERE symbol IN (?,?,?) AND trade_date>=? AND trade_date<=? ORDER BY trade_date',(*symbols,start,end))
            maps={s:{} for s in symbols}
            for r in rs:maps[r['symbol']][r['trade_date']]=r['close']
            idx={r['trade_date']:r['close'] for r in c.execute('SELECT trade_date,close FROM index_ohlcv WHERE trade_date>=? AND trade_date<=? ORDER BY trade_date',(start,end))}
            days={r[0] for r in c.execute('SELECT DISTINCT trade_date FROM equity_ohlcv WHERE trade_date>=? AND trade_date<=?',(start,end))};days.update(idx)
        dates=sorted(days)
        return {'start_requested':start,'end_requested':end,'stock_pair':compare(dates,maps[symbols[0]],maps[symbols[1]],symbols[:2]),
                'index_pair':compare(dates,maps[symbols[2]],idx,[symbols[2],'Imported index'])}
