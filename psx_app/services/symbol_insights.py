"""Read-only imported symbol extrema and date-anchored comparisons."""
import math
from psx_app.database.schema import get_connection
from psx_app.services.result_cache import persisted_result

ANCHOR = '2026-02-27'
START_2023 = '2023-10-01'
METRICS = [('max_high','high',True),('max_close','close',True),('min_low','low',False),('min_close','close',False),('max_average','avg_price',True),('min_average','avg_price',False),('max_volume','volume',True),('min_volume','volume',False)]

def valid(value):
    return value is not None and isinstance(value,(int,float)) and math.isfinite(value)

def empty_window():
    return {'count':0,'first':None,'last':None,'metrics':{name:{'value':None,'date':None,'ties':0} for name,_,_ in METRICS}}

def add(window,row):
    day=row['trade_date']; window['count']+=1
    window['first']=day if window['first'] is None or day<window['first'] else window['first']
    window['last']=day if window['last'] is None or day>window['last'] else window['last']
    for name,key,is_max in METRICS:
        value=row.get(key); current=window['metrics'][name]
        if not valid(value): continue
        old=current['value']
        if old is None or (value>old if is_max else value<old):current.update(value=value,date=day,ties=1)
        elif value==old:
            current['ties']+=1
            if day>current['date']:current['date']=day

def difference(value,base):
    if not valid(value) or not valid(base):return {'value':None,'pct':None}
    return {'value':value-base,'pct':(value-base)/base*100 if base>0 else None}

def comparison(anchor,latest,after):
    a=anchor or {};now=latest or {};m=after['metrics']
    def entry(key):return m[key]
    hi=entry('max_high');cl=entry('max_close');lo=entry('min_low');lc=entry('min_close')
    return {'anchor':anchor,'latest':latest,'after':after,
        'max_high_vs_anchor':difference(hi['value'],a.get('high')),
        'max_close_vs_anchor':difference(cl['value'],a.get('close')),
        'min_low_vs_anchor':difference(lo['value'],a.get('low')),
        'min_close_vs_anchor':difference(lc['value'],a.get('close')),
        'current_high_vs_anchor':difference(now.get('high'),a.get('high')),
        'current_close_vs_anchor':difference(now.get('close'),a.get('close')),
        'current_high_vs_max':difference(now.get('high'),hi['value']),
        'current_close_vs_max':difference(now.get('close'),cl['value'])}

class SymbolInsights:
    def __init__(self,db_path=None):self.db_path=db_path
    @persisted_result
    def report(self,symbol,sessions=14):
        symbol=symbol.strip().upper();sessions=max(1,min(6000,int(sessions)))
        windows={name:empty_window() for name in ('session','all','since_2023','since_2026','after_anchor')}
        latest=None;anchor=None;count=0
        with get_connection(self.db_path) as c:
            rows=c.execute('SELECT trade_date,open,high,low,close,pr_close,avg_price,volume FROM equity_ohlcv WHERE symbol=? ORDER BY trade_date DESC',(symbol,))
            for raw in rows:
                row=dict(raw);count+=1
                if latest is None:latest=row
                add(windows['all'],row)
                if count<=sessions:add(windows['session'],row)
                if row['trade_date']>=START_2023:add(windows['since_2023'],row)
                if row['trade_date']>=ANCHOR:add(windows['since_2026'],row)
                if row['trade_date']>ANCHOR:add(windows['after_anchor'],row)
                if row['trade_date']==ANCHOR:anchor=row
            if latest is None:return {'status':'NO_DATA','symbol':symbol,'requested':sessions}
            refs=[dict(r) for r in c.execute('SELECT list_name,company,sector FROM company_reference WHERE symbol=? ORDER BY list_name',(symbol,))]
            def rank(r):
                n=''.join(ch for ch in r['list_name'].lower() if ch.isalnum())
                return (0 if 'sectorwise' in n else 1 if n=='complist' else 2,r['list_name'])
            ref=min(refs,key=rank) if refs else None
            if ref:company={'name':ref['company'],'sector':ref['sector']}
            else:
                from psx_app.services.sector_reference import BUNDLED
                import json
                r=next((x for x in json.loads(BUNDLED.read_text()).get('COMP_LIST',[]) if x['symbol']==symbol),None)
                company={'name':r['company'] if r else None,'sector':r['sector'] if r else None}
            idx_latest_raw=c.execute('SELECT trade_date,open,high,low,close,pr_close FROM index_ohlcv WHERE trade_date<=? ORDER BY trade_date DESC LIMIT 1',(latest['trade_date'],)).fetchone()
            idx_latest=dict(idx_latest_raw) if idx_latest_raw else None
            idx_anchor=None;idx_after=empty_window()
            if idx_latest:
                for raw in c.execute('SELECT trade_date,open,high,low,close,pr_close FROM index_ohlcv WHERE trade_date>=? AND trade_date<=? ORDER BY trade_date DESC',(ANCHOR,idx_latest['trade_date'])):
                    row=dict(raw)
                    if row['trade_date']==ANCHOR:idx_anchor=row
                    elif row['trade_date']>ANCHOR:add(idx_after,row)
        return {'status':'OK','symbol':symbol,'requested':sessions,'company':company,'latest':latest,'windows':windows,
                'symbol_comparison':comparison(anchor,latest,windows['after_anchor']),
                'index_comparison':comparison(idx_anchor,idx_latest,idx_after),
                'index_note':'Imported index through the selected symbol’s latest stored date; a different latest date is shown explicitly. Index average and index-traded volume are not supplied.'}
