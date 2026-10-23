"""Shared, deterministic execution-plan checks. No fitted probabilities or invented targets."""
import math


def build_trade_plan(bar, pivots, side, min_rr=1.5, entry=None):
    entry = round(float(bar['close'] if entry is None else entry), 2)
    out = {'status':'NO TRADE', 'side':side, 'entry':entry, 'stop':None,
           'target_1':None, 'target_2':None, 'risk_reward':None, 'risk_per_share':None,
           'min_risk_reward':min_rr, 'reason':'No opening-trade signal. SELL means reduce an existing holding, not open a short.',
           'execution_note':'EOD analytical reference; no guaranteed fill. Recheck next-session price, costs, liquidity and eligibility.'}
    if side not in ('LONG','SHORT'):
        return out
    if 'volume' in bar and float(bar.get('volume') or 0) <= 0:
        out['reason']='Latest imported session has no positive reported volume.'
        return out
    ema = bar.get('ema21')
    if ema is None or not math.isfinite(entry) or entry <= 0:
        out['reason']='Insufficient valid data for an entry/stop plan.'
        return out
    if side == 'LONG':
        stop = round(min(float(pivots['S1']), float(ema)), 2)
        targets = sorted({round(float(pivots[k]),2) for k in ('R1','R2','R3') if float(pivots[k]) > entry})
        valid = 0 < stop < entry
    else:
        stop = round(max(float(pivots['R1']), float(ema)), 2)
        targets = sorted({round(float(pivots[k]),2) for k in ('S1','S2','S3') if 0 < float(pivots[k]) < entry}, reverse=True)
        valid = 0 < entry < stop
    targets = [t for t in targets if t > entry] if side == 'LONG' else [t for t in targets if 0 < t < entry]
    out.update(stop=stop, target_1=targets[0] if targets else None,
               target_2=targets[1] if len(targets)>1 else (targets[0] if targets else None))
    if not valid or not targets:
        out['reason']='Invalid entry/stop/structural-target direction; no fabricated target was substituted.'
        return out
    risk=abs(entry-stop);rr=abs(targets[0]-entry)/risk
    out.update(risk_per_share=round(risk,4),risk_reward=round(rr,4))
    if rr < min_rr:
        out['reason']=f'Structural target offers {rr:.2f}:1 before costs, below the {min_rr:.2f}:1 minimum.'
        return out
    out.update(status='VALID',reason='Directional levels valid; minimum gross reward/risk met. Not a probability or execution approval.')
    return out


def annotate_freshness(item, market_date):
    stale=bool(market_date and item['latest_date'] < market_date)
    item['data_freshness']={'market_latest_date':market_date, 'symbol_latest_date':item['latest_date'],
                            'status':'STALE' if stale else 'CURRENT',
                            'note':'Current means matches the newest imported cash session, not a live exchange feed.'}
    if stale:
        # Preserve the raw historical signal but block opening a trade from stale data.
        sig=item.get('signal',{})
        if sig.get('trade_plan'):
            sig['trade_plan']['status']='NO TRADE'
            sig['trade_plan']['reason']='Symbol is older than the latest imported market session.'
    return item
