"""Descending close-range presentation; unchanged price-rule and market data."""
import pytest
from test_v1318_market_highlights import ROOT,run_js

@pytest.mark.parametrize('close,position,up,down',[
 (110,0,1,0),(100,50,0,0),(90,100,0,1),(105,25,.5,0),(95,75,0,.5),
 (120,0,1,0),(80,100,0,1)])
def test_descending_range_marker_and_proximity(close,position,up,down):
 r=run_js(f'priceRange1319({{close:{close},pr_close:100}})')
 assert r['position']==pytest.approx(position)
 assert r['upperProximity']==pytest.approx(up) and r['lowerProximity']==pytest.approx(down)

@pytest.mark.parametrize('row',['null','{}','{close:10,pr_close:0}','{close:NaN,pr_close:100}'])
def test_missing_data_does_not_fabricate_marker(row):
 r=run_js(f'priceRange1319({row})')
 assert r['position'] is None and r['status']=='UNAVAILABLE'
 html=run_js(f'priceLimitCard1318({row},"TEST")')
 assert 'price-range-marker1319' not in html and 'range-unavailable1319' in html
 assert 'NaN' not in html and 'Infinity' not in html

def test_low_price_threshold_still_uses_one_rupee_not_ten_percent():
 r=run_js('priceRange1319({close:5.5,pr_close:5})')
 assert r['upper']==6 and r['lower']==4 and r['position']==25

def test_range_markup_end_order_date_and_actual_close_when_outside_bounds():
 html=run_js('priceLimitCard1318({close:120,pr_close:100,trade_date:"2026-10-30"},"<TEST>")')
 assert html.index('Upper Lock')<html.index('Lower Lock')
 assert 'PKR 120.00' in html and 'left:0.000000%' in html
 assert '2026-10-30' in html and '&lt;TEST&gt;' in html and 'Closing rate' in html
 assert 'role="img"' in html and 'role="slider"' not in html
 assert '--upper-strength1319:100.000%' in html and '--lower-strength1319:18.000%' in html
 assert 'Close-based check using the requested' not in html

def test_removed_detail_panel_and_badges_but_row_highlights_preserved():
 js=(ROOT/'psx_app/static/upgrade139.js').read_text()
 assert 'Range and volume calculation details' not in js and 'market-calculation-notes1317' not in js
 assert 'extrema-row-badge1318' not in js and '>Max high<' not in js and '>Min low<' not in js
 assert 'row-max-high1318' in js and 'row-min-low1318' in js

def test_range_uses_canonical_colors_and_does_not_change_backend():
 css=(ROOT/'psx_app/static/styles.css').read_text()
 assert '--pos-green: #03D815' in css and '--neg-red: #F63131' in css
 assert '--limit-up1318:var(--pos-green)' in css and '--limit-down1318:var(--neg-red)' in css
 assert 'var(--pos-green) var(--upper-strength1319)' in css
 assert 'var(--neg-red) var(--lower-strength1319)' in css
 assert 'var(--pos-green) 12%,var(--bg-card)' in css
 assert "values,'1.3.17'" in (ROOT/'psx_app/services/result_cache.py').read_text()
