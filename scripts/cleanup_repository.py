"""Remove generated/archived files only. Never delete a database, upload, credential or Git history.
Run from an extracted repository checkout: python scripts/cleanup_repository.py [--apply]
The default is a dry run. Commit deletions separately to remove tracked files from GitHub.
"""
import argparse
from pathlib import Path
import shutil

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--apply',action='store_true',help='Apply the listed non-data cleanup.')
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
if not (root/'psx_app/main.py').exists():raise SystemExit('Not a PSX application root; nothing changed.')
targets=[]
for folder in ['psx_app','tests']:
    targets.extend(p for p in (root/folder).rglob('__pycache__') if p.is_dir())
for name in ['.pytest_cache','docs/historical','docs/QA_1_3_3.json','docs/QA_1_3_4.json','docs/QA_1_3_5.json']:
    p=root/name
    if p.exists():targets.append(p)
for p in sorted(set(targets)):
    print(('REMOVE ' if args.apply else 'WOULD REMOVE ')+str(p.relative_to(root)))
    if args.apply:
        if p.is_dir():shutil.rmtree(p)
        else:p.unlink()
print('Financial data, secrets, active source, tests, and latest_cloud_sync.db.gz were NOT deleted.')
print('Commit any applied deletions to remove the tracked entries from GitHub; uploading a ZIP does not delete old files.')
