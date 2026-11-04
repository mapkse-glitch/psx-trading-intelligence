"""Tick-rounded price boundaries remain consistent with the displayed lock."""
import pytest
from test_v1318_market_highlights import run_js

@pytest.mark.parametrize('previous,close,lower,upper,status',[
 (25.41,22.87,22.87,27.95,'LOWER'),
 (73.98,66.58,66.58,81.38,'LOWER'),
 (25.41,22.88,22.87,27.95,'WITHIN'),
 (25.41,27.95,22.87,27.95,'UPPER'),
 (25.41,27.94,22.87,27.95,'WITHIN'),
 (25.45,22.91,22.91,28.00,'LOWER'),
 (5.00,4.00,4.00,6.00,'LOWER'),
 (5.00,6.00,4.00,6.00,'UPPER'),
])
def test_tick_rounded_limits(previous,close,lower,upper,status):
 r=run_js(f'priceLimit1318({{pr_close:{previous},close:{close}}})')
 assert r['lower']==pytest.approx(lower) and r['upper']==pytest.approx(upper)
 assert r['status']==status

def test_close_with_extra_precision_is_not_silently_rounded_into_lock():
 r=run_js('priceLimit1318({pr_close:25.41,close:22.871})')
 assert r['status']=='WITHIN'
 html=run_js('priceLimitCard1318({pr_close:25.41,close:22.871},"TEST")')
 assert 'PKR 22.871' in html and 'Within range' in html
