"""Daily imported cash-market summary; no assumed exchange circuit breakers."""
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import math,re
from psx_app.database.schema import get_connection
from psx_app.services.result_cache import persisted_result


def finite(value):
    try:
        n=float(value)
        return n if math.isfinite(n) else None
    except (TypeError,ValueError,OverflowError): return None


def movement(current,previous,*,positive_previous=True):
    current,previous=finite(current),finite(previous)
    if current is None or previous is None or (positive_previous and previous<=0): return None,None
    diff=current-previous
    if not math.isfinite(diff):return None,None
    pct=diff/previous*100 if previous>0 else None
    return diff,(pct if pct is None or math.isfinite(pct) else None)


def official_limit_flags(row,upper,lower):
    """Apply supplied verified limits only. Missing observations stay unknown."""
    def num(value):
        try:
            d=Decimal(str(value));return d if d.is_finite() and d>=0 else None
        except (InvalidOperation,ValueError,TypeError): return None
    upper,lower=num(upper),num(lower);high,low,close=(num(row.get(k)) for k in ('high','low','close'))
    if upper is not None and lower is not None and upper<=lower:return {'upper_touch':None,'upper_close':None,'lower_touch':None,'lower_close':None,'status':'UNAVAILABLE'}
    noise=Decimal('0.00000001')
    flags={'upper_touch':high>=upper-noise if upper is not None and high is not None else None,
           'upper_close':abs(close-upper)<=noise if upper is not None and close is not None else None,
           'lower_touch':low<=lower+noise if lower is not None and low is not None else None,
           'lower_close':abs(close-lower)<=noise if lower is not None and close is not None else None}
    # Never label unknown data Normal, and don't silently classify impossible close values.
    if upper is None or lower is None or close is None or close>upper+noise or close<lower-noise: status='UNAVAILABLE'
    elif flags['upper_close']: status='UPPER'
    elif flags['lower_close']: status='LOWER'
    else: status='NORMAL'
    flags['status']=status;return flags


def standard_band(selected, reference):
    """Estimated standard ready-market band; exceptions require exchange data.

    2024 phase-in: PSX/N-477; earlier 7.5% from PSX 2021 rule text.
    Earlier schedules are deliberately not assumed. The application does not
    store security-specific exceptions or authoritative daily band values.
    """
    phases=(('2024-07-22','0.10'),('2024-07-08','0.095'),('2024-06-24','0.09'),('2024-06-10','0.085'),('2024-05-27','0.08'),('2021-01-27','0.075'))
    rate=next((Decimal(x) for day,x in phases if selected>=day),None)
    try:
        ref=Decimal(str(reference))
        if rate is None or not ref.is_finite() or ref<=0:return None
        shift=max(ref*rate,Decimal('1'))
        upper=(ref+shift).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        lower=(ref-shift).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        if lower<=0 or upper<=lower:return None
        return upper,lower
    except (InvalidOperation,ValueError,TypeError):return None


def estimated_limit_flags(row,selected,reference):
    band=standard_band(selected,reference)
    if not band:return official_limit_flags(row,None,None)
    upper,lower=band
    # An observed price outside the assumed band indicates a potential
    # exception, bad data, or an adjusted reference. Do not classify it.
    for k in ('high','low','close'):
        v=finite(row.get(k))
        if v is not None and (Decimal(str(v)) > upper+Decimal('0.00000001') or Decimal(str(v)) < lower-Decimal('0.00000001')):
            return official_limit_flags(row,None,None)
    return official_limit_flags(row,upper,lower)


class DailySummary:
    def __init__(self,db_path=None):self.db_path=db_path

    def report(self,selected=None):
        return self.report_v1332(selected)

    @persisted_result
    def report_v1332(self,selected=None):
        if selected is not None:
            try:
                if len(selected)!=10 or date.fromisoformat(selected).isoformat()!=selected:raise ValueError()
            except (ValueError,TypeError):raise ValueError('Use a valid YYYY-MM-DD date.')
        with get_connection(self.db_path) as c:
            latest=c.execute('SELECT MAX(trade_date) FROM equity_ohlcv WHERE volume>0').fetchone()[0]
            selected=selected or latest
            if not selected:return {'status':'NO_DATA','date':None,'rows':[]}
            exists=c.execute('SELECT COUNT(*) FROM equity_ohlcv WHERE trade_date=? AND volume>0',(selected,)).fetchone()[0]
            if not exists:return {'status':'NO_DATA','date':selected,'rows':[],'latest':latest}
            previous=c.execute('SELECT MAX(trade_date) FROM equity_ohlcv WHERE trade_date<? AND volume>0',(selected,)).fetchone()[0]
            rows=[dict(r) for r in c.execute('''SELECT e.symbol,e.open,e.high,e.low,e.avg_price,e.close,e.pr_close,e.volume,
                p.volume AS previous_volume,p.close AS previous_session_close
                FROM equity_ohlcv e LEFT JOIN equity_ohlcv p ON p.symbol=e.symbol AND p.trade_date=?
                WHERE e.trade_date=? AND e.volume>0 ORDER BY e.symbol''',(previous or '',selected))]
            prior_total=c.execute('SELECT SUM(volume) FROM equity_ohlcv WHERE trade_date=? AND volume>0',(previous or '',)).fetchone()[0]
            ref=[dict(r) for r in c.execute('SELECT list_name,symbol,company,sector FROM company_reference ORDER BY list_name,symbol')]
            idx=c.execute('SELECT trade_date,close FROM index_ohlcv WHERE trade_date=?',(selected,)).fetchone()
            before=c.execute('SELECT trade_date,close FROM index_ohlcv WHERE trade_date=?',(previous or '',)).fetchone()
        def named(target,canonical):
            choices=sorted({r['list_name'] for r in ref if re.sub('[^a-z0-9]','',r['list_name'].lower())==target})
            return canonical if canonical in choices else (choices[0] if choices else None)
        comp_name=named('complist','COMP_LIST');kse_name=named('kse100','KSE100')
        comps={r['symbol'].upper():r for r in ref if r['list_name']==comp_name};ks={r['symbol'].upper():r for r in ref if r['list_name']==kse_name}
        breadth={'advancing':0,'declining':0,'unchanged':0,'unclassified':0}
        for row in rows:
            reference=comps.get(row['symbol'].upper(),{});fallback=ks.get(row['symbol'].upper(),{})
            row['company']=(reference.get('company') or fallback.get('company') or '').strip() or None
            row['sector']=(reference.get('sector') or fallback.get('sector') or '').strip() or 'Unmapped'
            for k in ('open','high','low','avg_price','close','pr_close','previous_session_close'):
                row[k]=finite(row[k])
            # Imported previous close is the exchange-file reference; where absent,
            # use only an exact prior market-session observation, never an older quote.
            baseline=row['pr_close'] if row['pr_close'] is not None and row['pr_close']>0 else row['previous_session_close']
            row['change'],row['change_pct']=movement(row['close'],baseline)
            row['change_baseline']='source previous close' if baseline is not None and baseline==row['pr_close'] else ('previous cash session' if row['change'] is not None else None)
            row['volume_change'],row['volume_change_pct']=movement(row['volume'],row['previous_volume'],positive_previous=False)
            v=row['change']; breadth['unclassified' if v is None else 'advancing' if v>0 else 'declining' if v<0 else 'unchanged']+=1
            # Standard-band estimate, not an exchange-provided limit.
            row['limits']=estimated_limit_flags(row,selected,baseline)
            row['status']=row['limits']['status']
        total=sum(r['volume'] for r in rows)
        diff,pct=movement(total,prior_total,positive_previous=False)
        index=dict(idx) if idx else None;old=dict(before) if before else None
        if index:
            index['close']=finite(index['close']);index['change'],index['pct']=movement(index['close'],old['close'] if old else None);index['baseline_date']=old['trade_date'] if old else None
        cap={}
        for key in ('upper_touch','upper_close','lower_touch','lower_close'):
            vals=[r['limits'][key] for r in rows if r['limits'][key] is not None]
            cap[key]={'count':sum(vals) if vals else None,'checked':len(vals),'total':len(rows)}
        return {'status':'OK','date':selected,'previous_cash_date':previous,'latest':latest,'rows':rows,
                'index':index,'volume':{'current':total,'previous':prior_total,'change':diff,'pct':pct},
                'breadth':{'total':len(rows),**breadth},'caps':cap,'reference_sources':{'company':comp_name,'fallback':kse_name},
                'cap_basis':'standard_estimate',
                'notes':['Only imported cash symbols with positive reported volume are counted as traded; totals may be incomplete if imports are incomplete.',
                         'Stock changes use the imported previous close; if missing, an exact prior stored market-session close is used. Volume changes use the same prior market date, not an older symbol record.',
                         'Index uses the selected date and exact previous stored cash session; if either index close is missing, change is unavailable. Missing imports cannot be distinguished from holidays. Sector references are current imported lists, not historical classifications.',
                         'Cap figures are standard-band estimates, not exchange-confirmed: exception history and adjusted reference-price information are not stored. Prices outside the assumed band are excluded. Before 27 Jan 2021 no band is assumed.']}
