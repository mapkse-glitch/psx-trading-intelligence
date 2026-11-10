"""Determine a new closing high using earlier imported closes only."""
import math

def new_closing_high(connection, symbol, row):
    if not row or not isinstance(row.get('close'), (int, float)) or not math.isfinite(row['close']) or row['close'] <= 0:
        return False
    previous = connection.execute("SELECT MAX(close) FROM equity_ohlcv WHERE symbol=? AND trade_date<? AND close>0", (symbol, row['trade_date'])).fetchone()[0]
    return previous is not None and math.isfinite(previous) and row['close'] > previous
