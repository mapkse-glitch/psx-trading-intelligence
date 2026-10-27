from psx_app.services.result_cache import persisted_result
"""Native market views; source averages only, exact-date benchmark joins."""
from datetime import date, timedelta
from psx_app.database.schema import get_connection


def delta(value, baseline):
    if value is None or baseline is None or baseline <= 0:
        return {'change': None, 'pct': None, 'baseline': baseline}
    return {'change': value-baseline, 'pct': (value/baseline-1)*100, 'baseline': baseline}


class MarketExplorer:
    def __init__(self, db_path=None): self.db_path = db_path

    @persisted_result
    def metadata(self):
        with get_connection(self.db_path) as c:
            dates = [r[0] for r in c.execute('SELECT DISTINCT trade_date FROM equity_ohlcv ORDER BY trade_date DESC')]
            symbols = [r[0] for r in c.execute('SELECT DISTINCT symbol FROM equity_ohlcv ORDER BY symbol')]
        return {'dates': dates, 'symbols': symbols, 'benchmark_note': 'Imported INDEX series (unverified identity; confirm it is KSE-100). Volume is calculated as the sum of all imported cash-symbol volumes on that date; not verified index-constituent volume.'}

    @persisted_result
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

    @persisted_result
    def symbol(self, symbol, n=50, end=None):
        symbol = symbol.strip().upper()
        n = max(1, min(6000, int(n)))
        with get_connection(self.db_path) as c:
            # One extra symbol record provides the previous volume for the oldest displayed row.
            history = [dict(r) for r in c.execute(
                'SELECT * FROM equity_ohlcv WHERE symbol=? AND trade_date<=? ORDER BY trade_date DESC LIMIT ?',
                (symbol, end or '9999-12-31', n + 1))]
            if not history:
                return {'status': 'NO_DATA', 'rows': [], 'index_rows': []}
            rows = history[:n]
            first, last = rows[-1]['trade_date'], rows[0]['trade_date']
            prev = history[n] if len(history) > n else None
            anchor = date.fromisoformat(last)
            monday = (anchor - timedelta(days=anchor.weekday())).isoformat()
            week_base = c.execute('SELECT close,trade_date FROM equity_ohlcv WHERE symbol=? AND trade_date<? ORDER BY trade_date DESC LIMIT 1', (symbol, monday)).fetchone()
            week_index = c.execute('SELECT close FROM index_ohlcv WHERE trade_date=?', (week_base[1] if week_base else '',)).fetchone()
            baseline_index = c.execute('SELECT close FROM index_ohlcv WHERE trade_date=?', (prev['trade_date'] if prev else '',)).fetchone()
            index_history = [dict(r) for r in c.execute('SELECT * FROM index_ohlcv WHERE trade_date>=? AND trade_date<=? ORDER BY trade_date DESC', (first, last))]
            index_before = c.execute('SELECT * FROM index_ohlcv WHERE trade_date<? ORDER BY trade_date DESC LIMIT 1', (first,)).fetchone()
            if index_before:
                index_history.append(dict(index_before))
            # A separate, dated latest-index card does not pretend an older index is same-day.
            latest_index_history = [dict(r) for r in c.execute('SELECT * FROM index_ohlcv WHERE trade_date<=? ORDER BY trade_date DESC LIMIT 2', (last,))]
            # Exact requested benchmark dates avoid scanning years of unrelated cash data
            # when the imported index is much older than the selected symbol.
            cash_volumes = {}
            volume_dates = sorted({r['trade_date'] for r in index_history})
            for offset in range(0, len(volume_dates), 200):
                group = volume_dates[offset:offset+200]
                sql = 'SELECT trade_date,SUM(volume) AS volume,COUNT(volume) AS reported_symbols,COUNT(*) AS symbols FROM equity_ohlcv WHERE trade_date IN (' + ','.join('?' for _ in group) + ') GROUP BY trade_date'
                cash_volumes.update({r['trade_date']: dict(r) for r in c.execute(sql, group)})
            # Ranges are independent of the displayed-row limit and bounded to YTD / 180 days.
            range_start = min(anchor.replace(month=1, day=1), anchor - timedelta(days=179)).isoformat()
            range_rows = [dict(r) for r in c.execute('SELECT trade_date,high,low FROM equity_ohlcv WHERE symbol=? AND trade_date>=? AND trade_date<=? ORDER BY trade_date', (symbol, range_start, last))]
            references = [dict(r) for r in c.execute('SELECT list_name,company,sector FROM company_reference WHERE symbol=? ORDER BY list_name', (symbol,))]

        def reference_rank(row):
            name = ''.join(ch for ch in row['list_name'].lower() if ch.isalnum())
            return (0 if 'sectorwise' in name else 1 if name == 'complist' else 2, row['list_name'])
        reference = min(references, key=reference_rank) if references else None
        if reference:
            company = {'name': reference['company'], 'sector': reference['sector'],
                       'source': 'Imported company reference: ' + reference['list_name']}
        else:
            from psx_app.services.sector_reference import BUNDLED
            import json
            bundled = next((r for r in json.loads(BUNDLED.read_text()).get('COMP_LIST', []) if r['symbol'] == symbol), None)
            company = {'name': bundled['company'] if bundled else None,
                       'sector': bundled['sector'] if bundled else None,
                       'source': 'Bundled Sector Wise company directory' if bundled else None}

        # A missing/zero prior volume is undefined, not 0% or infinity.
        def volume_change(current, previous):
            value, baseline = current.get('volume'), previous.get('volume') if previous else None
            valid = value is not None and value >= 0 and baseline is not None and baseline > 0
            current['volume_pct'] = (value / baseline - 1) * 100 if valid else None
            current['previous_volume'] = baseline
            current['volume_baseline_date'] = previous['trade_date'] if previous else None

        for i, row in enumerate(rows):
            row.update(delta(row['close'], row['pr_close']))
            volume_change(row, history[i+1] if i+1 < len(history) else None)
        for i, row in enumerate(index_history):
            row.update(delta(row['close'], row['pr_close']))
            volume = cash_volumes.get(row['trade_date'], {})
            row['volume'] = volume.get('volume')
            row['volume_symbols'] = volume.get('reported_symbols', 0)
            row['volume_method'] = 'SUM of imported cash-symbol volume on this date'
        for i, row in enumerate(index_history):
            volume_change(row, index_history[i+1] if i+1 < len(index_history) else None)
        index = {r['trade_date']: r for r in index_history if first <= r['trade_date'] <= last}
        idx_rows = [index[r['trade_date']] for r in rows if r['trade_date'] in index]
        ilast = index.get(last, {})
        latest_index = latest_index_history[0] if latest_index_history else None
        if latest_index:
            latest_index.update(delta(latest_index['close'], latest_index['pr_close']))
        ranges = []
        for label, days in [("Day's Range", 1), ('30 Days Range', 30), ('60 Days Range', 60), ('90 Days Range', 90), ('180 Days Range', 180), ("Year's Range", None)]:
            start = (anchor - timedelta(days=days-1)) if days else anchor.replace(month=1, day=1)
            window = [r for r in range_rows if r['trade_date'] >= start.isoformat()]
            high = max((r['high'] for r in window if r.get('high') is not None), default=None)
            low = min((r['low'] for r in window if r.get('low') is not None), default=None)
            ranges.append({'label': label, 'start': start.isoformat(), 'end': last,
                           'high': high, 'low': low, 'records': len(window),
                           'first_record': window[0]['trade_date'] if window else None,
                           'last_record': window[-1]['trade_date'] if window else None})
        extrema = []
        for label,key,maximum in [('Max intraday high','high',True),('Max closing high','close',True),('Min intraday low','low',False),('Min closing low','close',False),('Max source average','avg_price',True),('Min source average','avg_price',False),('Max volume','volume',True)]:
            valid = [r for r in rows if r.get(key) is not None]
            value = (max if maximum else min)((r[key] for r in valid), default=None)
            extrema.append({'label': label, 'value': value, 'dates': [r['trade_date'] for r in valid if r[key] == value]})
        return {'status':'OK','symbol':symbol,'company':company,'latest_symbol':rows[0],
                'latest_index':latest_index,'ranges':ranges,
                'range_basis':'Calendar-day windows including the latest stored symbol date; Year means January 1 through that date. Available imported records only; not affected by Records filter.',
                'volume_change_basis':'Previous stored symbol record for symbol volume; previous stored index date for index volume. Index volume is the sum of imported cash volumes, not verified constituent volume. Missing or nonpositive prior volume has no percentage.',
                'requested':n,'count':len(rows),'first':first,'last':last,'rows':rows,'index_rows':idx_rows,
                'missing_index_dates':[r['trade_date'] for r in rows if r['trade_date'] not in index],
                'extrema':extrema,'symbol_change':delta(rows[0]['close'],prev['close'] if prev else None),
                'index_change':delta(ilast.get('close'),baseline_index[0] if baseline_index else None),
                'week_symbol':delta(rows[0]['close'],week_base[0] if week_base else None),
                'week_index':delta(ilast.get('close'),week_index[0] if week_index else None),
                'baseline_date':prev['trade_date'] if prev else None,'week_baseline_date':week_base[1] if week_base else None,
                'benchmark_note':'Imported INDEX (KSE-100 identity unverified); exact matching dates only. Volume = sum of all imported cash-symbol volumes for each date, not verified index-constituent volume. Futures and account records are excluded to avoid double counting.'}
