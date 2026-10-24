"""Requested presentation changes must not alter calculations or retain hidden date pins."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]

def test_market_volume_has_only_calendar_and_symbol_has_no_calendar():
    js=(ROOT/'psx_app/static/upgrade139.js').read_text()
    view=js[js.index('async function renderMarketView'):js.index('const colors139=')]
    assert view.count('type="date"')==1
    assert 'calendar-only1312' in view
    assert "select('Year'" not in view and "select('Month'" not in view
    assert 'Trading date hierarchy' not in view
    assert 'marketAsOf1311' not in view
    assert 'new URLSearchParams({n:m.days,end:m.date})' not in js
    assert 'new URLSearchParams({n:m.days})' in js


def test_extremes_use_roles_and_date_range_is_prominent():
    js=(ROOT/'psx_app/static/upgrade139.js').read_text()
    assert "x.value==null?'':x.label.startsWith('Min')?'neg':'pos'" in js
    assert 'date-range1312' in js and '<strong>${fmtDate(r.first)}</strong>' in js
    assert '<strong>${fmtDate(r.last)}</strong>' in js
    css=(ROOT/'psx_app/static/styles.css').read_text()
    assert '.date-range-item1312 strong' in css and 'font-size:clamp(22px,2.2vw,30px)' in css


def test_removed_prose_and_index_title():
    js=(ROOT/'psx_app/static/upgrade139.js').read_text()
    assert '<h3>Index record</h3>' in js
    for phrase in ['Market index — imported prices','Market volume below is the total','Period baseline:','Week baseline:']:
        assert phrase not in js
    assert 'r.missing_index_dates.length' in js  # Missing data still disclosed.
    assert 'secondary-note1312' in js
    app=(ROOT/'psx_app/static/app.js').read_text()
    assert '<summary>Storage details</summary>' in app
    assert '<summary>Storage &amp; backup details</summary>' in app


def test_release_build_matches():
    html=(ROOT/'psx_app/static/index.html').read_text()
    main=(ROOT/'psx_app/main.py').read_text()
    assert 'content="1.3.14"' in html and 'version="1.3.14"' in main
    assert set(re.findall(r'\.js\?v=([^"\s]+)',html))=={'1.3.14'}
