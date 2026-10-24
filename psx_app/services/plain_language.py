"""Presentation only: never changes signal rules, trade validity or saved forecasts."""
import math


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def money(value):
    return f'{value:,.2f} PKR' if number(value) else 'Not set'


def simple_reason(reason):
    text = reason or ''
    if 'Stale' in text or 'stale' in text:
        return 'The latest price for this stock is older than the latest imported market day. Wait for fresh data.'
    if 'No opening-trade signal' in text:
        return 'There is no new buy or short entry. A sell warning means review shares you already own; it is not permission to open a short.'
    if 'Structural target offers' in text:
        return 'The possible gain to the price target is too small compared with the possible loss to the stop. Wait for a better entry; do not force a trade.'
    if 'Invalid entry/stop' in text:
        return 'The price, loss limit and target do not form a usable trade. Wait; no substitute target has been invented.'
    if 'costs consume' in text:
        return 'Estimated fees and price slippage leave too little potential gain. Do not enter.'
    return text or 'Wait: a usable trade has not been confirmed.'


def analysis_guide(latest, contract, analysis=None):
    a = analysis or {}; p = contract; lat = latest or {}; sig = lat.get('signal') or {}
    valid = p.get('status') == 'CONDITIONAL'
    side = p.get('side'); raw = sig.get('combined_signal', 'No signal')
    close = lat.get('close'); score = sig.get('score'); ws = a.get('weekly_summary') or {}
    def rule_valid():
        return valid and side in ('LONG', 'SHORT') and all(number(p.get(k)) for k in ('entry_low','entry_high','stop','target_1'))
    valid = rule_valid()
    timing = ('At the next trading day’s opening price only, between '
              f"{money(p.get('entry_low'))} and {money(p.get('entry_high'))}. "
              'Skip if the opening price is outside this range. Recheck that potential gain is at least 1.5 times the loss risk and remains positive after costs.')
    wait_reason = simple_reason(p.get('reason'))
    buy = timing if valid and side == 'LONG' else 'Do not open a new buy now. ' + (wait_reason if not valid else 'The current setup is for a possible short, not a buy.')
    short = (timing + ' Only if your broker confirms that shorting this instrument is permitted and executable.') if valid and side == 'SHORT' else 'Do not open a short now. ' + (wait_reason if not valid else 'The current setup is a buy, not a short.')
    unsafe = lat.get('data_freshness', {}).get('status') == 'STALE' or not number(lat.get('volume')) or lat.get('volume',0) <= 0 or sig.get('combined_signal') == 'INSUFFICIENT DATA'
    if unsafe:
        valid = False; buy = short = 'Wait for current, usable price and volume data. No new trade is supported.'
    owned = ('Price indicators are weak: review reducing shares you already own at the next tradable session; do not treat this as a short entry. An executable sell price is not known from daily history.'
             if raw in ('SELL','SHORT SELL') and not unsafe else
             'No rule-based sell warning for existing holdings.' if raw == 'BUY' and not unsafe else
             'Review existing holdings; there is no clear new action. Your purchase price and risk limits are not supplied.')
    action = ('CONDITIONAL BUY' if side == 'LONG' else 'CONDITIONAL SHORT — permission required') if valid else 'WAIT — NO NEW TRADE'
    target = (f"First take-profit price: {money(p.get('target_1'))}. " +
              (f"Second reference target: {money(p.get('target_2'))}; the saved simulation exits at the first target, not this second level. " if number(p.get('target_2')) else '') +
              'For the up-to-10-record simulation, close at the first target, loss limit, or the 10th trading record’s close, whichever happens first. Actual fills are not guaranteed.') if valid else 'No new-trade profit target is active because there is no valid entry. A personal profit-taking price needs your purchase price and position details.'
    stop = (f"Loss limit: {money(p.get('stop'))}. " + ('Exit the buy if price falls to this level.' if side=='LONG' else 'Buy back the short if price rises to this level.') + ' A gap may cause a worse fill.') if valid else 'No new-trade stop is active because there is no valid entry. This does not mean an existing holding has no downside risk.'
    support=[];resistance=[]
    dp=(lat.get('daily_pivots') or {}).get('classic') or {}; kl=a.get('key_levels') or {}
    for value in [*dp.values(),kl.get('swing_high_20d'),kl.get('swing_low_20d')]:
        if number(value) and number(close):
            if value<close:support.append(value)
            if value>close:resistance.append(value)
    support=max(support) if support else None; resistance=min(resistance) if resistance else None
    day = lat.get('change_pct'); week=ws.get('change_4w_pct'); slope=(a.get('trend_line') or {}).get('slope_pkr_per_day')
    trend = f"The latest closing price is {money(close)}. "
    trend += f"It {'rose' if day>0 else 'fell' if day<0 else 'was unchanged'} by {abs(day):.2f}% on the latest stored trading day. " if number(day) else 'A prior closing price is needed to calculate the daily change. '
    trend += (f"Over the last four completed weeks, the closing price {'rose' if week>0 else 'fell' if week<0 else 'was unchanged'} by {abs(week):.2f}%. " if number(week) else 'There are not enough completed weeks for a four-week comparison. ')
    levels = ((f"The nearest calculated price floor below the close is {money(support)}. " if support is not None else 'No calculated floor below the close is available. ') +
              (f"The nearest calculated ceiling above the close is {money(resistance)}. " if resistance is not None else 'No calculated ceiling above the close is available. ') +
              'These are watch levels, not guaranteed turning points or entry instructions. ')
    if number(slope): levels += f"The last 20 recorded prices show a {'downward' if slope<0 else 'upward' if slope>0 else 'flat'} fitted trend."
    mas=[lat.get(k) for k in ('ema9','ema21','ema50','ema200','sma20','sma50')];available=[x for x in mas if number(x)]
    above=sum(close>x for x in available) if number(close) else 0
    averages=(f"The price is above {above} of {len(available)} available price averages. " + ('Most comparisons favour buyers.' if above>len(available)/2 else 'Most comparisons do not favour a new buy.') if available else 'There is not enough history to calculate price averages.')
    rsi=lat.get('rsi14');hist=lat.get('macd_hist')
    momentum=(('Recent buying pressure is unusually strong.' if rsi>=70 else 'Recent selling pressure is unusually strong; that alone does not mean the price will recover.' if rsi<=30 else 'Recent buying and selling pressure is between the usual extremes.') if number(rsi) else 'Buying/selling pressure cannot yet be calculated.')
    if number(hist):momentum+=' Short-term momentum is '+('stronger' if hist>0 else 'weaker' if hist<0 else 'unchanged')+' relative to its slower signal.'
    return {'action':action,'reason':wait_reason if not valid else 'A conditional price plan passes the current rules; it is not a guarantee.',
            'as_of':lat.get('latest_date'),'buy':buy,'sell_existing':owned,'short':short,'take_profit':target,'stop_loss':stop,
            'when_not_to_buy':'Do not buy while this page says WAIT, when the plan is for a short, when data are old or volume is zero, or when the next opening price fails the entry range or reward-versus-loss checks.',
            'steps':[{'title':'1. What the price is doing','detail':trend},{'title':'2. Prices to watch','detail':levels},
                     {'title':'3. Is the price stronger than its recent averages?','detail':averages},
                     {'title':'4. Are buyers or sellers gaining strength?','detail':momentum}],
            'score':score,'score_explanation':'The rule score adds bullish (+1), bearish (-1) and neutral (0) indicator votes. Positive favours rising prices; negative favours falling prices. Correlated indicators are not independent evidence. It is not a win percentage, and it does not override the entry safety checks.',
            'history':{'records':lat.get('bars_count'),'starts':lat.get('first_date'),'ends':lat.get('latest_date')},
            'levels_active':valid,'support_watch':support,'resistance_watch':resistance}


def forecast_display(outcome):
    status=outcome.get('status','PENDING')
    labels={'PENDING':'Waiting for later market data','OPEN':'Simulated trade still open','NO_TRADE':'No trade recommended',
            'NOT_TRIGGERED':'Entry conditions not met','AMBIGUOUS':'Cannot tell which level was hit first',
            'INSUFFICIENT_DATA':'Matching price data missing','STOP_REACHED':'Loss limit reached',
            'TARGET_REACHED':'Profit target reached','HORIZON_CLOSED':'Time limit reached — simulated trade closed'}
    reasons={'PENDING':'Not calculated yet — waiting for later price records.', 'OPEN':'Not final — the simulated position is still open.',
             'NO_TRADE':'Not applicable — no trade was recommended.', 'NOT_TRIGGERED':'Not applicable — no simulated entry occurred.',
             'AMBIGUOUS':'Unknown — daily prices cannot show whether the loss limit or target was reached first.',
             'INSUFFICIENT_DATA':'Cannot calculate — a required price record is missing.'}
    value=outcome.get('net_return_pct')
    # Only closed simulations can show a realised percentage, never zero-fill missing data.
    closed=status in ('STOP_REACHED','TARGET_REACHED','HORIZON_CLOSED')
    return {'status_label':labels.get(status,status.replace('_',' ').title()),'return_value':value if closed and number(value) else None,
            'return_note':reasons.get(status,'Cannot calculate — a closed simulated return is unavailable.')}
