"""Native market views; source averages only, exact-date benchmark joins."""
from datetime import date, timedelta
from psx_app.database.schema import get_connection


def delta(value, baseline):
    if value is None or baseline is None or baseline <= 0:
        return {'change': None, 'pct': None, 'baseline': baseline}
    return {'change': value-baseline, 'pct': (value/baseline-1)*100, 'baseline': baseline}


class MarketExplorer:
    def __init__(self, db_path=None): self.db_path = db_path

    def metadata(self):
        with get_connection(self.db_path) as c:
            dates = [r[0] for r in c.execute('SELECT DISTINCT trade_date FROM equity_ohlcv ORDER BY trade_date DESC')]
            symbols = [r[0] for r in c.execute('SELECT DISTINCT symbol FROM equity_ohlcv ORDER BY symbol')]
        return {'dates': dates, 'symbols': symbols, 'benchmark_note': 'Imported INDEX series (unverified identity; confirm it is KSE-100). Volume is calculated as the sum of all imported cash-symbol volumes on that date; not verified index-constituent volume.'}

    def volume(self, selected=None, top_n=10):
        top_n = min(10, max(1, int(top_n)))
        with get_connection(self.db_path) as c:
            selected = selected or c.execute('SELECT MAX(trade_date) FROM equity_ohlcv').fetchone()[0]
            rows = [dict(r) for r in c.execute('SELECT symbol,volume FROM equity_ohlcv WHERE trade_date=? AND volume>0 ORDER BY volume DESC,symbol', (selected,))]
        total = sum(r['volume'] for r in rows)
        parts = rows[:top_n]
        others = total-sum(r['volume'] for r in parts)
        if others: parts.append({'symbol': 'Others', 'volume': others})
        for r in parts: r['pct'] = r['volume']/total*100 if total else 0
        return {'date': selected, 'top_n': top_n, 'total': total, 'parts': parts, 'top_pct': (total-others)/total*100 if total else 0, 'universe': 'All imported cash symbols with positive reported volume; not exchange-wide coverage verification.'}

    def symbol(self, symbol, n=50, end=None):
        n = max(1, min(6000, int(n)))
        with get_connection(self.db_path) as c:
            rows = [dict(r) for r in c.execute('SELECT * FROM equity_ohlcv WHERE symbol=? AND trade_date<=? ORDER BY trade_date DESC LIMIT ?', (symbol.upper(),end or '9999-12-31',n))]
            if not rows: return {'status':'NO_DATA','rows':[], 'index_rows':[]}
            first,last = rows[-1]['trade_date'],rows[0]['trade_date']
            prev = c.execute('SELECT close,trade_date FROM equity_ohlcv WHERE symbol=? AND trade_date<? ORDER BY trade_date DESC LIMIT 1',(symbol.upper(),first)).fetchone()
            monday = (date.fromisoformat(last)-timedelta(days=date.fromisoformat(last).weekday())).isoformat()
            week_base = c.execute('SELECT close,trade_date FROM equity_ohlcv WHERE symbol=? AND trade_date<? ORDER BY trade_date DESC LIMIT 1',(symbol.upper(),monday)).fetchone()
            week_index = c.execute('SELECT close FROM index_ohlcv WHERE trade_date=?',(week_base[1] if week_base else '',)).fetchone()
            baseline_index = c.execute('SELECT close FROM index_ohlcv WHERE trade_date=?',(prev[1] if prev else '',)).fetchone()
            index = {r['trade_date']:dict(r) for r in c.execute('SELECT * FROM index_ohlcv WHERE trade_date>=? AND trade_date<=?',(first,last))}
            cash_volumes = {r['trade_date']: dict(r) for r in c.execute('SELECT trade_date,SUM(volume) AS volume,COUNT(*) AS symbols FROM equity_ohlcv WHERE trade_date>=? AND trade_date<=? GROUP BY trade_date',(first,last))}
        idx_rows=[]
        for r in rows:
            r.update(delta(r['close'],r['pr_close']))
            if r['trade_date'] in index:
                ir=index[r['trade_date']];ir.update(delta(ir['close'],ir['pr_close']));ir['volume']=cash_volumes.get(r['trade_date'],{}).get('volume');ir['volume_symbols']=cash_volumes.get(r['trade_date'],{}).get('symbols',0);ir['volume_method']='SUM of imported cash-symbol volume on this date';idx_rows.append(ir)
        ilast=index.get(last,{})
        extrema=[]
        for label,key,maximum in [('Max intraday high','high',True),('Max closing high','close',True),('Min intraday low','low',False),('Min closing low','close',False),('Max source average','avg_price',True),('Min source average','avg_price',False),('Max volume','volume',True)]:
            valid=[r for r in rows if r.get(key) is not None]
            value=(max if maximum else min)((r[key] for r in valid),default=None)
            extrema.append({'label':label,'value':value,'dates':[r['trade_date'] for r in valid if r[key]==value]})
        return {'status':'OK','symbol':symbol.upper(),'requested':n,'count':len(rows),'first':first,'last':last,'rows':rows,'index_rows':idx_rows,'missing_index_dates':[r['trade_date'] for r in rows if r['trade_date'] not in index],'extrema':extrema,'symbol_change':delta(rows[0]['close'],prev[0] if prev else None),'index_change':delta(ilast.get('close'),baseline_index[0] if baseline_index else None),'week_symbol':delta(rows[0]['close'],week_base[0] if week_base else None),'week_index':delta(ilast.get('close'),week_index[0] if week_index else None),'baseline_date':prev[1] if prev else None,'week_baseline_date':week_base[1] if week_base else None,'benchmark_note':'Imported INDEX (KSE-100 identity unverified); exact matching dates only. Volume = sum of all imported cash-symbol volumes for each date, not verified index-constituent volume. Futures and account records are excluded to avoid double counting.'}
