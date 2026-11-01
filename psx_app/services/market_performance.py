"""Read-only, batched market performance. Imported membership, no sample fallback."""
from collections import defaultdict
from datetime import date, timedelta
import calendar
import math
import re
from psx_app.database.schema import get_connection
from psx_app.services.result_cache import persisted_result

KINDS = ('daily','weekly','monthly','quarterly','halfyear','ninemonth','yearly')


def period_for(day, kind):
    d = date.fromisoformat(day) if isinstance(day,str) else day
    fy = d.year + (d.month >= 7)
    fm = (d.month - 7) % 12
    if kind == 'daily': return d.isoformat(), d, d, d.strftime('%-d %b %Y')
    if kind == 'weekly':
        if d.weekday() > 4: return None
        y,w,_ = d.isocalendar(); start = d-timedelta(days=d.weekday())
        return f'{y}-W{w:02}', start, start+timedelta(days=4), f'{y} · Week {w:02}'
    if kind == 'monthly': y,m=d.year,d.month; key=f'{y}-{m:02}'; months=1; label=d.strftime('%B %Y')
    else:
        label=f'FY {fy-1}–{str(fy)[2:]}'
        if kind == 'quarterly':
            n=fm//3; offset=n*3; months=3; key=f'FY{fy}-Q{n+1}'; label+=f' · Q{n+1}'
        elif kind == 'halfyear':
            n=fm//6; offset=n*6; months=6; key=f'FY{fy}-H{n+1}'; label+=f' · H{n+1}'
        elif kind == 'ninemonth':
            if fm >= 9: return None
            offset=0; months=9; key=f'FY{fy}-9M'; label+=' · Nine months'
        elif kind == 'yearly': offset=0; months=12; key=f'FY{fy}'
        else: raise ValueError('Unknown period')
        absolute=(fy-1)*12+6+offset; y,m=divmod(absolute,12);m+=1
    start=date(y,m,1); absolute=y*12+m-1+months; ey,em=divmod(absolute,12)
    end=date(ey,em+1,1)-timedelta(days=1)
    return key,start,end,label


def change(last, base):
    if not _finite(last) or not _finite(base) or base <= 0 or last <= 0: return None,None
    delta=last-base
    pct=delta/base*100
    return (delta,pct) if _finite(delta) and _finite(pct) else (None,None)


def _finite(v):
    return v is not None and math.isfinite(float(v))


class MarketPerformance:
    def __init__(self,db_path=None): self.db_path=db_path

    @persisted_result
    def report(self,kind='daily',key=None):
        if kind not in KINDS: raise ValueError('Unknown market performance period')
        if key is not None and (len(key)>32 or not re.fullmatch(r'[A-Za-z0-9-]+',key)):
            raise ValueError('Invalid period selection')
        with get_connection(self.db_path) as c:
            dates=[r[0] for r in c.execute('SELECT trade_date FROM equity_ohlcv UNION SELECT trade_date FROM index_ohlcv ORDER BY trade_date')]
            options={}
            for day in dates:
                p=period_for(day,kind)
                if p: options[p[0]]=p
            ordered=sorted(options.values(),key=lambda p:p[1],reverse=True)
            if not ordered:
                return {'status':'NO_DATA','kind':kind,'options':[],'charts':[],'combo':None,'selected':None}
            requested=key
            if kind=='daily' and key:
                try: date.fromisoformat(key)
                except ValueError: raise ValueError('Use a valid ISO date')
                eligible=[p for p in ordered if p[0]<=key]
                if not eligible: raise ValueError('No imported data on or before this date')
                selected=eligible[0]
            elif key:
                if key not in options: raise ValueError('No imported data for this period')
                selected=options[key]
            else: selected=ordered[0]
            key,start,end,label=selected; lo,hi=start.isoformat(),end.isoformat()
            # Weekday filtering also applies to the baseline: imported weekend rows
            # never become Monday–Friday weekly observations. Both backends tested.
            from psx_app.database.turso import backend_name
            weekday="EXTRACT(ISODOW FROM CAST(trade_date AS DATE)) < 6" if backend_name()=='postgres' else "CAST(strftime('%w',trade_date) AS INTEGER) BETWEEN 1 AND 5"
            day_filter=' AND '+weekday if kind=='weekly' else ''
            refs=[dict(r) for r in c.execute('SELECT list_name,symbol,company,sector FROM company_reference ORDER BY list_name,symbol')]
            def normalize(s): return re.sub('[^a-z0-9]','',s.lower())
            def list_name(target):
                candidates=sorted({r['list_name'] for r in refs if normalize(r['list_name'])==target})
                return next((s for s in candidates if s=={'complist':'COMP_LIST','kse100':'KSE100'}[target]),candidates[0] if candidates else None)
            comp_name,kse_name=list_name('complist'),list_name('kse100')
            comp={r['symbol'].upper():r for r in refs if r['list_name']==comp_name}
            members={r['symbol'].upper():r for r in refs if r['list_name']==kse_name}
            def sector(sym): return (comp.get(sym,{}).get('sector') or members.get(sym,{}).get('sector') or '').strip() or 'Unmapped'
            # One aggregate scan and indexed seeks, not a request/query per symbol.
            rows=[dict(r) for r in c.execute(f'''
                WITH a AS (SELECT symbol,MAX(trade_date) AS last_date,MIN(trade_date) AS first_date,
                  SUM(volume) AS volume,COUNT(*) AS sessions FROM equity_ohlcv
                  WHERE trade_date>=? AND trade_date<=? {day_filter} GROUP BY symbol)
                SELECT a.*,e.close,
                  (SELECT b.close FROM equity_ohlcv b WHERE b.symbol=a.symbol AND b.trade_date<? {day_filter} ORDER BY b.trade_date DESC LIMIT 1) AS baseline,
                  (SELECT b.trade_date FROM equity_ohlcv b WHERE b.symbol=a.symbol AND b.trade_date<? {day_filter} ORDER BY b.trade_date DESC LIMIT 1) AS baseline_date
                FROM a LEFT JOIN equity_ohlcv e ON e.symbol=a.symbol AND e.trade_date=a.last_date
                ORDER BY a.symbol''',(lo,hi,lo,lo))]
            index_rows=[dict(r) for r in c.execute(f'SELECT trade_date,close FROM index_ohlcv WHERE trade_date<=? {day_filter} AND (trade_date>=? OR trade_date=(SELECT MAX(trade_date) FROM index_ohlcv WHERE trade_date<? {day_filter})) ORDER BY trade_date',(hi,lo,lo))]
            # The bounded daily sector aggregate is reduced to chart buckets before JSON.
            daily=[]
            if kind!='daily':
                daily=[dict(r) for r in c.execute(f'''SELECT e.trade_date,
                  COALESCE(NULLIF(TRIM(cr.sector),''),NULLIF(TRIM(kr.sector),''),'Unmapped') AS sector,
                  SUM(e.volume) AS volume FROM equity_ohlcv e
                  LEFT JOIN company_reference cr ON cr.symbol=e.symbol AND cr.list_name=?
                  LEFT JOIN company_reference kr ON kr.symbol=e.symbol AND kr.list_name=?
                  WHERE e.trade_date>=? AND e.trade_date<=? {day_filter}
                  GROUP BY e.trade_date,COALESCE(NULLIF(TRIM(cr.sector),''),NULLIF(TRIM(kr.sector),''),'Unmapped')
                  ORDER BY e.trade_date''',(comp_name or '',kse_name or '',lo,hi))]
        cash_as_of=max((r['last_date'] for r in rows),default=None)
        cash_first=min((r['first_date'] for r in rows),default=None)
        period_index=[r for r in index_rows if r['trade_date']>=lo]
        index_latest=period_index[-1] if period_index else None
        index_base=next((r for r in index_rows if r['trade_date']<lo),None)
        delta,pct=change(index_latest['close'] if index_latest else None,index_base['close'] if index_base else None)
        volumes=defaultdict(int); returns=[]; invalid=[]; stale=[]
        for r in rows:
            r['sector']=sector(r['symbol']);volumes[r['sector']]+=r['volume'] or 0
            if r['symbol'] not in members: continue
            if r['last_date']!=cash_as_of: stale.append(r['symbol']);continue
            if not _finite(r['close']) or not _finite(r['baseline']): invalid.append(r['symbol']);continue
            diff,ret=change(r['close'],r['baseline'])
            if ret is None: invalid.append(r['symbol']);continue
            returns.append({'name':r['symbol'],'value':ret,'difference':diff,'sector':r['sector'],
                            'close':r['close'],'baseline':r['baseline'],'baseline_date':r['baseline_date'],'date':r['last_date']})
        sector_returns=defaultdict(list); sector_members=defaultdict(int)
        for sym in members: sector_members[sector(sym)]+=1
        for r in returns: sector_returns[r['sector']].append(r['value'])
        sr=[{'name':s,'value':sum(values)/len(values),'eligible':len(values),'members':sector_members[s]} for s,values in sector_returns.items()]
        charts=[]
        def chart(id,title,items,unit,tone='volume',field='value',positive=None):
            values=[{**r,'value':r[field]} for r in items if _finite(r[field]) and (positive is None and r[field]>0 or positive is True and r[field]>0 or positive is False and r[field]<0)]
            values.sort(key=lambda r:((-r['value']) if positive is not False else r['value'],r['name']))
            charts.append({'id':id,'title':title,'unit':unit,'tone':tone,'rows':values[:10],
              'unavailable':not bool(members) if id not in ('scrip_volume','sector_volume') else False})
        chart('scrip_volume','Top scrip-wise volume leaders',[{'name':r['symbol'],'value':r['volume']} for r in rows],'shares')
        chart('sector_volume','Top sector-wise volume leaders',[{'name':s,'value':v} for s,v in volumes.items()],'shares')
        chart('sector_gainers','Sector-wise major gainers · KSE100',sr,'%', 'pos',positive=True)
        chart('sector_losers','Sector-wise major losers · KSE100',sr,'%', 'neg',positive=False)
        for field,unit,word in [('difference','PKR','PKR'),('value','%','percentage')]:
            for up in (True,False):chart(f'scrip_{word}_{"gainers" if up else "losers"}',f'Scrip-wise major {"gainers" if up else "losers"} · {word} · KSE100',returns,unit,'pos' if up else 'neg',field,up)
        expected=end
        while expected.weekday()>4: expected-=timedelta(days=1)
        warnings=[]
        trailing=cash_as_of is None or cash_as_of<expected.isoformat() or index_latest is None or index_latest['trade_date']<expected.isoformat()
        if trailing: warnings.append('Partial / incomplete period: imported cash or index data does not reach the final weekday.')
        if not members: warnings.append('Import the KSE100 membership sheet to populate KSE100 return charts. No fallback membership is used.')
        if delta is None: warnings.append('Index change is unavailable: a positive period-end close and pre-period baseline are required.')
        if stale: warnings.append(f'{len(stale)} KSE100 symbols excluded from returns because their quotes are older than the period cash date.')
        if invalid: warnings.append(f'{len(invalid)} KSE100 symbols excluded from returns because valid prices or pre-period baselines are missing.')
        if volumes.get('Unmapped',0): warnings.append('Unmapped volume is retained separately; import COMP_LIST for full sector coverage.')
        no_quotes=sorted(set(members)-{r['symbol'] for r in rows})
        if no_quotes: warnings.append(f'{len(no_quotes)} imported KSE100 members have no cash records in this period.')
        if not cash_first or cash_first>lo: warnings.append('Coverage begins at the first stored session shown; non-trading days and missing imports cannot be distinguished.')
        return {'status':'OK','kind':kind,'selected':key,'requested':requested,'label':label,'start':lo,'end':hi,
          'options':[{'key':p[0],'label':p[3],'start':p[1].isoformat(),'end':p[2].isoformat()} for p in ordered],
          'cash_as_of':cash_as_of,'cash_first':cash_first,'index':{'close':index_latest['close'] if index_latest and _finite(index_latest['close']) else None,
          'date':index_latest['trade_date'] if index_latest else None,'baseline_date':index_base['trade_date'] if index_base else None,
          'baseline':index_base['close'] if index_base and _finite(index_base['close']) else None,'change':delta,'pct':pct},
          'partial':trailing,'warnings':warnings,'charts':charts,'combo':self._combo(kind,start,end,daily,index_rows,volumes) if kind!='daily' else None,
          'coverage':{'symbols':len(rows),'volume':sum(volumes.values()),'members':len(members),'eligible':len(returns),
          'stale':len(stale),'invalid_baseline_or_price':len(invalid),'missing':len(no_quotes),'membership_source':kse_name,
          'observed_dates':len({d for d in dates if lo<=d<=hi and (kind!='weekly' or date.fromisoformat(d).weekday()<5)})},
          'method':'Price returns against the last stored close before the period starts. Sector returns are equal-weight member averages, not index-point contributions. Imported KSE100 membership is static; historical reconstitutions, dividends and corporate-action adjustments are not modeled. Volume is imported cash-market shares, not official index volume. Missing imports cannot be identified as exchange holidays.'}

    @staticmethod
    def _combo(kind,start,end,daily,index_rows,totals):
        top=[s for s in sorted(totals,key=lambda s:(-totals[s],s)) if s!='Unmapped'][:5]
        sectors=top+(['Other'] if any(s not in top and s!='Unmapped' for s in totals) else [])+(['Unmapped'] if 'Unmapped' in totals else [])
        if kind=='weekly': anchors=[start+timedelta(days=n) for n in range(5)]
        elif kind=='monthly': anchors=sorted({date.fromisoformat(r['trade_date']) for r in daily+index_rows if start.isoformat()<=r['trade_date']<=end.isoformat()})
        else:
            anchors=[];d=start
            while d<=end:
                anchors.append(d);d=date(d.year+(d.month==12),d.month%12+1,1)
        buckets=[]
        for anchor in anchors:
            finish=anchor if kind in ('weekly','monthly') else date(anchor.year,anchor.month,calendar.monthrange(anchor.year,anchor.month)[1])
            a,b=anchor.isoformat(),finish.isoformat(); cash=[r for r in daily if a<=r['trade_date']<=b]
            stack={s:0 for s in sectors}
            for row in cash:
                s=row['sector'];group=s if s in top or s=='Unmapped' else 'Other';stack[group]+=row['volume'] or 0
            ir=[r for r in index_rows if a<=r['trade_date']<=b]; prior=[r for r in index_rows if r['trade_date']<a]
            latest=ir[-1] if ir else None;base=prior[-1] if prior else None
            delta,_=change(latest['close'] if latest else None,base['close'] if base else None)
            buckets.append({'date':a,'end':b,'volume':sum(stack.values()) if cash else None,'sectors':stack if cash else None,
                            'index_change':delta,'index_date':latest['trade_date'] if latest else None,
                            'baseline_date':base['trade_date'] if base else None})
        return {'sectors':sectors,'buckets':buckets,'volume_source':'Imported cash-market volume, stacked by sector','line':'Index change (points)'}
