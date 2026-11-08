"""Sector peer intelligence over imported cash records; no exchange calendar inferred."""
from datetime import date, timedelta
import calendar, math
from psx_app.database.schema import get_connection
from psx_app.services.market_analytics1335 import refs
from psx_app.services.result_cache import persisted_result

KINDS=('daily','weekly','monthly','quarterly','yearly')
def shift_month(d,n):
    y,m=divmod(d.year*12+d.month-1+n,12);return date(y,m+1,1)
def bounds(d,kind):
    if kind=='weekly':
        start=d-timedelta(days=d.weekday());return start,start+timedelta(days=4)
    if kind=='monthly':start=date(d.year,d.month,1);return start,shift_month(start,1)-timedelta(days=1)
    if kind=='quarterly':start=date(d.year,((d.month-1)//3)*3+1,1);return start,shift_month(start,3)-timedelta(days=1)
    if kind=='yearly':return date(d.year,1,1),date(d.year,12,31)
    return d,d

def valid(v,positive=False):return isinstance(v,(float,int)) and math.isfinite(v) and (v>0 if positive else v>=0)
def ratio(v,b,allow_zero=False):
    if not valid(v,not allow_zero) or not valid(b,True):return None
    n=(v/b-1)*100
    return n if math.isfinite(n) else None
def change(v,b):return ratio(v,b)
def volume_change(v,b):return ratio(v,b,True)
def last_weekday(d):
    while d.weekday()>4:d-=timedelta(days=1)
    return d

def percentile(v,vals):
    if len(vals)==1:return 50.0
    return 100*(sum(x<v for x in vals)+0.5*(sum(x==v for x in vals)-1))/(len(vals)-1)

def rate(s):
    if s>=90:return 'Excellent'
    if s>=80:return 'Very Strong'
    if s>=70:return 'Strong'
    if s>=60:return 'Positive'
    if s>=40:return 'Neutral'
    if s>=20:return 'Weak'
    return 'Very Weak'

def score(rows,period,prior):
    eligible=[]
    for row in rows:
        p,q=row[period],row[prior]
        p['volume_pct']=volume_change(p['volume'],q['volume']) if p['complete'] and q['complete'] else None
        if p['complete'] and q['complete'] and p['return_pct'] is not None and p['volume_pct'] is not None and p['consistency'] is not None:
            eligible.append(row)
    returns=[x[period]['return_pct'] for x in rows if x[period]['return_pct'] is not None]
    mean=sum(returns)/len(returns) if returns else None
    volumes=[x[period]['volume'] for x in eligible];momenta=[x[period]['volume_pct'] for x in eligible];relative=[x[period]['return_pct']-mean for x in eligible]
    for row in rows:
        p=row[period];p.update(score=None,rating='Insufficient data',rank=None,components=None,relative_pct=(p['return_pct']-mean if p['return_pct'] is not None and mean is not None else None))
    for row in eligible:
        p=row[period];rel=p['return_pct']-mean;p['relative_pct']=rel
        # Fixed return scale, sector percentiles and direction consistency are distinct factors.
        comp={'price':max(0,min(100,50+2.5*p['return_pct'])), 'activity':percentile(p['volume'],volumes), 'volume_momentum':percentile(p['volume_pct'],momenta), 'relative':percentile(rel,relative), 'consistency':p['consistency']*100}
        s=sum(comp[k]*w for k,w in [('price',.35),('activity',.20),('volume_momentum',.20),('relative',.15),('consistency',.10)])
        if p['return_pct']<0:s=min(s,79.0)
        p.update(score=round(s,2),rating=rate(round(s,2)),components={k:round(v,2) for k,v in comp.items()})
    # Competition ranks preserve ties; previous ranks use the same rules independently.
    for row in eligible:row[period]['rank']=1+sum(other[period]['score']>row[period]['score'] for other in eligible)
    return mean,len(eligible)

class SectorIntelligence1336:
    def __init__(self,db_path=None):self.db_path=db_path
    @persisted_result
    def report(self,sector,kind='daily',year=None):
        if kind not in KINDS:raise ValueError('Invalid timeframe')
        sector=sector.strip()
        if not sector or len(sector)>150:raise ValueError('Invalid sector')
        if year is not None and not 1904<=int(year)<=9996:raise ValueError('Invalid year')
        with get_connection(self.db_path) as c:
            source=refs(c)
            if not source:return {'status':'NO_REFERENCE','rows':[]}
            members=[dict(r) for r in c.execute('SELECT symbol,company FROM company_reference WHERE list_name=? AND sector=? ORDER BY symbol',(source,sector))]
            if not members:raise ValueError('Sector not found in imported reference')
            latest=c.execute('SELECT MAX(trade_date) FROM equity_ohlcv WHERE trade_date>=? AND trade_date<?',(f'{int(year):04}-01-01',f'{int(year)+1:04}-01-01')).fetchone()[0] if kind=='yearly' and year else c.execute('SELECT MAX(trade_date) FROM equity_ohlcv').fetchone()[0]
            if not latest:return {'status':'NO_DATA','sector':sector,'rows':[]}
            d=date.fromisoformat(latest)
            if kind=='daily':
                dates=[r[0] for r in c.execute('SELECT DISTINCT trade_date FROM equity_ohlcv WHERE trade_date<=? ORDER BY trade_date DESC LIMIT 4',(latest,))][::-1]
                current_dates=dates[-1:];prev_dates=dates[-2:-1];older_dates=dates[-3:-2]; earliest=dates[0]
                periods=[(x[0],x[0]) if x else (None,None) for x in (current_dates,prev_dates,older_dates)]
                date_lists=[current_dates,prev_dates,older_dates]
            else:
                windows=[];anchor=d
                for _ in range(3):
                    start,end=bounds(anchor,kind);windows.append((start,end));anchor=start-timedelta(days=1)
                earliest=windows[-1][0].isoformat()
                dates=[r[0] for r in c.execute('SELECT DISTINCT trade_date FROM equity_ohlcv WHERE trade_date>=? AND trade_date<=? ORDER BY trade_date',(earliest,latest))]
                if kind=='weekly':dates=[x for x in dates if date.fromisoformat(x).weekday()<5]
                periods=[(a.isoformat(),b.isoformat()) for a,b in windows]
                date_lists=[[x for x in dates if a<=x<=b] for a,b in periods]
                if kind=='weekly':
                    if not date_lists[0]:return {'status':'NO_DATA','sector':sector,'rows':[]}
                    latest=date_lists[0][-1]
            # Indexed baseline seeks plus one bounded sector-range scan, not one network request per symbol.
            from psx_app.database.turso import backend_name
            weekday=(' AND EXTRACT(ISODOW FROM CAST(b.trade_date AS DATE)) < 6' if backend_name()=='postgres' else " AND CAST(strftime('%w',b.trade_date) AS INTEGER) BETWEEN 1 AND 5") if kind=='weekly' else ''
            before=[dict(r) for r in c.execute('''SELECT cr.symbol,e.trade_date,e.close,e.volume FROM company_reference cr JOIN equity_ohlcv e ON e.symbol=cr.symbol AND e.trade_date=(SELECT MAX(b.trade_date) FROM equity_ohlcv b WHERE b.symbol=cr.symbol AND b.trade_date<?'''+weekday+''') WHERE cr.list_name=? AND cr.sector=?''',(earliest,source,sector))]
            records=[dict(r) for r in c.execute('''SELECT e.symbol,e.trade_date,e.close,e.volume FROM equity_ohlcv e JOIN company_reference cr ON cr.symbol=e.symbol AND cr.list_name=? AND cr.sector=? WHERE e.trade_date>=? AND e.trade_date<=? ORDER BY e.symbol,e.trade_date''',(source,sector,earliest,latest))]
        by={m['symbol']:[] for m in members}
        for r in before+records:
            if kind=='weekly' and date.fromisoformat(r['trade_date']).weekday()>=5:continue
            by[r['symbol']].append(r)
        def metrics(records,days):
            if not days:return dict(start=None,baseline_date=None,end=None,end_date=None,change=None,return_pct=None,volume=None,sessions=0,complete=False,consistency=None)
            day_set=set(days)
            rows=[r for r in records if r['trade_date'] in day_set];prior=[r for r in records if r['trade_date']<days[0] and valid(r['close'],True)];base=prior[-1] if prior else None
            # Do not substitute stale last quotes for the market's period endpoint.
            last=next((r for r in reversed(rows) if r['trade_date']==days[-1] and valid(r['close'],True)),None)
            p=change(last['close'] if last else None,base['close'] if base else None)
            complete=bool(base and last and len(rows)==len(days) and all(valid(r['close'],True) and valid(r['volume']) for r in rows))
            n=0;direction=0;previous=base['close'] if base else None
            for r in rows:
                v=change(r['close'],previous)
                if v is not None:n+=1;direction+=1 if v>0 else .5 if v==0 else 0
                previous=r['close'] if valid(r['close'],True) else None
            volume=sum(r['volume'] for r in rows if valid(r['volume'])) if rows else None
            return dict(start=base['close'] if base else None,baseline_date=base['trade_date'] if base else None,end=last['close'] if last else None,end_date=last['trade_date'] if last else None,change=(last['close']-base['close'] if p is not None else None),return_pct=p,volume=volume,sessions=sum(1 for r in rows if valid(r['volume']) and r['volume']>0),observed=len(rows),expected=len(days),complete=complete,consistency=direction/n if n and complete else None)
        output=[]
        for m in members:
            rs=sorted(by[m['symbol']],key=lambda r:r['trade_date']); a,b,z=(metrics(rs,ds) for ds in date_lists)
            eq=metrics(rs,date_lists[1][:len(date_lists[0])]) if date_lists[0] and len(date_lists[1])>=len(date_lists[0]) else None
            output.append({**m,'current':a,'previous':b,'older':z,'equivalent':eq,'value':None})
        prev_mean,prev_count=score(output,'previous','older');mean,count=score(output,'current','previous')
        for r in output:
            a,b,e=r['current'],r['previous'],r['equivalent'];r['performance_difference']=a['return_pct']-b['return_pct'] if a['return_pct'] is not None and b['return_pct'] is not None else None
            r['rank_movement']=b['rank']-a['rank'] if a['rank'] is not None and b['rank'] is not None else None
            r['equivalent_volume_pct']=volume_change(a['volume'],e['volume']) if e and a['complete'] and e['complete'] else None
            r['equivalent_return_difference']=a['return_pct']-e['return_pct'] if e and a['return_pct'] is not None and e['return_pct'] is not None and a['complete'] and e['complete'] else None
        active=[r for r in output if r['current']['sessions']>0]; returns=[r for r in output if r['current']['return_pct'] is not None]
        pick=lambda seq,k,reverse=True:sorted(seq,key=lambda r:((-k(r) if reverse else k(r)),r['symbol']))[0]['symbol'] if seq else None
        overview={'listed':len(output),'active':len(active),'advancing':sum(r['current']['return_pct']>0 for r in returns),'declining':sum(r['current']['return_pct']<0 for r in returns),'unchanged':sum(r['current']['return_pct']==0 for r in returns),'return_unknown':len(output)-len(returns),'volume':sum(r['current']['volume'] or 0 for r in output) if any(r['current']['volume'] is not None for r in output) else None,'volume_complete':all(r['current']['complete'] for r in output),'value':None,'best':pick(returns,lambda r:r['current']['return_pct']),'worst':pick(returns,lambda r:r['current']['return_pct'],False),'most_active':pick(active,lambda r:r['current']['volume'] or 0)}
        incomplete=kind!='daily' and date.fromisoformat(latest)<last_weekday(date.fromisoformat(periods[0][1]))
        return {'status':'OK','sector':sector,'source':source,'kind':kind,'as_of':latest,'periods':[{'start':a,'end':b,'dates':ds} for (a,b),ds in zip(periods,date_lists)],'partial':incomplete,'peer_mean':mean,'scored':count,'previous_scored':prev_count,'overview':overview,'rows':output}
