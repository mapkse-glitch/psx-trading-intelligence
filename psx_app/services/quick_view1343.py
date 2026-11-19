"""Symbol quick view over imported cash records and estimated lock touches."""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import sys
import json
import math
from psx_app.database.schema import get_connection
from psx_app.services.market_explorer import delta
from psx_app.services.result_cache import persisted_result
from psx_app.services.sector_reference import BUNDLED
from psx_app.services.technical_service import TechnicalService, wilder_rsi_series

METRICS = [('max_high','high',True),('max_close','close',True),('min_low','low',False),('min_close','close',False),('max_average','avg_price',True),('min_average','avg_price',False),('max_volume','volume',True),('min_volume','volume',False)]

def _good(x, price=True):
    try:
        n=float(x)
        return math.isfinite(n) and (n>0 if price else n>=0)
    except (ValueError,TypeError,OverflowError):
        return False

def _estimated_touch_flags(row):
    """Use the checker's 10%-or-PKR-1 thresholds on intraday highs/lows.

    Imported pr_close is the checker reference; a missing value is not silently
    replaced with another date. Thresholds are rounded to paisa before comparison.
    Exchange-specific limits and historical exceptions are not in the database.
    """
    previous=row.get('pr_close')
    if not _good(previous):return (None,None)
    try:
        ref=Decimal(str(previous))
        upper=max(ref*Decimal('1.10'),ref+Decimal('1')).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        lower=min(ref*Decimal('.90'),ref-Decimal('1')).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        u,l=float(upper),float(lower)
        if not math.isfinite(u) or not math.isfinite(l):return (None,None)
    except (InvalidOperation,ValueError,TypeError,OverflowError):return (None,None)
    def touch(field,limit,above):
        value=row.get(field)
        if not _good(value):return None
        value=float(value)
        epsilon=sys.float_info.epsilon*max(1,abs(value),abs(u),abs(l))*8
        return value>=limit-epsilon if above else value<=limit+epsilon
    return touch('high',u,True),touch('low',l,False)


def _ref_rank(row):
    name=''.join(ch for ch in row['list_name'].lower() if ch.isalnum())
    return (0 if 'sectorwise' in name else 1 if name=='complist' else 2,row['list_name'])

def _refs(rows):
    result={}
    for r in rows:
        sym=r['symbol'].strip().upper()
        if sym and (sym not in result or ((not bool((r.get('company') or '').strip()),_ref_rank(r)) < (not bool((result[sym].get('company') or '').strip()),_ref_rank(result[sym])))): result[sym]=r
    return result

def _bundled():
    try:return {r['symbol'].upper():r for r in json.loads(BUNDLED.read_text()).get('COMP_LIST',[]) if r.get('symbol')}
    except (OSError,ValueError,TypeError):return {}

def _company(sym,refs,bundled):
    r=refs.get(sym) or bundled.get(sym) or {}
    return (r.get('company') or '').strip() or None

def _year_start(d):
    # Inclusive trailing year, including the anchor date.
    try:previous=d.replace(year=d.year-1)
    except ValueError:previous=d.replace(year=d.year-1,day=28)
    return previous+timedelta(days=1)

def _windows(anchor):
    return [(f'{n} Days',(anchor-timedelta(days=n-1)).isoformat()) for n in (7,14,30,90,180)]+[
        ('1 Year',_year_start(anchor).isoformat()),('All-Time High Since 1 October 2023','2023-10-01'),('All-Time High Since 27 February 2026','2026-02-27')]

def _summarize_ranges(bars,anchor):
    """Accumulate reverse-chronological ranges once; ties keep latest dates."""
    windows=_windows(anchor)
    results=[None]*len(windows)
    metrics={name:{'value':None,'date':None} for name,_,_ in METRICS}
    counts=[0,0];checked=[0,0];total=0;idx=len(bars)-1
    for original,(label,start) in sorted(enumerate(windows),key=lambda x:x[1][1],reverse=True):
        while idx>=0 and bars[idx]['trade_date']>=start:
            row=bars[idx];idx-=1;total+=1
            for name,key,maximum in METRICS:
                value=row.get(key)
                if not _good(value,key!='volume'):continue
                old=metrics[name]['value']
                if old is None or (value>old if maximum else value<old):
                    metrics[name]={'value':value,'date':row['trade_date']}
            for side,flag in enumerate(_estimated_touch_flags(row)):
                if flag is not None:
                    checked[side]+=1
                    if flag:counts[side]+=1
        coverage=[{'count':counts[i] if checked[i] else None,'checked':checked[i],'total':total} for i in (0,1)]
        results[original]={'label':label,'start':start,'end':anchor.isoformat(),'metrics':{k:v.copy() for k,v in metrics.items()},
                           'upper_lock_count':coverage[0]['count'],'lower_lock_count':coverage[1]['count'],
                           'upper_lock_coverage':coverage[0],'lower_lock_coverage':coverage[1]}
    return results

def _breakouts(bars):
    """Latest session versus preceding imported sessions; no partial extrema."""
    names=[(f'{n} Sessions',n) for n in (7,14,30,90,180)]+[('1 Year',None)]
    if not bars:return [{'range':name,'high':None,'low':None} for name,_ in names]
    last=bars[-1]; prior=bars[:-1]; anchor=date.fromisoformat(last['trade_date'])
    output=[]
    for name,n in names:
        if n is None:
            start=_year_start(anchor).isoformat()
            complete=bool(prior) and prior[0]['trade_date']<=start
            window=[(i,r) for i,r in enumerate(prior) if r['trade_date']>=start]
        else:
            complete=len(prior)>=n
            start_index=max(0,len(prior)-n)
            window=list(enumerate(prior[start_index:],start_index))
        sides={}
        for field,is_high in (('high',True),('low',False)):
            # An unknown observation can hide a more extreme price. Do not
            # assert either a breakout or a negative result for that side.
            def valid_side(row):
                if not _good(row.get(field)):return False
                # Reject a contradictory high/low pair instead of treating
                # a corrupted bar as a historical price record.
                if _good(row.get('high')) and _good(row.get('low')) and float(row['high'])<float(row['low']):return False
                return True
            if not complete or not window or not valid_side(last) or any(not valid_side(r) for _,r in window):
                sides[field]=None; continue
            if is_high:
                idx,record=max(window,key=lambda x:(float(x[1][field]),x[0]))
                hit=float(last[field])>float(record[field])
            else:
                idx,record=min(window,key=lambda x:(float(x[1][field]),-x[0]))
                hit=float(last[field])<float(record[field])
            sides[field]={'hit':hit,'previous':record[field],'previous_date':record['trade_date'],
                          'current':last[field],'current_date':last['trade_date'],'elapsed_sessions':len(bars)-1-idx}
        output.append({'range':name,**sides})
    return output

def _volume_comparison(bars):
    latest=bars[-1] if bars else None
    previous=bars[-2] if len(bars)>1 else None
    lv=latest.get('volume') if latest and _good(latest.get('volume'),False) else None
    pv=previous.get('volume') if previous and _good(previous.get('volume'),False) else None
    change=(float(lv)-float(pv))*100/float(pv) if lv is not None and pv is not None and float(pv)>0 else None
    return {'latest':lv,'latest_date':latest['trade_date'] if latest else None,
            'previous':pv,'previous_date':previous['trade_date'] if previous else None,'change_pct':change}

class QuickView:
    def __init__(self,db_path=None):self.db_path=db_path

    @persisted_result
    def metadata(self):
        with get_connection(self.db_path) as c:
            references=[dict(r) for r in c.execute('SELECT list_name,symbol,company,sector FROM company_reference')]
            symbols={r[0] for r in c.execute('SELECT DISTINCT symbol FROM equity_ohlcv')}
        priced=set(symbols);refs=_refs(references);symbols.update(refs);bundled=_bundled()
        return {'symbols':[{'symbol':s,'company':_company(s,refs,bundled),'has_history':s in priced} for s in sorted(symbols) if s]}

    @persisted_result
    def report(self,symbol):
        symbol=symbol.strip().upper()
        if not symbol or len(symbol)>24:raise ValueError('Invalid symbol')
        with get_connection(self.db_path) as c:
            bars=[dict(r) for r in c.execute('SELECT trade_date,open,high,low,close,pr_close,avg_price,volume FROM equity_ohlcv WHERE symbol=? ORDER BY trade_date',(symbol,))]
            refs=_refs([dict(r) for r in c.execute('SELECT list_name,symbol,company,sector FROM company_reference WHERE symbol=?',(symbol,))])
            market_date=c.execute('SELECT MAX(trade_date) FROM equity_ohlcv WHERE volume>0').fetchone()[0]
            top=[dict(r) for r in c.execute('SELECT symbol,volume FROM equity_ohlcv WHERE trade_date=? AND volume>0 ORDER BY volume DESC,symbol ASC LIMIT 10',(market_date or '',))]
            top5_rows=[dict(r) for r in c.execute('''SELECT trade_date,ticker,rank,rate,volume,trades FROM top5_volume_records WHERE ticker=? AND trade_date IN (SELECT DISTINCT trade_date FROM top5_volume_records WHERE ticker=? ORDER BY trade_date DESC LIMIT 4) ORDER BY trade_date DESC,rank ASC''',(symbol,symbol))]
            toprefs=_refs([dict(r) for r in c.execute('SELECT list_name,symbol,company,sector FROM company_reference WHERE symbol IN ('+','.join('?' for _ in top)+')',tuple(x['symbol'] for x in top))]) if top else {}
        bundled=_bundled();company=_company(symbol,refs,bundled)
        for i,row in enumerate(top):row.update(rank=i+1,company=_company(row['symbol'],toprefs,bundled))
        recognition=next((r for r in top if r['symbol']==symbol),None)
        top5_blocks=[]
        for row in top5_rows:
            day=row['trade_date']
            if not top5_blocks or top5_blocks[-1]['trade_date']!=day:
                top5_blocks.append({'ticker':symbol,'trade_date':day,'title':f"{symbol} — Top 5 Volume Trades ({date.fromisoformat(day).strftime('%d-%m-%Y')})",'rows':[],'max_volume':0})
            block=top5_blocks[-1]
            block['rows'].append(row)
            block['max_volume']=max(block['max_volume'],row['volume'] or 0)
        base={'top5_block':top5_blocks[0] if top5_blocks else None,'top5_blocks':top5_blocks,'symbol':symbol,'company':company,'market_date':market_date,'top5':top[:5],'top10':recognition,'first':bars[0]['trade_date'] if bars else None,'last':bars[-1]['trade_date'] if bars else None,
              'closes':[[r['trade_date'],float(r['close']) if _good(r.get('close')) else None] for r in bars],
              'breakouts':_breakouts(bars),'volume_comparison':_volume_comparison(bars)}
        if not bars:return {**base,'status':'NO_DATA','ranges':[],'card':{'symbol':symbol,'company':company or 'Company unavailable','status':'NO_DATA'},'technical':None}
        anchor=date.fromisoformat(bars[-1]['trade_date'])
        ranges=_summarize_ranges(bars,anchor)
        latest=bars[-1]; market_anchor=date.fromisoformat(market_date) if market_date else anchor
        monday=(market_anchor-timedelta(days=market_anchor.weekday())).isoformat(); month=market_anchor.replace(day=1).isoformat()
        def movement_for(start):
            older=next((r for r in reversed(bars) if r['trade_date']<start),None)
            current=latest['close'] if latest['trade_date']>=start else None
            return delta(current,older['close'] if older and _good(older['close']) else None) if _good(current) else {'change':None,'pct':None}
        change=delta(latest['close'] if _good(latest['close']) else None,latest['pr_close'] if _good(latest['pr_close']) else None)
        card={'symbol':symbol,'company':company or 'Company unavailable','trade_date':latest['trade_date'],'stale':bool(market_date and latest['trade_date']<market_date),'status':'OK','close':latest['close'] if _good(latest['close']) else None,'high':latest['high'] if _good(latest['high']) else None,'low':latest['low'] if _good(latest['low']) else None,'avg_price':latest['avg_price'] if _good(latest['avg_price']) else None,'volume':latest['volume'] if _good(latest['volume'],False) else None,**change,'week':movement_for(monday),'month':movement_for(month)}
        # RSI follows the existing full-history engine. Invalid closes are not
        # silently skipped. Daily classic pivots require genuine high/low/close.
        technical={'rsi':None,'pivots':None}
        if all(_good(b.get('close')) for b in bars):
            try:
                technical_service=TechnicalService(self.db_path)
                period=int(technical_service.repo.get_settings().get('rsi_period',14))
                technical['rsi']=wilder_rsi_series([float(b['close']) for b in bars],period)[-1]
            except (ValueError,TypeError,OverflowError,ZeroDivisionError):pass
        if all(_good(latest.get(k)) for k in ('high','low','close')) and latest['low']<=latest['close']<=latest['high']:
            technical['pivots']=TechnicalService.compute_classic_fib_camarilla_pivots(latest['high'],latest['low'],latest['close'])['classic']
        return {**base,'status':'OK','ranges':ranges,'card':card,'technical':technical}
