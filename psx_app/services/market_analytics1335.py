"""Read-only historical market analytics. No implied exchange calendar or prices."""
import math
from psx_app.database.schema import get_connection
from psx_app.services.result_cache import persisted_result

def finite(v):
    return v if isinstance(v,(int,float)) and math.isfinite(v) else None

def movement(value,base):
    v,b=finite(value),finite(base)
    if v is None or b is None or b<=0:return {'change':None,'pct':None}
    change=v-b;pct=(v/b-1)*100
    return {'change':change if math.isfinite(change) else None,'pct':pct if math.isfinite(pct) else None}

def refs(c):
    names=[r[0] for r in c.execute('SELECT DISTINCT list_name FROM company_reference ORDER BY list_name')]
    norm=lambda s:''.join(ch for ch in s.lower() if ch.isalnum())
    choices=[n for n in names if norm(n)=='complist'] or [n for n in names if norm(n)=='kse100']
    return min(choices,key=lambda n:(n not in ('COMP_LIST','KSE100'),n)) if choices else None

def company(c,symbol):
    rows=[dict(r) for r in c.execute('SELECT list_name,company,sector FROM company_reference WHERE symbol=? ORDER BY list_name',(symbol,))]
    def rank(x):
        n=''.join(ch for ch in x['list_name'].lower() if ch.isalnum())
        return (0 if 'sectorwise' in n else 1 if n=='complist' else 2,x['list_name'])
    r=min(rows,key=rank) if rows else {}
    return {'name':r.get('company') or None,'sector':r.get('sector') or None}

def year_ok(year):
    year=int(year)
    if not 1901<=year<=9998:raise ValueError('Invalid year')
    return year

def monthly_cells(rows,year):
    by={}
    for r in rows:
        if finite(r['close']) is not None and r['close']>0:by[r['trade_date'][:7]]=r
    cells={}
    for m in range(1,13):
        key=f'{year:04d}-{m:02d}';prev=f'{year-1:04d}-12' if m==1 else f'{year:04d}-{m-1:02d}';end=by.get(key);base=by.get(prev)
        if end:cells[m]={'date':end['trade_date'],'close':end['close'],'baseline_date':base['trade_date'] if base else None,**movement(end['close'],base['close'] if base else None)}
    return cells

class MarketAnalytics1335:
    def __init__(self,db_path=None):self.db_path=db_path
    @persisted_result
    def metadata(self):
        with get_connection(self.db_path) as c:
            syms=[r[0] for r in c.execute('SELECT DISTINCT symbol FROM equity_ohlcv ORDER BY symbol')]
            years=[r[0] for r in c.execute('SELECT DISTINCT SUBSTR(trade_date,1,4) FROM equity_ohlcv ORDER BY 1 DESC')]
            iyears=[r[0] for r in c.execute('SELECT DISTINCT SUBSTR(trade_date,1,4) FROM index_ohlcv ORDER BY 1 DESC')]
            source=refs(c);sectors=[r[0] for r in c.execute('SELECT DISTINCT sector FROM company_reference WHERE list_name=? AND sector<>? ORDER BY sector',(source,''))] if source else []
        return {'symbols':syms,'years':years,'index_years':iyears,'sectors':sectors,'sector_source':source,'indices':['Imported index'] if iyears else []}
    @persisted_result
    def symbol_chart(self,symbol,sessions=14):
        symbol=symbol.strip().upper();sessions=max(1,min(6000,int(sessions)))
        with get_connection(self.db_path) as c:
            rows=[dict(r) for r in c.execute('SELECT trade_date,close,volume FROM equity_ohlcv WHERE symbol=? ORDER BY trade_date DESC LIMIT ?',(symbol,sessions+1))]
            info=company(c,symbol)
            if not rows:return {'status':'NO_DATA','symbol':symbol,'company':info,'rows':[]}
            chosen=list(reversed(rows[:sessions]));prev=rows[sessions] if len(rows)>sessions else None
            first,last=chosen[0]['trade_date'],chosen[-1]['trade_date']
            idx={r['trade_date']:r['close'] for r in c.execute('SELECT trade_date,close FROM index_ohlcv WHERE trade_date>=? AND trade_date<=?',(first,last))}
        previous=prev['close'] if prev else None
        for r in chosen:
            r['close']=finite(r['close']);r['volume']=finite(r['volume']);r.update(movement(r['close'],previous));previous=r['close']
        stock={'start':chosen[0]['close'],'end':chosen[-1]['close'],**movement(chosen[-1]['close'],chosen[0]['close'])}
        i={'start':finite(idx.get(first)),'end':finite(idx.get(last)),**movement(idx.get(last),idx.get(first))}
        return {'status':'OK','symbol':symbol,'company':info,'first':first,'last':last,'requested':sessions,'rows':chosen,'stock':stock,'index':i}
    @persisted_result
    def high_low(self,symbol):
        symbol=symbol.strip().upper()
        with get_connection(self.db_path) as c:
            info=company(c,symbol)
            rows=[dict(r) for r in c.execute('SELECT trade_date,high,low FROM equity_ohlcv WHERE symbol=? ORDER BY trade_date',(symbol,))]
        groups={}
        for r in rows:
            key=r['trade_date'][:7];g=groups.setdefault(key,{'month':key,'high':None,'low':None})
            hi,lo=finite(r['high']),finite(r['low'])
            if hi is not None and hi>=0:g['high']=hi if g['high'] is None else max(g['high'],hi)
            if lo is not None and lo>=0:g['low']=lo if g['low'] is None else min(g['low'],lo)
        months=list(groups.values());years={}
        for m in months:
            y=m['month'][:4];v=years.setdefault(y,{'year':y,'high':None,'low':None})
            if m['high'] is not None:v['high']=m['high'] if v['high'] is None else max(v['high'],m['high'])
            if m['low'] is not None:v['low']=m['low'] if v['low'] is None else min(v['low'],m['low'])
        return {'symbol':symbol,'company':info,'first':rows[0]['trade_date'] if rows else None,'last':rows[-1]['trade_date'] if rows else None,'years':list(years.values()),'months':months}
    @persisted_result
    def sector_monthly(self,sector,year):
        year=year_ok(year)
        with get_connection(self.db_path) as c:
            source=refs(c)
            if not source:return {'status':'NO_REFERENCE','rows':[],'months':[]}
            members=[dict(r) for r in c.execute('SELECT symbol,company FROM company_reference WHERE list_name=? AND sector=? ORDER BY symbol',(source,sector))]
            rows=[dict(r) for r in c.execute('''SELECT symbol,trade_date,close FROM (SELECT e.symbol,e.trade_date,e.close,ROW_NUMBER() OVER(PARTITION BY e.symbol,SUBSTR(e.trade_date,1,7) ORDER BY e.trade_date DESC) AS rn FROM equity_ohlcv e JOIN company_reference cr ON e.symbol=cr.symbol AND cr.list_name=? AND cr.sector=? WHERE e.trade_date>=? AND e.trade_date<?) x WHERE rn=1 ORDER BY symbol,trade_date''',(source,sector,f'{year-1:04d}-12-01',f'{year+1:04d}-01-01'))]
        by={}
        for r in rows:by.setdefault(r['symbol'],[]).append(r)
        for m in members:m['months']=monthly_cells(by.get(m['symbol'],[]),year)
        months=sorted({int(k) for r in members for k in r['months']})
        return {'status':'OK','year':year,'sector':sector,'source':source,'months':months,'rows':members}
    @persisted_result
    def index_monthly(self,year):
        year=year_ok(year)
        with get_connection(self.db_path) as c:
            rows=[dict(r) for r in c.execute('''SELECT trade_date,close FROM (SELECT trade_date,close,ROW_NUMBER() OVER(PARTITION BY SUBSTR(trade_date,1,7) ORDER BY trade_date DESC) AS rn FROM index_ohlcv WHERE trade_date>=? AND trade_date<?) x WHERE rn=1 ORDER BY trade_date''',(f'{year-1:04d}-01-01',f'{year+1:04d}-01-01'))]
        prior=[x for x in rows if x['trade_date'][:4]==str(year-1) and finite(x['close']) is not None and x['close']>0]
        current=[x for x in rows if x['trade_date'][:4]==str(year) and finite(x['close']) is not None and x['close']>0]
        base=prior[-1] if prior else None;last=current[-1] if current else None
        cells=monthly_cells(rows,year)
        # The first recorded month of a year uses the final available close
        # in the preceding year, even when intervening months are absent.
        if cells and base:
            first=cells[min(cells)]
            first['baseline_date']=base['trade_date']
            first.update(movement(first['close'],base['close']))
        return {'year':year,'index':'Imported index','months':cells,'baseline':base,'latest':last,**movement(last['close'] if last else None,base['close'] if base else None)}
