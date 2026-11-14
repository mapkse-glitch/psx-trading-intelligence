"""Top imported daily cash-volume observations, never individual trades."""
from psx_app.database.schema import get_connection
from psx_app.services.volume_index1339 import _date


def top_volumes(db_path, date, symbol=''):
    date=_date(date)
    symbol=(symbol or '').strip().upper()
    if len(symbol)>24:
        raise ValueError('Invalid symbol')
    with get_connection(db_path) as c:
        if symbol:
            rows=c.execute('''SELECT symbol,trade_date,volume,close FROM equity_ohlcv
              WHERE symbol=? AND trade_date<=? ORDER BY volume DESC,trade_date DESC,symbol ASC LIMIT 10''',(symbol,date))
        else:
            rows=c.execute('''SELECT symbol,trade_date,volume,close FROM equity_ohlcv
              WHERE trade_date=? ORDER BY volume DESC,symbol ASC LIMIT 10''',(date,))
        return {'date':date,'symbol':symbol,'rows':[dict(x) for x in rows]}
