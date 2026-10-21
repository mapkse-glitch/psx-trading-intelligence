"""Conservative, reversible date cleanup certified by a newly supplied workbook.

Never guess dates from the computer clock, contract month, or the latest date.
Only quarantine an out-of-coverage row when its day/month-swapped key has
identical seven OHLCV measures in the typed-date source. The original full row
is retained in import_issues in the same import transaction.
"""
import json
from datetime import date

MEASURES = ('volume', 'pr_close', 'high', 'low', 'open', 'close', 'avg_price')


def quarantine_verified_swaps(conn, mode, records, batch_id, source_file_id, now):
    if not records or mode not in ('CASH', 'FUTURES'):
        return 0
    table, key = ('equity_ohlcv', 'symbol') if mode == 'CASH' else ('futures_ohlcv', 'contract_symbol')
    verified = {(r['trade_date'], r[key]): r for r in records}
    first = min(r['trade_date'] for r in records)
    last = max(r['trade_date'] for r in records)
    repairs = []
    for stored in conn.execute(f'SELECT * FROM {table} WHERE trade_date < ? OR trade_date > ?', (first, last)):
        row = dict(stored)
        try:
            y, m, d = map(int, row['trade_date'].split('-'))
            flipped = date(y, d, m).isoformat()
        except (ValueError, TypeError):
            continue
        src = verified.get((flipped, row[key]))
        if not src or not all(row[col] == src[col] for col in MEASURES):
            continue
        if not any(src[col] not in (None, 0) for col in MEASURES):
            continue
        repairs.append((row, flipped))
    for row, corrected in repairs:
        conn.execute('''INSERT INTO import_issues
            (batch_id,source_file_id,module,severity,issue_type,symbol,trade_date,message,raw_payload,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (batch_id, source_file_id, mode, 'WARNING', 'SOURCE_VERIFIED_DATE_SWAP', row[key], row['trade_date'],
             f"Quarantined legacy date {row['trade_date']}; typed source certifies {corrected} with identical OHLCV. Original row retained here.",
             json.dumps({'table': table, 'original_row': row, 'verified_date': corrected}), now))
        conn.execute(f'DELETE FROM {table} WHERE id=?', (row['id'],))
    return len(repairs)
