"""Daily (not swing-pivot) market structure for a single imported symbol.

The previous *consecutive stored* session supplies the structural high/low.
A 0.5% similarity band identifies near-flat pairs; everything else not
aligned in both directions is mixed. This is an explicit descriptive heuristic,
not an official or predictive indicator. All decisions are made forward only.
"""
import math

SIMILARITY=0.005

def _price(x):
    try:
        return math.isfinite(float(x)) and float(x)>0
    except (TypeError, ValueError, OverflowError):
        return False

def _valid(b):
    if not all(_price(b.get(k)) for k in ('high','low','close')):return False
    return float(b['low'])<=float(b['close'])<=float(b['high'])

def analyze_structure(bars):
    events={k:None for k in ('HH','HL','LH','LL')}
    last_signal=None; state=None; duration=0; previous=None; partial=False
    prior_bar=None; relevant=None
    for bar in bars:
        if not _valid(bar):
            # Do not bridge broken OHLC records or infer the missing direction.
            prior_bar=None;state=None;duration=0;previous=None;partial=False;relevant=None
            continue
        high=float(bar['high']);low=float(bar['low']);close=float(bar['close']);day=bar['trade_date']
        if prior_bar is None:
            prior_bar=bar;state=None;duration=0;relevant=None;continue
        ph=float(prior_bar['high']);pl=float(prior_bar['low']);pday=prior_bar['trade_date']
        relevant={'high':{'price':prior_bar['high'],'date':pday},'low':{'price':prior_bar['low'],'date':pday}}
        if high>ph:events['HH']={'price':bar['high'],'date':day}
        elif high<ph:events['LH']={'price':bar['high'],'date':day}
        if low>pl:events['HL']={'price':bar['low'],'date':day}
        elif low<pl:events['LL']={'price':bar['low'],'date':day}
        # Classify a signal using the prior state/levels before updating it.
        if state in ('bullish','bearish'):
            kind=direction=level=None
            if close>ph:
                kind='BOS' if state=='bullish' else 'CHoCH';direction='bullish';level=prior_bar['high']
            elif close<pl:
                kind='BOS' if state=='bearish' else 'CHoCH';direction='bearish';level=prior_bar['low']
            if kind:
                last_signal={'kind':kind,'direction':direction,'level':level,'level_date':pday,'close':bar['close'],'date':day}
        near=abs(high-ph)/ph<=SIMILARITY and abs(low-pl)/pl<=SIMILARITY
        if near:new='sideways'
        elif high>ph and low>pl:new='bullish'
        elif high<ph and low<pl:new='bearish'
        else:new='mixed'
        if state==new:
            duration+=1
        else:
            previous={'state':state,'sessions':duration,'partial':partial} if state else None
            # The start before the first comparable pair is unknowable.
            partial=state is None
            state=new;duration=1
        prior_bar=bar
    return {'state':state or 'unavailable','sessions':duration,'partial':partial,'previous':previous,
            'events':events,'relevant':relevant,'signal':last_signal,'similarity_pct':SIMILARITY*100}
