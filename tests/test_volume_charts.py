"""Execute chart rendering in Node; verify dynamic labels/layout without a CDN."""
import json, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def run_chart(parts):
    source=(ROOT/'psx_app/static/upgrade139.js').read_text()
    source=source[source.index('const colors139='):source.index('function marketRefresh139()')]
    js="const h=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('\\\"','&quot;');const fmtNum=(n,d=2)=>Number(n).toFixed(d);\n"+source
    js+='\nconst parts='+json.dumps(parts)+';const r={total:parts.reduce((s,p)=>s+p.volume,0),parts};console.log(JSON.stringify({labels:volumeLabels139(parts),donut:donut139(r),bars:columns139(r),colors:parts.map(volumeColor139)}));'
    return json.loads(subprocess.check_output(['node','-e',js],text=True))

def sample(pcts):
    return [{'symbol':('Others' if i==len(pcts)-1 else 'SYM'+str(i)), 'pct':p,'volume':p*10000} for i,p in enumerate(pcts)]

def test_donut_direct_labels_replace_legend_and_match_bar_colors():
    parts=sample([7,6.3,6,4.4,3.3,3.3,2.5,2.3,2.3,2,60.6]);r=run_chart(parts)
    assert '<ul' not in r['donut'] and 'chart-legend139' not in r['donut']
    assert r['donut'].count('class="donut-label139"')==11
    for p,color in zip(parts,r['colors']):
        assert p['symbol'] in r['donut'] and p['symbol'] in r['bars']
        assert f'stroke="{color}"' in r['donut'] and f'fill="{color}"' in r['bars']
        assert f"{p['pct']:.2f}%" in r['donut']
    assert r['colors'][-1]=='#8492A6'

def test_labels_stay_in_bounds_and_do_not_overlap_at_extremes():
    for percentages in [[.01]*10+[99.9],[9.99]*10+[.1],[50,50],[100]]:
        r=run_chart(sample(percentages))
        for side in [-1,1]:
            ys=sorted(p['y'] for p in r['labels'] if p['side']==side)
            assert all(34<=y<=444 for y in ys)
            assert all(b-a>=33.99 for a,b in zip(ys,ys[1:]))

def test_chart_data_updates_and_symbols_are_escaped():
    a=run_chart([{'symbol':'<TEST>','pct':100,'volume':1000000}])
    b=run_chart([{'symbol':'<TEST>','pct':100,'volume':2000000}])
    assert '&lt;TEST>' in a['donut'] and '<TEST>' not in a['donut']
    assert '1.00M' in a['donut'] and '2.00M' in b['donut']
    r=run_chart([])
    assert 'No positive' in r['donut'] and 'No volume data' in r['bars']

def test_headline_and_responsive_chart_container():
    js=(ROOT/'psx_app/static/upgrade139.js').read_text()
    assert 'stocks account for ${r.top_pct.toFixed(2)}% of total volume' in js
    assert '39.45' not in js
    css=(ROOT/'psx_app/static/styles.css').read_text()
    assert '.volume-chart139{overflow-x:auto' in css
