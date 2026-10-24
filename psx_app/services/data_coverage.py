from psx_app.services.result_cache import persisted_result
"""Read-only per-instrument coverage; never manufacture cash OHLCV from other modules."""
import re
from psx_app.database.schema import get_connection
from psx_app.services.technical_service import TechnicalService
from psx_app.services.sector_reference import SectorReference
from psx_app.config import CORE_36_TICKERS

CONTRACT_SUFFIX = re.compile(r'[-\s](?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z0-9]*$')

class DataCoverage:
    def __init__(self, db_path=None): self.db_path = db_path

    def report(self, search=''):
        result=dict(self._full_report())
        q=search.strip().upper()
        if q:
            result['items']=[r for r in result['items'] if q in r['symbol'] or q in r['sector'].upper()]
            result['count']=len(result['items'])
        return result

    @persisted_result
    def _full_report(self):
        items = {r['symbol']: r for r in TechnicalService(self.db_path).get_universe_summary(scope='all')['items']}
        with get_connection(self.db_path) as c:
            cash = {r['symbol']:dict(r) for r in c.execute('SELECT symbol,COUNT(*) AS rows,MIN(trade_date) AS first,MAX(trade_date) AS latest FROM equity_ohlcv GROUP BY symbol')}
            futures = {r['symbol']:dict(r) for r in c.execute('SELECT base_symbol AS symbol,COUNT(*) AS rows,MAX(trade_date) AS latest FROM futures_ohlcv GROUP BY base_symbol')}
            top5 = {r['symbol']:dict(r) for r in c.execute('SELECT ticker AS symbol,COUNT(*) AS rows,MAX(trade_date) AS latest FROM top5_volume_records GROUP BY ticker')}
            account_rows = [dict(r) for r in c.execute('SELECT symbol,account_id,COUNT(*) AS rows,MAX(trade_date) AS latest FROM trade_executions GROUP BY symbol,account_id')]
            summaries = [dict(r) for r in c.execute('SELECT symbol,account_id,COUNT(*) AS rows,MAX(trade_date) AS latest FROM account_daily_symbol_summary GROUP BY symbol,account_id')]
            index = dict(c.execute('SELECT COUNT(*) AS rows,MIN(trade_date) AS first,MAX(trade_date) AS latest FROM index_ohlcv').fetchone())
        account = {}
        for r in account_rows + summaries:
            original = r['symbol']; sym = original if original in cash else CONTRACT_SUFFIX.sub('', original)
            rec = account.setdefault(sym, {'symbols':set(), 'accounts':set(), 'latest':None})
            rec['symbols'].add(original); rec['accounts'].add(r['account_id'])
            rec['latest'] = max(rec['latest'] or '', r['latest'] or '')
        lists = SectorReference(self.db_path).lists()
        directory = {r['symbol']:r for r in lists.get('COMP_LIST', [])}
        members = {}
        for name,rows in lists.items():
            for r in rows: members.setdefault(r['symbol'], []).append(name)
        latest = max((r['latest'] for r in cash.values()), default=None)
        all_symbols = sorted(set(cash)|set(futures)|set(top5)|set(account)|set(members)|set(CORE_36_TICKERS))
        rows = []
        for sym in all_symbols:
            data=cash.get(sym, {}); tech=items.get(sym, {}); sig=tech.get('signal') or {}; plan=sig.get('trade_plan') or {}
            notes=[]
            if not data: notes.append('No stored cash OHLCV. Reference membership, trade executions, ranked Top5 trades and futures prices cannot replace cash candles.')
            elif not tech: notes.append('Cash history exists but technical summary is unavailable; investigate engine coverage.')
            else:
                if data['latest'] != latest: notes.append('Historical cash data exists; behind latest imported cash session. Not a current-session candidate.')
                if sig.get('combined_signal')=='INSUFFICIENT DATA': notes.append('Insufficient signal-ready indicators/history; not absent data.')
                if float(tech.get('volume') or 0)<=0: notes.append('Latest symbol session has no positive reported volume.')
                if plan.get('status')!='VALID': notes.append(plan.get('reason') or 'No valid opening plan.')
            acct=account.get(sym, {})
            rows.append(dict(symbol=sym, sector=directory.get(sym, {}).get('sector','Unclassified'),
                             cash_rows=data.get('rows',0), first_cash_date=data.get('first'), latest_cash_date=data.get('latest'),
                             engine_bars=tech.get('bars_count',0), freshness=tech.get('data_freshness',{}).get('status','NO_CASH_DATA'),
                             signal=sig.get('combined_signal','NO_CASH_DATA'), score=sig.get('score'), plan_status=plan.get('status','UNAVAILABLE'),
                             futures_rows=futures.get(sym,{}).get('rows',0), latest_futures_date=futures.get(sym,{}).get('latest'),
                             top5_rows=top5.get(sym,{}).get('rows',0), latest_top5_date=top5.get(sym,{}).get('latest'),
                             account_symbols=sorted(acct.get('symbols',[])), accounts=sorted(acct.get('accounts',[])), latest_account_date=acct.get('latest'),
                             reference_lists=members.get(sym,[]), notes=notes))
        summary=dict(cash_symbols=len(cash), technical_symbols=len(items),
                     cash_missing_in_engine=sorted(set(cash)-set(items)), core_missing_cash=sorted(set(CORE_36_TICKERS)-set(cash)),
                     futures_base_symbols=len(futures), futures_missing_cash=sorted(set(futures)-set(cash)),
                     top5_symbols=len(top5), top5_missing_cash=sorted(set(top5)-set(cash)),
                     account_base_symbols=len(account), account_missing_cash=sorted(set(account)-set(cash)),
                     current_cash_symbols=sum(r['latest']==latest for r in cash.values()),
                     stale_cash_symbols=sum(r['latest']!=latest for r in cash.values()),
                     insufficient_signal_symbols=sum(r.get('signal',{}).get('combined_signal')=='INSUFFICIENT DATA' for r in items.values()),
                     latest_cash_date=latest, index=index)
        return dict(summary=summary, count=len(rows), items=rows,
                    note='Counts describe imported records, not an exchange-verified active security list. Historical, rights and inactive securities may be included. Only cash OHLCV drives equity indicators. Futures-observed is not broker short eligibility. INDEX identity and volume are unverified/unavailable in the legacy schema. Dates are each source latest, not assumed equal.')
