"""Date-integrity guard: never market future-dated historical rows as today's signal."""
from datetime import datetime
from zoneinfo import ZoneInfo
from psx_app.database.schema import get_connection


def date_integrity(db_path=None):
    today = datetime.now(ZoneInfo('Asia/Karachi')).date().isoformat()
    tables = {'cash': 'equity_ohlcv', 'futures': 'futures_ohlcv', 'top5': 'top5_volume_records', 'accounts': 'account_daily_symbol_summary', 'executions': 'trade_executions', 'index': 'index_ohlcv'}
    result = {'today': today, 'timezone': 'Asia/Karachi', 'sources': {}, 'future_rows_count': 0}
    with get_connection(db_path) as conn:
        existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for name, table in tables.items():
            if table not in existing: continue
            row = conn.execute(f'SELECT MIN(trade_date), MAX(trade_date), COUNT(*), SUM(CASE WHEN trade_date > ? THEN 1 ELSE 0 END) FROM {table}', (today,)).fetchone()
            result['sources'][name] = {'first_date': row[0], 'latest_date': row[1], 'rows': row[2], 'future_rows': row[3] or 0}
            result['future_rows_count'] += row[3] or 0
    result['ok'] = result['future_rows_count'] == 0
    result['message'] = ('No future-dated rows detected. This does not prove all historical dates are correct.' if result['ok'] else
                         'Future-dated rows detected. Setups are blocked. Open Settings → Date normalization, review the dry-run plan, then apply only verified corrections.')
    return result
