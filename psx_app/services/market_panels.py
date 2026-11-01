"""Read-only, bounded-result market panels; imported SEL_COMP_LIST only.
Trading-session gaps refer to stored sessions for the selected symbol, not a
fabricated exchange calendar. No nearest-date substitution for matched index.
"""
import calendar
from datetime import date, timedelta
from psx_app.database.schema import get_connection
from psx_app.services.market_explorer import delta
from psx_app.services.result_cache import persisted_result


def month_before(value):
    d = date.fromisoformat(value)
    year, month = (d.year, d.month-1) if d.month > 1 else (d.year-1, 12)
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1])).isoformat()


def reference_name(c):
    names = [r[0] for r in c.execute('SELECT DISTINCT list_name FROM company_reference ORDER BY list_name')]
    names = [n for n in names if ''.join(ch for ch in n.lower() if ch.isalnum()) == 'selcomplist']
    return min(names, key=lambda n: (n != 'SEL_COMP_LIST', n)) if names else None


def difference(a, b):
    return a-b if a is not None and b is not None else None


class MarketPanels:
    def __init__(self, db_path=None): self.db_path = db_path

    @persisted_result
    def matching(self, symbol):
        symbol = symbol.strip().upper()
        with get_connection(self.db_path) as c:
            latest = c.execute('SELECT trade_date,close FROM equity_ohlcv WHERE symbol=? ORDER BY trade_date DESC LIMIT 1', (symbol,)).fetchone()
            if not latest:
                return {'status':'NO_DATA','symbol':symbol,'rows':[],'latest':None,'latest_index':None}
            latest = dict(latest)
            cutoff = month_before(latest['trade_date'])
            index = c.execute('SELECT trade_date,close FROM index_ohlcv WHERE trade_date<=? ORDER BY trade_date DESC LIMIT 1', (latest['trade_date'],)).fetchone()
            index = dict(index) if index else None
            # The window counts ALL stored symbol sessions through the latest date;
            # filtering in the outer query must not shorten this trading-session gap.
            rows = [dict(r) for r in c.execute('''WITH history AS (
                SELECT trade_date,close,COUNT(*) OVER () - ROW_NUMBER() OVER (ORDER BY trade_date) AS sessions_ago
                FROM equity_ohlcv WHERE symbol=? AND trade_date<=?
            ) SELECT trade_date,close,sessions_ago FROM history WHERE trade_date<?
              ORDER BY ABS(close-?),trade_date DESC LIMIT 10''', (symbol, latest['trade_date'], cutoff, latest['close']))]
            dates = [r['trade_date'] for r in rows]
            indices = {r['trade_date']:dict(r) for r in c.execute('SELECT trade_date,close FROM index_ohlcv WHERE trade_date IN ('+','.join('?' for _ in dates)+')', dates)} if dates else {}
        for row in rows:
            old_index = indices.get(row['trade_date'])
            row.update(latest_close=latest['close'], latest_index_close=index['close'] if index else None,
                       close_difference=difference(latest['close'], row['close']),
                       index_date=old_index['trade_date'] if old_index else None,
                       index_close=old_index['close'] if old_index else None,
                       index_difference=difference(index['close'] if index else None, old_index['close'] if old_index else None))
        return {'status':'OK','symbol':symbol,'latest':latest,'latest_index':index,'cutoff':cutoff,'rows':rows,
                'basis':'All stored symbol history strictly before one calendar month prior to the latest symbol date. Ranked by absolute closing-price distance, newest date first on ties. Session gaps count stored symbol records; index joins use the exact matched date only.'}

    @persisted_result
    def sectors(self):
        with get_connection(self.db_path) as c:
            name = reference_name(c)
            if not name:
                return {'status':'NO_REFERENCE','source':None,'sectors':[]}
            rows = [dict(r) for r in c.execute('SELECT sector,COUNT(*) AS symbols FROM company_reference WHERE list_name=? GROUP BY sector ORDER BY sector', (name,))]
        return {'status':'OK','source':name,'sectors':rows}

    @persisted_result
    def small_cards(self, sector, sessions=14):
        sessions = min(6000, max(1, int(sessions)))
        with get_connection(self.db_path) as c:
            name = reference_name(c)
            if not name:
                return {'status':'NO_REFERENCE','cards':[],'index':None,'as_of':None,'requested':sessions,'source':None,'sector':sector}
            members = [dict(r) for r in c.execute('SELECT symbol,company,sector FROM company_reference WHERE list_name=? AND sector=? ORDER BY symbol', (name, sector))]
            if not members:
                return {'status':'NO_SECTOR','cards':[],'index':None,'as_of':None,'requested':sessions,'source':name,'sector':sector}
            as_of = c.execute('SELECT MAX(trade_date) FROM equity_ohlcv').fetchone()[0]
            if not as_of:
                return {'status':'OK','cards':[{**r,'status':'NO_DATA'} for r in members],'index':None,'as_of':None,'requested':sessions,'source':name,'sector':sector}
            anchor = date.fromisoformat(as_of)
            monday = (anchor-timedelta(days=anchor.weekday())).isoformat()
            month = anchor.replace(day=1).isoformat()
            stats = {}
            # At most 50 members per query, one compact aggregate per symbol returned.
            # No full per-symbol history travels to Python and no per-card query loop.
            for offset in range(0,len(members),50):
                symbols = [r['symbol'] for r in members[offset:offset+50]]
                sql = '''WITH ranked AS (
                    SELECT symbol,trade_date,close,pr_close,high,low,avg_price,volume,
                      ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY trade_date DESC) AS rn
                    FROM equity_ohlcv WHERE symbol IN ('''+','.join('?' for _ in symbols)+''') AND trade_date<=?
                ) SELECT symbol,
                    MAX(CASE WHEN rn=1 THEN trade_date END) AS trade_date,
                    MAX(CASE WHEN rn=1 THEN close END) AS close,
                    MAX(CASE WHEN rn=1 THEN pr_close END) AS pr_close,
                    MAX(CASE WHEN rn=1 THEN high END) AS high,
                    MAX(CASE WHEN rn=1 THEN low END) AS low,
                    MAX(CASE WHEN rn=1 THEN avg_price END) AS avg_price,
                    MAX(CASE WHEN rn=1 THEN volume END) AS volume,
                    COUNT(CASE WHEN rn<=? THEN 1 END) AS session_count,
                    MIN(CASE WHEN rn<=? THEN trade_date END) AS session_first,
                    MAX(CASE WHEN rn<=? THEN high END) AS session_high,
                    MIN(CASE WHEN rn<=? THEN low END) AS session_low,
                    MAX(CASE WHEN trade_date<? THEN trade_date END) AS week_baseline_date,
                    MAX(CASE WHEN trade_date<? THEN trade_date END) AS month_baseline_date
                  FROM ranked GROUP BY symbol'''
                for r in c.execute(sql, (*symbols, as_of, sessions, sessions, sessions, sessions, monday, month)):
                    stats[r['symbol']] = dict(r)
            # Fetch exact WTD/MTD baselines in bounded batches instead of N+1 lookups.
            keys = sorted({(r['symbol'], r[k]) for r in stats.values() for k in ('week_baseline_date','month_baseline_date') if r[k]})
            baselines = {}
            for offset in range(0,len(keys),100):
                pairs = keys[offset:offset+100]
                sql = 'SELECT symbol,trade_date,close FROM equity_ohlcv WHERE (symbol,trade_date) IN ('+','.join('(?,?)' for _ in pairs)+')'
                baselines.update({(r['symbol'],r['trade_date']):r['close'] for r in c.execute(sql, tuple(v for pair in pairs for v in pair))})
            # This one shared index window is reused across all sector cards.
            index_rows = [dict(r) for r in c.execute('SELECT trade_date,close,pr_close,high,low FROM index_ohlcv WHERE trade_date<=? ORDER BY trade_date DESC LIMIT ?', (as_of,sessions+1))]
        cards = []
        for member in members:
            row = stats.get(member['symbol'])
            if not row:
                cards.append({**member,'status':'NO_DATA'}); continue
            row.update(delta(row['close'],row['pr_close']))
            week_base = baselines.get((member['symbol'],row['week_baseline_date']))
            month_base = baselines.get((member['symbol'],row['month_baseline_date']))
            row['week'] = delta(row['close'] if row['trade_date']>=monday else None,week_base)
            row['month'] = delta(row['close'] if row['trade_date']>=month else None,month_base)
            cards.append({**member,**row,'status':'OK','stale':row['trade_date']<as_of})
        index = None
        if index_rows:
            window = index_rows[:sessions]
            previous = index_rows[sessions] if len(index_rows)>sessions else None
            latest = index_rows[0]
            index = {'latest':{**latest,**delta(latest['close'],latest['pr_close'])},
                     'window':{**delta(latest['close'],previous['close'] if previous else None),
                               'high':max((r['high'] for r in window if r['high'] is not None),default=None),
                               'low':min((r['low'] for r in window if r['low'] is not None),default=None),
                               'count':len(window),'first':window[-1]['trade_date'],'last':window[0]['trade_date'],
                               'baseline_date':previous['trade_date'] if previous else None}}
        return {'status':'OK','sector':sector,'source':name,'as_of':as_of,'requested':sessions,'cards':cards,'index':index,
                'basis':'Sessions are the last N stored records for each symbol and independently for the index, through the latest imported cash-market date. WTD/MTD use the last available close before Monday/month start; no new-period record or missing baseline is unavailable. Index session change uses the stored close immediately before its N-session window. Missing records are not filled.'}
