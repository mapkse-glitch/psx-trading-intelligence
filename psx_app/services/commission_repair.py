"""One-time atomic commission repair; unverified historic summaries are never guessed."""
import json
import threading
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

_MARKER = 'commission_repair_pkr_v1'
_lock = threading.Lock()
_done = False


def ensure_repaired(db_path=None):
    global _done
    if _done:
        return
    with _lock:
        if _done:
            return
        _done = repair(db_path)


def repair(db_path=None, connection=None):
    from psx_app.database.schema import get_connection
    from psx_app.parsers.tradelog_parser import compute_execution_charges
    now = datetime.now(timezone.utc).isoformat()
    with (connection if connection is not None else get_connection(db_path)) as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT 1 FROM app_settings WHERE key=?', (_MARKER,)).fetchone():
            return True
        rows = [dict(r) for r in c.execute("SELECT * FROM trade_executions WHERE account_id IN ('91404','91269') ORDER BY id").fetchall()]
        summaries = [dict(r) for r in c.execute("SELECT * FROM account_daily_symbol_summary WHERE account_id IN ('91404','91269')").fetchall()]
        if not rows and not summaries:
            c.rollback()
            return False
        groups = defaultdict(list)
        for r in rows:
            groups[(r['account_id'], r['trade_date'], r['symbol'])].append(r)
        indexed = {(r['account_id'], r['trade_date'], r['symbol']):r for r in summaries}
        revisions, updates, summary_updates, warnings = [], [], [], []
        d = lambda x: Decimal(str(x))
        near = lambda a,b: abs(d(a)-d(b)) <= Decimal('0.00001')
        for key, trades in groups.items():
            summary = indexed.get(key)
            reason = None
            if not summary:
                reason = 'No matching account summary; original charges retained.'
            else:
                for side, prefix in [('BUY','buy'), ('SELL','sell')]:
                    selected = [r for r in trades if r['normalized_side'] == side]
                    if sum(r['quantity'] for r in selected) != summary[prefix+'_qty'] or not near(sum((d(r['trade_value']) for r in selected),Decimal(0)),summary[prefix+'_value']):
                        reason = 'Execution records do not fully match the original summary; retained for review.'; break
                if any(r['normalized_side'] not in ('BUY','SELL') for r in trades):
                    reason = 'Unknown transaction side; retained for review.'
                for column in ('commission_amount','sst_amount','total_charges'):
                    if not near(sum((d(r[column]) for r in trades),Decimal(0)),summary[column]):
                        reason = 'Execution charges do not match the summary; retained for review.'
            changed = []
            if not reason:
                for r in trades:
                    try:
                        old_comm, old_sst, old_total = d(r['commission_amount']),d(r['sst_amount']),d(r['total_charges'])
                        if not near(old_total,old_comm+old_sst):
                            reason = 'Additional or inconsistent charges; retained for review.'; break
                        if r['normalized_side'] == 'BUY':
                            if old_comm != 0 or old_sst != 0:
                                reason = 'Unexpected buy charges; retained for review.'; break
                            new = compute_execution_charges('BUY',r['quantity'],r['price'],r['trade_value'])
                        else:
                            if old_comm <= 0 or old_sst < 0:
                                reason = 'Original historical SST rate cannot be verified; retained for review.'; break
                            rate = old_sst / old_comm
                            if not Decimal(0) <= rate <= Decimal(1):
                                reason = 'Original historical SST rate cannot be verified; retained for review.'; break
                            new = compute_execution_charges('SELL',r['quantity'],r['price'],r['trade_value'], {'sst_rate': str(rate)})
                        changed.append((r,new))
                    except (InvalidOperation, TypeError, ValueError, ZeroDivisionError):
                        reason = 'Invalid trade or tax data; retained for review.'; break
            if reason:
                warnings.append((key,reason)); continue
            sell = [new for old,new in changed if old['normalized_side']=='SELL']
            comm = sum((d(x['commission_amount']) for x in sell),Decimal(0))
            sst = sum((d(x['sst_amount']) for x in sell),Decimal(0))
            total=comm+sst
            net=d(summary['gross_pnl'])-total
            labels={x['commission_slab'] for x in sell}
            label=next(iter(labels)) if len(labels)==1 else ('Mixed slabs (execution-level)' if labels else '—')
            result={**summary,'commission_slab_label':label,'commission_amount':float(comm),'sst_amount':float(sst),'total_charges':float(total),'net_pnl':float(net),'return_on_buy':float(net/d(summary['buy_value'])) if d(summary['buy_value'])>0 else None,'origin_type':'RAW_EXECUTIONS','updated_at':now}
            for old,new in changed:
                if all(old[k]==new[k] for k in ('commission_slab','commission_amount','sst_amount','total_charges')): continue
                revisions.append(('trade_executions',str(old['id']),json.dumps(old),json.dumps(new),'Commission repair: PKR per share',now))
                updates.append((new['commission_slab'],new['commission_amount'],new['sst_amount'],new['total_charges'],old['id']))
            if any(summary[k]!=result[k] for k in ('commission_slab_label','commission_amount','sst_amount','total_charges','net_pnl','return_on_buy','origin_type')):
                revisions.append(('account_daily_symbol_summary',str(summary['id']),json.dumps(summary),json.dumps(result),'Commission repair: verified execution group',now))
                summary_updates.append((label,float(comm),float(sst),float(total),float(net),result['return_on_buy'],result['origin_type'],now,summary['id']))
        c.executemany('INSERT INTO source_revisions (table_name,business_key,old_value_json,new_value_json,reason,recorded_at) VALUES (?,?,?,?,?,?)',revisions)
        c.executemany('UPDATE trade_executions SET commission_slab=?,commission_amount=?,sst_amount=?,total_charges=? WHERE id=?',updates)
        c.executemany('UPDATE account_daily_symbol_summary SET commission_slab_label=?,commission_amount=?,sst_amount=?,total_charges=?,net_pnl=?,return_on_buy=?,origin_type=?,updated_at=? WHERE id=?',summary_updates)
        c.executemany("INSERT INTO import_issues (module,severity,issue_type,account_id,trade_date,symbol,message,created_at) VALUES ('MODULE_B','WARNING','COMMISSION_REPAIR_REVIEW',?,?,?,?,?)",[(k[0],k[1],k[2],reason,now) for k,reason in warnings])
        c.execute('INSERT INTO app_settings (key,value_json,description,version,updated_at) VALUES (?,?,?,?,?)',(_MARKER,json.dumps({'executions':len(updates),'summaries':len(summary_updates),'review_groups':len(warnings)}),'One-time automatic commission repair',1,now))
        c.execute("INSERT INTO audit_events (event_type,actor,details_json,created_at) VALUES ('COMMISSION_REPAIR','system',?,?)",(json.dumps({'executions':len(updates),'summaries':len(summary_updates),'review_groups':len(warnings)}),now))
        c.commit()
        return True
