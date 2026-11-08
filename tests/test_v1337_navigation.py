from pathlib import Path
import pytest
from test_v1335_analytics import svc

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'psx_app' / 'static'

def test_navigation_groups_and_market_tabs():
 html=(STATIC/'index.html').read_text()
 assert 'Data &amp; System Management' in html
 group=html.split('<details class="nav-group1337"',1)[1].split('</details>',1)[0]
 assert group.index('data-view="reconciliation"') < group.index('data-view="settings"')
 assert all(f'data-view="{old}"' not in html for old in ('highlow','monthlysector','monthlyindex'))
 tabs=(STATIC/'market1321.js').read_text()
 assert "['highLow','Symbol High-Low Analysis']" in tabs
 assert "['monthlyPerformance','Monthly Performance']" in tabs
 app=(STATIC/'app.js').read_text()
 assert "view === 'highlow'" in app and "view === 'monthlysector' || view === 'monthlyindex'" in app

def test_monthly_change_and_missing_baseline(svc):
 report=svc.sector_monthly('SECTOR',2026)
 abc=next(x for x in report['rows'] if x['symbol']=='ABC')
 assert abc['months'][1]['change'] == pytest.approx(21)
 assert abc['months'][1]['pct'] == pytest.approx(21)
 assert abc['months'][3]['change'] is None
 assert abc['months'][3]['pct'] is None

def test_requested_display_and_hover_preservation():
 js=(STATIC/'analytics1335.js').read_text(); css=(STATIC/'styles.css').read_text()
 sector=js.split('function sectorTable1335(',1)[1].split('async function renderAnalytics1335',1)[0]
 assert 'Company Name' not in sector
 assert 'v?.change' in sector and 'v?.pct' in sector
 assert 'chart1337-label' in js and 'analytic-label-${j?' in js
 assert 'cursor:help' not in css.replace(' ', '')
 assert 'data-chart-tip1329' in js
 intelligence=(STATIC/'sectorIntelligence1336.js').read_text()
 assert 'si-method1336' not in intelligence and 'html+=siCharts1336(r.rows)' in intelligence
