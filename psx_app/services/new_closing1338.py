"""Determine a new closing high using earlier imported closes only."""
import math

def new_closing_high(connection, symbol, row):
    if not row or not isinstance(row.get('close'), (int, float)) or not math.isfinite(row['close']) or row['close'] <= 0:
        return False
    previous = connection.execute("SELECT MAX(close) FROM equity_ohlcv WHERE symbol=? AND trade_date<? AND close>0", (symbol, row['trade_date'])).fetchone()[0]
    return previous is not None and math.isfinite(previous) and row['close'] > previous


def closing_ath_record(connection, symbol):
    """Earliest strict closing record at the maximum over all imported history.

    A first observation has no prior record to exceed; later ties are not new.
    """
    row = connection.execute("""SELECT trade_date, close FROM equity_ohlcv
        WHERE symbol=? AND close>0 AND close=(SELECT MAX(close) FROM equity_ohlcv WHERE symbol=? AND close>0)
        ORDER BY trade_date ASC LIMIT 1""", (symbol, symbol)).fetchone()
    if row is None:
        return None
    record = dict(row)
    return record if new_closing_high(connection, symbol, record) else None

def is_closing_ath(row, record):
    return bool(row and record and row.get('trade_date') == record['trade_date'] and row.get('close') == record['close'])
