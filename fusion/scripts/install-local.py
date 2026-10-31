#!/usr/bin/env python3
"""Install a versioned, verified local Fusion runtime without changing stock Proton."""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base', required=True, type=Path)
parser.add_argument('--unix-build', required=True, type=Path)
parser.add_argument('--pe-build', required=True, type=Path)
parser.add_argument('--destination', type=Path, default=Path(os.environ.get('XDG_DATA_HOME', str(Path.home()/'.local/share'))) / 'fusion-linux-dx11/runtimes/Proton-Fusion')
args = parser.parse_args()
reference = json.loads((ROOT / 'fusion/upstream.json').read_text())['reference_runtime']
if args.base.joinpath('version').read_text().split()[-1] != reference:
    parser.error('The installed base differs from fusion/upstream.json. Build a full SDK runtime or update and verify the source base first.')
versions = args.destination / 'versions'
versions.mkdir(parents=True, exist_ok=True)
install_lock = (args.destination / '.install.lock').open('a')
fcntl.flock(install_lock, fcntl.LOCK_EX)
stage = Path(tempfile.mkdtemp(prefix='.stage-', dir=versions))
try:
    subprocess.run(['cp', '-a', '--reflink=auto', str(args.base.resolve()) + '/.', str(stage)], check=True)
    for path in (stage/'__pycache__', stage/'user_settings.py', stage/'dist.lock'):
        if path.is_dir(): shutil.rmtree(path)
        else: path.unlink(missing_ok=True)
    payload = {
        'files/lib/wine/x86_64-unix/win32u.so': args.unix_build/'dlls/win32u/win32u.so',
        'files/lib/wine/x86_64-unix/winex11.so': args.unix_build/'dlls/winex11.drv/winex11.so',
        'files/lib/wine/x86_64-windows/bcp47langs.dll': args.pe_build/'dlls/bcp47langs/x86_64-windows/bcp47langs.dll',
        'proton': ROOT/'proton', 'fusion/__init__.py': ROOT/'fusion/__init__.py',
        'fusion/profile.py': ROOT/'fusion/profile.py', 'fusion/dxvk.conf': ROOT/'fusion/dxvk.conf',
    }
    for relative, source in payload.items():
        target = stage/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.unlink(missing_ok=True)
        shutil.copy2(source, target)
    (stage/'proton').chmod(0o755)
    spec = importlib.util.spec_from_file_location('write_manifest', ROOT/'fusion/scripts/write-manifest.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = module.write(stage, 'native-overlay')
    (stage/'compatibilitytool.vdf').write_text('"compatibilitytools" { "compat_tools" { "Proton-Fusion" { "install_path" "." "display_name" "Proton-Fusion" "from_oslist" "windows" "to_oslist" "linux" } } }\n')
    target = versions/manifest['build_id']
    if target.exists():
        if (target/'fusion-runtime.json').read_bytes() != (stage/'fusion-runtime.json').read_bytes():
            raise RuntimeError('An existing build has conflicting metadata; leaving it untouched')
        shutil.rmtree(stage)
    else:
        stage.rename(target)
    link = args.destination / '.current-new'
    link.unlink(missing_ok=True)
    link.symlink_to(Path('versions')/target.name, target_is_directory=True)
    os.replace(link, args.destination/'current')
    print(target.resolve())
finally:
    if stage.exists(): shutil.rmtree(stage)
