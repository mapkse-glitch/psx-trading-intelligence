"""Run outside web requests: python -m tools.refresh_learning --symbols ATRL PRL"""
import argparse,json
from psx_app.database.schema import init_db,get_connection
from psx_app.services.learning_research import train_symbol
from psx_app.services.forecast_ledger import ForecastLedger

def main():
    p=argparse.ArgumentParser();p.add_argument('--symbols',nargs='+');args=p.parse_args();init_db()
    if args.symbols: symbols=args.symbols
    else:
        with get_connection() as c:symbols=[r[0] for r in c.execute('SELECT DISTINCT symbol FROM equity_ohlcv ORDER BY symbol')]
    for symbol in symbols:
        try:
            r=train_symbol(symbol);print(json.dumps({k:r.get(k) for k in ('symbol','as_of','status','samples','beats_baseline_brier')}))
        except Exception: print(json.dumps({'symbol':symbol,'status':'FAILED','note':'Inspect local driver logs; no model promoted.'}))
    print(json.dumps(ForecastLedger().reconcile(limit=1000)))
if __name__=='__main__':main()
