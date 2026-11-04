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
            # Rank only eligible older prices first. Count gaps for the ten
            # selected dates using the existing (symbol,trade_date) index, rather
            # than calculating two window functions for every stored session.
            rows = [dict(r) for r in c.execute('''WITH nearest AS (
                SELECT trade_date,close FROM equity_ohlcv
                WHERE symbol=? AND trade_date<?
                ORDER BY ABS(close-?),trade_date DESC LIMIT 10
            ) SELECT n.trade_date,n.close,
                (SELECT COUNT(*) FROM equity_ohlcv AS later
                 WHERE later.symbol=? AND later.trade_date>n.trade_date AND later.trade_date<=?) AS sessions_ago
              FROM nearest AS n ORDER BY ABS(n.close-?),n.trade_date DESC''',
              (symbol,cutoff,latest['close'],symbol,latest['trade_date'],latest['close']))]
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

    def matching_range(self, symbol, low, high, page=1, include_recent=False):
        """All matching closes in deterministic pages; gaps count every stored session."""
        import math
        symbol = symbol.strip().upper()
        if not math.isfinite(low) or not math.isfinite(high) or low < 0 or high < low:
            raise ValueError('Enter a valid nonnegative range with start no greater than end.')
        page = int(page)
        if page < 1 or page > 1000000:
            raise ValueError('Invalid page number.')
        page_size = 100
        with get_connection(self.db_path) as c:
            latest = c.execute('SELECT trade_date,close FROM equity_ohlcv WHERE symbol=? ORDER BY trade_date DESC LIMIT 1', (symbol,)).fetchone()
            if not latest:
                return {'status':'NO_DATA','symbol':symbol,'rows':[],'latest':None,'latest_index':None,'total':0,'page':page,'page_size':page_size,'include_recent':include_recent}
            latest = dict(latest)
            cutoff = month_before(latest['trade_date'])
            idx = c.execute('SELECT trade_date,close FROM index_ohlcv WHERE trade_date<=? ORDER BY trade_date DESC LIMIT 1', (latest['trade_date'],)).fetchone()
            idx = dict(idx) if idx else None
            # Rank before filtering, so the gap includes all stored records.
            date_limit = latest['trade_date'] if include_recent else cutoff
            date_op = '<=' if include_recent else '<'
            where = f'symbol=? AND trade_date{date_op}? AND close>=? AND close<=?'
            total = c.execute(f'SELECT COUNT(*) FROM equity_ohlcv WHERE {where}', (symbol,date_limit,low,high)).fetchone()[0]
            # One indexed symbol scan, exact-date index join and bounded page.
            rows = [dict(r) for r in c.execute(f'''WITH history AS (
                SELECT trade_date,close,ROW_NUMBER() OVER (ORDER BY trade_date DESC)-1 AS sessions_ago
                FROM equity_ohlcv WHERE symbol=? AND trade_date<=?
            ) SELECT h.trade_date,h.close,h.sessions_ago,i.trade_date AS index_date,i.close AS index_close
              FROM history h LEFT JOIN index_ohlcv i ON i.trade_date=h.trade_date
              WHERE h.trade_date{date_op}? AND h.close>=? AND h.close<=?
              ORDER BY ABS(h.close-?),h.trade_date DESC LIMIT ? OFFSET ?''',
              (symbol,latest['trade_date'],date_limit,low,high,latest['close'],page_size,(page-1)*page_size))]
        for row in rows:
            row.update(latest_close=latest['close'],latest_index_close=idx['close'] if idx else None,
                       close_difference=difference(latest['close'],row['close']),
                       index_difference=difference(idx['close'] if idx else None,row['index_close']))
        return {'status':'OK','symbol':symbol,'latest':latest,'latest_index':idx,'cutoff':cutoff,
                'rows':rows,'total':total,'page':page,'page_size':page_size,'include_recent':include_recent}

    def small_cards(self, sector=None, sessions=14):
        return self.small_cards_v1322(sector, sessions)

    @persisted_result
    def small_cards_v1322(self, sector=None, sessions=14):
        sessions = min(6000, max(1, int(sessions)))
        with get_connection(self.db_path) as c:
            name = reference_name(c)
            if not name:
                return {'status':'NO_REFERENCE','cards':[],'index':None,'as_of':None,'requested':sessions,'source':None,'sector':sector,'sectors':[]}
            sectors = [dict(r) for r in c.execute('SELECT sector,COUNT(*) AS symbols FROM company_reference WHERE list_name=? GROUP BY sector ORDER BY sector', (name,))]
            if sector is None and sectors: sector = sectors[0]['sector']
            members = [dict(r) for r in c.execute('SELECT symbol,company,sector FROM company_reference WHERE list_name=? AND sector=? ORDER BY symbol', (name, sector))]
            if not members:
                return {'status':'NO_SECTOR','cards':[],'index':None,'as_of':None,'requested':sessions,'source':name,'sector':sector,'sectors':sectors}
            as_of = c.execute('SELECT MAX(trade_date) FROM equity_ohlcv').fetchone()[0]
            if not as_of:
                return {'status':'OK','cards':[{**r,'status':'NO_DATA'} for r in members],'index':None,'as_of':None,'requested':sessions,'source':name,'sector':sector,'sectors':sectors}
            anchor = date.fromisoformat(as_of)
            monday = (anchor-timedelta(days=anchor.weekday())).isoformat()
            month = anchor.replace(day=1).isoformat()
            stats = {}
            # Each UNION branch uses the existing (symbol,trade_date) index to read
            # only N latest rows BEFORE numbering. WTD/MTD use two indexed seeks.
            # One network query per <=50 members, not one request per card and not
            # a window sort over every historical row in the selected sector.
            for offset in range(0,len(members),50):
                branches, params = [], []
                for member in members[offset:offset+50]:
                    sym = member['symbol']
                    branches.append('''SELECT ? AS symbol,
                        MAX(CASE WHEN rn=1 THEN trade_date END) AS trade_date,
                        MAX(CASE WHEN rn=1 THEN close END) AS close,
                        MAX(CASE WHEN rn=1 THEN pr_close END) AS pr_close,
                        MAX(CASE WHEN rn=1 THEN high END) AS high,
                        MAX(CASE WHEN rn=1 THEN low END) AS low,
                        MAX(CASE WHEN rn=1 THEN avg_price END) AS avg_price,
                        MAX(CASE WHEN rn=1 THEN volume END) AS volume,
                        COUNT(*) AS session_count, MIN(trade_date) AS session_first,
                        MAX(high) AS session_high, MIN(low) AS session_low,
                        (SELECT trade_date FROM equity_ohlcv WHERE symbol=? AND trade_date<? ORDER BY trade_date DESC LIMIT 1) AS week_baseline_date,
                        (SELECT trade_date FROM equity_ohlcv WHERE symbol=? AND trade_date<? ORDER BY trade_date DESC LIMIT 1) AS month_baseline_date
                        FROM (SELECT *,ROW_NUMBER() OVER (ORDER BY trade_date DESC) AS rn
                          FROM (SELECT trade_date,close,pr_close,high,low,avg_price,volume
                            FROM equity_ohlcv WHERE symbol=? AND trade_date<=?
                            ORDER BY trade_date DESC LIMIT ?) AS limited) AS ranked''')
                    params.extend((sym,sym,monday,sym,month,sym,as_of,sessions))
                for row in c.execute(' UNION ALL '.join(branches), params):
                    if row['trade_date'] is not None: stats[row['symbol']] = dict(row)
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
        return {'status':'OK','sector':sector,'source':name,'as_of':as_of,'requested':sessions,'cards':cards,'index':index,'sectors':sectors,
                'basis':'Sessions are the last N stored records for each symbol and independently for the index, through the latest imported cash-market date. WTD/MTD use the last available close before Monday/month start; no new-period record or missing baseline is unavailable. Index session change uses the stored close immediately before its N-session window. Missing records are not filled.'}
