"""Requested card corrections only: colors, lock status, tracking close and motion."""
import json
import pytest
from test_v1318_market_highlights import ROOT,run_js

@pytest.mark.parametrize('change,color',[(3.08,'pos'),(-784,'neg'),(0,''),(None,'')])
def test_latest_symbol_and_index_close_use_daily_sign(change,color):
 for title in ['Latest Close','Latest Index Close']:
  html=run_js('latestMarketCard1317('+json.dumps(title)+','+json.dumps({'close':500,'change':change,'pct':change,'trade_date':'2026-10-30'})+',"TEST")')
  assert f'class="latest-close1317 {color}"' in html
  assert 'DoD Change' in html and 'DoD Change (%)' in html and '500.00' in html

@pytest.mark.parametrize('close,color,pos,closed',[(110,'pos',0,True),(90,'neg',100,True),(105,'pos',25,False),(95,'neg',75,False),(100,'',50,False),(120,'pos',0,True),(80,'neg',100,True)])
def test_closing_rate_is_beneath_bar_tracks_indicator_and_has_sign(close,color,pos,closed):
 html=run_js(f'priceLimitCard1318({{close:{close},pr_close:100,trade_date:"2026-10-30"}},"TEST")')
 assert f'class="moving-close1320 {color}"' in html
 assert f'--close-position1320:{pos:.6f}%' in html and f'left:{pos:.6f}%' in html
 assert html.index('price-range-track1319')<html.index('Closing rate')
 assert f'PKR {close:.2f}' in html and 'Previous close</span>' not in html
 assert 'range-closing1319' not in html and 'price-range-footer1319' not in html
 assert 'price-lock-status1320' in html
 status_icon=html.split('price-lock-status1320',1)[1].split('</svg>',1)[0]
 assert ('M9 14V9a7 7 0 0 1 14 0v5' in status_icon)==closed
 assert ('M9 14V9a7 7 0 0 1 13-3' in status_icon)==(not closed)

@pytest.mark.parametrize('row',[None,{}, {'close':10,'pr_close':0}])
def test_unavailable_uses_unlocked_icon_no_marker_and_neutral_label(row):
 html=run_js('priceLimitCard1318('+json.dumps(row)+',"TEST")')
 assert 'Check unavailable' in html and 'price-range-marker1319' not in html
 assert 'class="moving-close1320 "' in html
 assert 'Previous close</span>' not in html
 assert 'M9 14V9a7 7 0 0 1 13-3' in html

def test_motion_is_opt_in_to_os_preference_short_and_does_not_animate_layout():
 css=(ROOT/'psx_app/static/styles.css').read_text()
 assert '@media(prefers-reduced-motion:no-preference)' in css
 assert '.view-container{animation:workspaceEnter1320 .18s ease-out both}' in css
 assert '@media(prefers-reduced-motion:reduce){.view-container{animation:none!important}' in css
 assert '.price-range-marker1319,.moving-close1320{transition:none!important}' in css
 assert 'left:clamp(0px,calc(var(--close-position1320) - 72px),calc(100% - 144px))' in css
 assert '.moving-close1320.pos>strong{color:var(--pos-green)}' in css
 assert '.moving-close1320.neg>strong{color:var(--neg-red)}' in css
