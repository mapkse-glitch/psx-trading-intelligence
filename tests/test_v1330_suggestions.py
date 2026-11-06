"""Guard the shared, local-first searchable filter behavior."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]

def test_suggestions_are_visible_and_keyboard_accessible():
    source=(ROOT/'psx_app/static/search1327.js').read_text()
    css=(ROOT/'psx_app/static/styles.css').read_text()
    for token in ("setAttribute('role','combobox')", "setAttribute('role','listbox')", "setAttribute('role','option')", "aria-activedescendant", "e.key==='ArrowDown'", "e.key==='ArrowUp'", "e.key==='Escape'", "e.key==='Enter'", 'No matching options', '300 shown', 'select.dispatchEvent', 'select.replaceChildren(...original)'):
        assert token in source
    assert 'row.textContent=option.textContent.trim()' in source
    assert 'fetch(' not in source and 'apiGet(' not in source
    assert 'select.options.length<12' in source and '/symbol|ticker/i' in source
    assert '.search-suggestions1330[hidden]{display:none}' in css
    subprocess.run(['node','--check',str(ROOT/'psx_app/static/search1327.js')],check=True)
