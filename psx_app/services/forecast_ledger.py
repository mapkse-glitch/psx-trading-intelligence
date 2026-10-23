"""Immutable as-of forecasts; conservative daily-bar reconciliation, no hindsight edits."""
import json,hashlib
from datetime import datetime,timezone
from psx_app.database.schema import get_connection
from psx_app.services.technical_service import TechnicalService

VERSION='1.3.9-rules-1'
COST=.001  # 10 bps fee per side; illustrative, not broker verified
SLIP=.001


def execution_contract(latest):
    p=dict(latest.get('signal',{}).get('trade_plan') or {})
    entry=p.get('entry'); side=p.get('side')
    valid=p.get('status')=='VALID' and side in ('LONG','SHORT')
    lower=round(entry*.9975,4) if entry else None; upper=round(entry*1.0025,4) if entry else None
    reason=p.get('reason','No valid structural setup.')
    if latest.get('data_freshness',{}).get('status')=='STALE': valid=False;reason='Stale symbol data.'
    risk=abs(entry-p['stop']) if valid else None
    net_rr=(abs(p['target_1']-entry)-entry*2*(COST+SLIP))/(risk+entry*2*(COST+SLIP)) if valid and risk else None
    if valid and (net_rr is None or net_rr<=0): valid=False;reason='Assumed costs consume the target reward.'
    return {'status':'CONDITIONAL' if valid else 'NO TRADE','side':side,'reference_entry':entry,'entry_low':lower,'entry_high':upper,'stop':p.get('stop'),'target_1':p.get('target_1'),'target_2':p.get('target_2'),'gross_rr':p.get('risk_reward'),'net_rr':net_rr,'reason':reason,'entry_rule':'Next imported market session OPEN only, within +/-0.25% of reference; no later intraday entry or chasing. Recheck reward/risk at actual assumed fill.','expiry':'Entry expires after the next market session. Swing exits at T1, stop, or 10th session close.','avoid':['Do not enter outside the entry band or through the stop/target.','Do not trade stale/missing or zero-volume data.','Require actual-fill gross R/R >= 1.5 and positive reward after assumed costs.','Short entries require independently confirmed broker permission and an executable instrument; cash OHLC is only a hypothetical reference.'],'fee_each_side_bps':10,'slippage_each_side_bps':10,'fundamentals':'Unavailable: no verified financial statements or current news source supplied.'}


def evaluate(payload, bars, market_dates):
    """Evaluate only dates AFTER immutable cutoff; never infer intraday ordering."""
    future=[d for d in market_dates if d>payload['as_of']]
    if not future: return {'status':'PENDING','explanation':'Awaiting next imported market session.'}
    mapping={r['trade_date']:r for r in bars}; first=mapping.get(future[0])
    if not first: return {'status':'INSUFFICIENT_DATA','explanation':'Next market session has no matching symbol bar; no substituted entry date.'}
    close=first.get('close');ref=payload['reference_close'];score=payload['score']
    actual= None if close is None else close-ref
    direction='NEUTRAL' if score==0 else ('UP' if score>0 else 'DOWN')
    directional=('UNSCORED_NEUTRAL' if not score else ('CORRECT' if actual is not None and actual*score>0 else ('FLAT' if actual==0 else ('WRONG' if actual is not None else 'INSUFFICIENT_DATA'))))
    out={'next_session':future[0],'expected_direction':direction,'next_close_change':actual,'directional_result':directional}
    p=payload['contract']
    if p['status']!='CONDITIONAL': return {**out,'status':'NO_TRADE','explanation':'No entry was recommended. Directional result is separate from trade performance.'}
    entry=first.get('open');side=p['side'];sign=1 if side=='LONG' else -1
    if entry is None or entry<=0 or not first.get('volume') or not (p['entry_low']<=entry<=p['entry_high']):
        return {**out,'status':'NOT_TRIGGERED','explanation':'Next-session open was missing, illiquid, or outside the recorded entry band.'}
    fill=entry*(1+sign*SLIP);stop=p['stop'];target=p['target_1']
    risk=(fill-stop)*sign; reward=(target-fill)*sign
    if risk<=0 or reward<=0 or reward/risk<1.5 or reward-fill*2*COST<=0:
        return {**out,'status':'NOT_TRIGGERED','explanation':'Gap/slippage invalidated the actual-fill direction, gross R/R or cost safeguard.'}
    horizon=payload['horizon']; dates=future[:horizon]
    out.update(entry_date=first['trade_date'],assumed_fill=fill,execution='Hypothetical daily-OHLC simulation, not broker fills.')
    def closed(status,price,dt,explanation):
        exit_fill=price*(1-sign*SLIP)
        net=(exit_fill-fill)*sign-COST*(fill+exit_fill)
        return {**out,'status':status,'exit_date':dt,'assumed_exit':exit_fill,'net_return_pct':net/fill*100,'explanation':explanation}
    for i,d in enumerate(dates):
        b=mapping.get(d)
        if not b or any(b.get(k) is None for k in ('open','high','low','close')):
            return {**out,'status':'INSUFFICIENT_DATA','explanation':'Missing session/OHLC inside the evaluation horizon.'}
        o,h,l=b['open'],b['high'],b['low']
        if i and (o-stop)*sign<=0: return closed('STOP_REACHED',o,d,'Opened beyond stop; adverse gap priced at open.')
        if i and (o-target)*sign>=0: return closed('TARGET_REACHED',target,d,'Opened beyond target; capped at recorded target, no favourable gap windfall.')
        stop_hit=l<=stop if sign==1 else h>=stop
        target_hit=h>=target if sign==1 else l<=target
        if stop_hit and target_hit: return {**out,'status':'AMBIGUOUS','exit_date':d,'explanation':'Stop and target both inside daily range; intraday sequence unknown. No win or profit credited.'}
        if stop_hit:return closed('STOP_REACHED',stop,d,'Observed range crossed the recorded stop; not an explanation of market cause.')
        if target_hit:return closed('TARGET_REACHED',target,d,'Observed range crossed T1 without crossing stop in an earlier evaluated bar.')
    if len(future)>=horizon:return closed('HORIZON_CLOSED',mapping[dates[-1]]['close'],dates[-1],'Horizon ended without stop or T1. Net result includes illustrative costs.')
    return {**out,'status':'OPEN','explanation':'Triggered; swing horizon still running.'}


class ForecastLedger:
    def __init__(self, db_path=None):self.db_path=db_path
    def record(self,symbol):
        result=TechnicalService(self.db_path).get_ticker_analysis(symbol,tail_bars=1)
        latest=result.get('latest')
        if not latest:raise ValueError('No symbol data to record.')
        if latest.get('data_freshness',{}).get('status')=='STALE':raise ValueError('Stale symbol: forecasts cannot be recorded as current.')
        with get_connection(self.db_path) as c:
            rule=c.execute("SELECT value_json FROM app_settings WHERE key='rule_version'").fetchone()
            version=VERSION+'-cfg'+str(rule[0] if rule else '1')
            for horizon in (1,10):
                payload={'symbol':latest['symbol'],'as_of':latest['latest_date'],'reference_close':latest['close'],'score':latest['signal']['score'],'horizon':horizon,'version':version,'contract':execution_contract(latest),'history':{'first':latest['first_date'],'sessions':latest['bars_count']},'origin':'FORWARD_RECORDED','recorded_at':datetime.now(timezone.utc).isoformat()}
                key=hashlib.sha256(f"{payload['symbol']}:{payload['as_of']}:{horizon}:{version}".encode()).hexdigest()
                c.execute('INSERT OR IGNORE INTO forecast_ledger(forecast_id,symbol,as_of,horizon,version,payload_json,created_at) VALUES (?,?,?,?,?,?,?)',(key,payload['symbol'],payload['as_of'],horizon,version,json.dumps(payload),payload['recorded_at']))
            c.commit()
        return {'status':'RECORDED','symbol':latest['symbol'],'as_of':latest['latest_date'],'note':'Idempotent snapshot; original forecast cannot be overwritten. Not a historical backtest.'}
    def reconcile(self,limit=100):
        with get_connection(self.db_path) as c:
            # Re-evaluate if imported source revision changes, but preserve all previous outcome observations.
            revision=c.execute('SELECT MAX(id),COUNT(*) FROM import_batches WHERE status=\'COMMITTED\'').fetchone()
            rev=str(tuple(revision))
            rows=c.execute('SELECT * FROM forecast_ledger WHERE evaluated_revision IS NULL OR evaluated_revision!=? ORDER BY last_checked,as_of,forecast_id LIMIT ?',(rev,limit)).fetchall()
            dates=[r[0] for r in c.execute('SELECT DISTINCT trade_date FROM equity_ohlcv ORDER BY trade_date')]
            updated=0
            for r in rows:
                payload=json.loads(r['payload_json'])
                bars=[dict(b) for b in c.execute('SELECT trade_date,open,high,low,close,volume FROM equity_ohlcv WHERE symbol=? AND trade_date>? ORDER BY trade_date LIMIT 10',(r['symbol'],r['as_of']))]
                outcome=evaluate(payload,bars,dates)
                encoded=json.dumps(outcome,sort_keys=True);digest=hashlib.sha256(encoded.encode()).hexdigest()
                c.execute('INSERT OR IGNORE INTO forecast_observations(forecast_id,digest,outcome_json,created_at) VALUES (?,?,?,?)',(r['forecast_id'],digest,encoded,datetime.now(timezone.utc).isoformat()))
                # Pending/open forecasts are eligible again without waiting for a new batch identifier.
                marker=None if outcome['status'] in ('PENDING','OPEN','INSUFFICIENT_DATA') else rev
                c.execute('UPDATE forecast_ledger SET outcome_json=?,evaluated_revision=?,last_checked=? WHERE forecast_id=?',(encoded,marker,datetime.now(timezone.utc).isoformat(),r['forecast_id']))
                updated+=1
            c.commit()
        return {'evaluated':updated,'limit':limit,'note':'Reconciliation is bounded; use Evaluate saved forecasts again for additional pending records.'}
    def list(self):
        with get_connection(self.db_path) as c:
            rows=[dict(r) for r in c.execute('SELECT * FROM forecast_ledger ORDER BY as_of DESC,created_at DESC LIMIT 200')]
        return {'items':[{'id':r['forecast_id'],**json.loads(r['payload_json']),'outcome':json.loads(r['outcome_json'] or '{"status":"PENDING"}')} for r in rows],'note':'Forward-recorded snapshots only. Creation timestamp proves when recorded, not exchange-time data availability. Outcome observations are retained separately when source data changes.'}
