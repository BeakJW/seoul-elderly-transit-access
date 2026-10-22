"""Restore the exact original boundary file from its browser-upload-sized ZIP."""
from pathlib import Path
import zipfile,hashlib,shutil
root=Path(__file__).resolve().parents[1]
p=root/'data/raw/HangJeongDong_ver20260701.geojson'
if not p.exists():
    with zipfile.ZipFile(p.with_suffix('.zip')) as z, z.open(p.name) as src, p.open('wb') as dst:
        shutil.copyfileobj(src,dst)
assert hashlib.sha256(p.read_bytes()).hexdigest()=='c01ef44a0eb00978662ba7a6240ccb1da287fb52abd85104a1758969d391132f'
print('Boundary original restored and SHA256 verified.')
