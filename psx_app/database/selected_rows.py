"""Fetch only incoming trading dates, in bounded, stable keyset pages."""
def date_rows(conn, table, dates):
    if table not in ('equity_ohlcv', 'futures_ohlcv', 'index_ohlcv'):
        raise ValueError('Unsupported canonical table')
    dates = sorted(set(dates))
    for offset in range(0, len(dates), 40):
        group = dates[offset:offset+40]
        last = -1
        while group:
            rows = conn.execute(f'SELECT * FROM {table} WHERE trade_date IN ({",".join("?" for _ in group)}) AND id>? ORDER BY id LIMIT 500', (*group, last)).fetchall()
            if not rows:
                break
            yield from rows
            last = rows[-1]['id']
