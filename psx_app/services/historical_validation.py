"""Bounded, chronological, long-only rule audit. Not an optimized or trained prediction model."""
from datetime import date
from psx_app.database.schema import get_connection
from psx_app.services.technical_service import TechnicalService, ENGINE_VERSION
from psx_app.services.signal_reliability import build_trade_plan


def validate_bars(symbol, bars, settings, start=None, end=None, horizon=10, fees_bps=10.0, slippage_bps=10.0, min_rr=1.5):
    if not 1 <= horizon <= 60 or not 0 <= fees_bps <= 200 or not 0 <= slippage_bps <= 200 or not 0 <= min_rr <= 10:
        raise ValueError('Invalid validation settings.')
    for value in (start, end):
        if value:
            date.fromisoformat(value)
    if start and end and start > end:
        raise ValueError('Start date must not exceed end date.')
    # End-date filtering precedes calculation; older bars warm up indicators without future data.
    bars=[dict(b) for b in bars if not end or b['trade_date'] <= end]
    if any(bars[i]['trade_date'] >= bars[i+1]['trade_date'] for i in range(len(bars)-1)):
        raise ValueError('Bars must have unique ascending trading dates.')
    if len(bars) > 6000:
        raise ValueError('Single-symbol validation supports up to 6,000 sessions. Use a bounded offline study for larger datasets.')
    calc=TechnicalService().calculate_series_for_bars(symbol,bars,settings=settings,is_futures_eligible=False)
    series=calc.get('series',[]); trades=[]; rejected=0; unresolved=0; i=25; curve=1.0; peak=1.0; drawdown=0.0
    fee=fees_bps/10000; slip=slippage_bps/10000
    while i+1 < len(series):
        signal=series[i]
        if (start and signal['trade_date'] < start) or signal['action'] != 'BUY':
            i+=1;continue
        piv=TechnicalService.compute_classic_fib_camarilla_pivots(signal['high'],signal['low'],signal['close'])['classic']
        plan=build_trade_plan(signal,piv,'LONG',min_rr=min_rr)
        if plan['status'] != 'VALID':
            rejected+=1;i+=1;continue
        next_bar=series[i+1]
        if next_bar['volume'] <= 0 or next_bar['open'] <= 0:
            rejected+=1;i+=1;continue
        entry=next_bar['open']*(1+slip);stop=plan['stop'];target=plan['target_1']
        # Do not recalculate structural targets using future prices or invent a target to rescue a gap.
        if not 0 < stop < entry < target or (target-entry)/(entry-stop) < min_rr:
            rejected+=1;i+=1;continue
        j=i+1;last=min(i+horizon,len(series)-1)
        exit_price=None;reason=None; ambiguous=False
        while j<=last:
            b=series[j]
            if b['volume'] <= 0:
                j+=1;continue
            if b['open'] <= stop:
                exit_price=b['open'];reason='GAP_STOP'
            elif b['low'] <= stop:
                exit_price=stop;reason='STOP';ambiguous=b['high']>=target
            elif b['open'] >= target:
                # Conservative limit fill: do not credit a favorable opening gap beyond the target.
                exit_price=target;reason='TARGET'
            elif b['high'] >= target:
                exit_price=target;reason='TARGET'
            elif j==last:
                exit_price=b['close'];reason='TIME_EXIT'
            if exit_price is not None:break
            j+=1
        if exit_price is None or (j==len(series)-1 and reason=='TIME_EXIT' and i+horizon >= len(series)):
            # Omit unresolved end-of-sample positions; do not pretend their time horizon elapsed.
            unresolved+=1;i=last+1;continue
        received=exit_price*(1-slip)
        net=(received*(1-fee))/(entry*(1+fee))-1
        curve*=1+net;peak=max(peak,curve);drawdown=max(drawdown,(peak-curve)/peak)
        trades.append({'signal_date':signal['trade_date'],'entry_date':next_bar['trade_date'],'exit_date':series[j]['trade_date'],
                       'entry':round(entry,4),'stop':stop,'target':target,'exit':round(received,4),
                       'net_return_pct':net*100,'exit_reason':reason,'ambiguous_stop_target_bar':ambiguous})
        i=j+1  # One position at a time; signal may next be formed after this exit.
    wins=sum(t['net_return_pct']>0 for t in trades)
    groups={}
    for t in trades:
        y=t['entry_date'][:4];g=groups.setdefault(y,{'year':y,'trades':0,'net_sum_pct':0.0,'wins':0})
        g['trades']+=1;g['net_sum_pct']+=t['net_return_pct'];g['wins']+=t['net_return_pct']>0
    return {'engine_version':ENGINE_VERSION,'symbol':symbol,'status':'COMPLETED' if trades else 'NO QUALIFYING CLOSED TRADES',
            'rule_settings':{k:settings.get(k) for k in ('rsi_period','macd_fast','macd_slow','macd_signal','bb_period','bb_std','adx_period','strict_indicator_sufficiency','signal_buy_threshold','signal_sell_threshold','rule_version')},
            'method':'Chronological fixed-rule long-only audit; not parameter optimization, walk-forward fitting, or a profit forecast.',
            'coverage':{'history_start':bars[0]['trade_date'] if bars else None,'history_end':bars[-1]['trade_date'] if bars else None,'sessions':len(bars),'evaluation_start':start,'evaluation_end':end},
            'assumptions':{'horizon_sessions':horizon,'fees_bps_each_side':fees_bps,'slippage_bps_each_side':slippage_bps,'minimum_gross_rr':min_rr,
                           'entry':'Next session open plus adverse slippage; must remain below structural target and above stop.',
                           'ambiguity':'Stop first when both stop and target occur in a daily bar. Stop gaps fill at the opening price.',
                           'position':'One hypothetical fully allocated position per symbol at a time; no leverage or portfolio simulation.'},
            'limitations':['Unverified raw corporate-action adjustment status.','Fee inputs are illustrative all-in assumptions, not a verified broker/tax schedule.',
                           'Daily OHLCV cannot establish intraday ordering, market depth, price-lock fills or actual executable capacity.',
                           'Drawdown is measured at trade closes, not mark-to-market; intratrade losses can be worse.',
                           'No survivorship-free historical universe, out-of-sample model selection or calibrated win probability is claimed.',
                           'Unresolved end-of-sample trades are excluded; periods with no trades are not evidence of profitability.'],
            'summary':{'closed_trades':len(trades),'rejected_candidates':rejected,'unresolved_positions_excluded':unresolved,'sample_warning':'Fewer than 30 closed trades; do not infer a reliable edge.' if len(trades)<30 else 'Historical results are descriptive, not a prediction.', 'wins':wins,'win_rate_pct':wins/len(trades)*100 if trades else None,
                       'mean_net_return_pct':sum(t['net_return_pct'] for t in trades)/len(trades) if trades else None,
                       'compounded_trade_return_pct':(curve-1)*100 if trades else None,'trade_close_drawdown_pct':drawdown*100 if trades else None},
            'yearly':list(groups.values()),'trades':trades}


class HistoricalValidationService:
    def __init__(self,db_path=None):self.db_path=db_path
    def run(self,symbol,**kwargs):
        from psx_app.database.repository import Repository
        symbol=TechnicalService.resolve_ticker(symbol)
        with get_connection(self.db_path) as c:
            rows=c.execute('SELECT trade_date,open,high,low,close,pr_close,volume FROM equity_ohlcv WHERE symbol=? ORDER BY trade_date ASC LIMIT 6001',(symbol,)).fetchall()
        return validate_bars(symbol,[dict(r) for r in rows],Repository(self.db_path).get_settings(),**kwargs)
