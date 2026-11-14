"""Cash-market daily volume with same-date imported index movements."""
from datetime import date
import math
from psx_app.database.schema import get_connection


def _date(value):
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError()
        return value
    except (TypeError, ValueError):
        raise ValueError('Use valid ISO dates')


def _valid(value):
    return value is not None and math.isfinite(float(value)) and float(value) > 0


def daily_volume_index(db_path, start, end):
    start, end = _date(start), _date(end)
    if start > end:
        raise ValueError('Start date must not be after end date')
    with get_connection(db_path) as c:
        volumes = [dict(r) for r in c.execute('''SELECT trade_date,SUM(volume) AS volume
            FROM equity_ohlcv WHERE trade_date>=? AND trade_date<=?
            GROUP BY trade_date ORDER BY trade_date''', (start,end))]
        previous = c.execute('SELECT close FROM index_ohlcv WHERE trade_date<? ORDER BY trade_date DESC LIMIT 1',(start,)).fetchone()
        previous = previous['close'] if previous else None
        index = {}
        for r in c.execute('SELECT trade_date,close FROM index_ohlcv WHERE trade_date>=? AND trade_date<=? ORDER BY trade_date',(start,end)):
            close = r['close']
            index[r['trade_date']] = (close if _valid(close) else None,
                float(close)-float(previous) if _valid(close) and _valid(previous) else None)
            previous = close
    rows = []
    for row in volumes:
        close, movement = index.get(row['trade_date'], (None, None))
        rows.append({'date':row['trade_date'],'volume':row['volume'],'index_close':close,'index_change':movement})
    return {'start':start,'end':end,'rows':rows}
