"""Regression checks for new tab wiring and progressive native filter search."""
from pathlib import Path
import subprocess
from test_v1321_frontend import frontend
ROOT=Path(__file__).resolve().parents[1]

def test_matching_tab_is_adjacent_and_existing_tab_remains():
 html=frontend("marketTabs1321('matching1')")
 assert html.index('>Matching Rate</button>')<html.index('>Matching Rate 1</button>')<html.index('>Small Cards</button>')
 assert html.count('aria-pressed="true"')==1
 assert 'Matching Rate 1</button>' in html

def test_search_and_range_assets_and_default_records():
 index=(ROOT/'psx_app/static/index.html').read_text()
 for name in ['matching1327.js','search1327.js']:
  assert name+'?v=1.3.32' in index
  subprocess.run(['node','--check',str(ROOT/'psx_app/static'/name)],check=True)
 search=(ROOT/'psx_app/static/search1327.js').read_text()
 assert 'select.options.length<12' in search and "input.type='search'" in search
 assert "select.addEventListener('change'" in search and 'select.replaceChildren(...original)' in search
 match=(ROOT/'psx_app/static/matching1327.js').read_text()
 for part in ['includeRecent:true','include_recent:',"page_size",'Find prices','Include latest month']:
  assert part in match
 market=(ROOT/'psx_app/static/upgrade139.js').read_text()
 assert "symbol:'PRL',days:14" in market and 'renderMatchingOne1327(container,ticket)' in market
