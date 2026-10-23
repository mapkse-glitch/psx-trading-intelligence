"""Display-only ordering regressions; no finance/database mutations."""
import json
import shutil
import subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
UTILITY = ROOT / 'psx_app/static/table_display.js'

def js(code):
    if not shutil.which('node'):
        pytest.skip('Node.js is needed for browser utility unit tests')
    result = subprocess.run(['node', '-e', f'const {{dateKey,newestFirst}}=require({json.dumps(str(UTILITY))});\n'+code], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)

@pytest.mark.parametrize('dates,expected', [
    (['2026-10-12','2026-10-21','2026-09-30'], ['2026-10-21','2026-10-12','2026-09-30']),
    (['31-12-2025','01-01-2026','21-10-2026'], ['21-10-2026','01-01-2026','31-12-2025']),
    (['2025-12','2026-01','2026-10'], ['2026-10','2026-01','2025-12']),
    ([2020,2016,2026,2025], [2026,2025,2020,2016]),
    (['2026-10-21T09:00:00','2026-10-22T08:00:00','2026-10-21T15:00:00'], ['2026-10-22T08:00:00','2026-10-21T15:00:00','2026-10-21T09:00:00']),
])
def test_newest_first_across_formats(dates, expected):
    assert js(f'console.log(JSON.stringify(newestFirst({json.dumps(dates)})));') == expected

def test_stable_sort_preserves_within_day_rank_and_does_not_mutate():
    assert js('''const rows=Object.freeze([Object.freeze({d:'2026-10-21',rank:1}),Object.freeze({d:'2026-10-22',rank:2}),Object.freeze({d:'2026-10-22',rank:3})]);
      const out=newestFirst(rows,r=>r.d);console.log(JSON.stringify([out.map(r=>r.rank),rows.map(r=>r.rank),out[0]===rows[1]]));''') == [[2,3,1],[1,2,3],True]

def test_invalid_dates_last_without_silent_day_month_swap():
    assert js("console.log(JSON.stringify(newestFirst(['not a date',null,'2026-02-30','2026-10-21','10/12/2026','2026-13-01'])));") == ['2026-10-21','not a date',None,'2026-02-30','10/12/2026','2026-13-01']

def test_iso_timezones_compare_instants():
    assert js("console.log(JSON.stringify(newestFirst(['2026-10-22T12:00:00+05:00','2026-10-22T08:00:00Z'])));") == ['2026-10-22T08:00:00Z','2026-10-22T12:00:00+05:00']

def test_empty_input_and_leap_year_validation():
    assert js("console.log(JSON.stringify([newestFirst(),newestFirst(null),dateKey('2024-02-29')===dateKey('29-02-2024'),dateKey('2025-02-29')===-Infinity]));") == [[],[],True,True]

def test_alignment_and_display_source_contract():
    css=(ROOT/'psx_app/static/styles.css').read_text()
    app=(ROOT/'psx_app/static/app.js').read_text()
    index=(ROOT/'psx_app/static/index.html').read_text()
    assert 'table.data-table th.num,' in css and 'table.data-table td.num { text-align: right;' in css
    assert index.index('/table_display.js') < index.index('/app.js')
    assert 'TableDisplay.newestFirst(rows, r => r.trade_date)' in app
    assert 'TableDisplay.newestFirst(res.rows, r => r.DATE)' in app
    assert 'TableDisplay.newestFirst(rep.monthly_summary.rows' in app
    assert 'TableDisplay.newestFirst(rep.yearly_summary.rows' in app
    assert 'TableDisplay.newestFirst(hist.batches' in app
    assert 'TableDisplay.newestFirst(data.backups' in app
    assert 'fmtDate(tDates[0])' in app and 'tDates[tDates.length-1]' not in app
    assert 'table.data-table tr.total-row td {\n  background-color: var(--bg-card-alt);' in css
    assert 'oldest → newest' not in app
    assert 'Sep–Oct 2026' not in app and 'Older Futures Rows (August)' not in app
    assert 'function renderTechnicalSvgChart(series)' in app
    assert 'renderTop5SvgChart(trendData.trend)' in app
