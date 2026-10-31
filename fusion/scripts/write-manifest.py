#!/usr/bin/env python3
"""Record the exact runtime payload consumed by the Fusion launcher."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = ('proton', 'fusion/__init__.py', 'fusion/profile.py', 'fusion/dxvk.conf',
           'files/lib/wine/x86_64-unix/win32u.so',
           'files/lib/wine/x86_64-unix/winex11.so',
           'files/lib/wine/x86_64-windows/bcp47langs.dll')


def write(runtime, kind):
    runtime = Path(runtime)
    files = {name: hashlib.sha256((runtime / name).read_bytes()).hexdigest() for name in PAYLOAD}
    upstream = json.loads((ROOT / 'fusion/upstream.json').read_text())
    revision = subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip()
    digest = hashlib.sha256(json.dumps(dict(files=files, source_commit=revision, kind=kind,
                                           proton_base=upstream['proton']['commit']), sort_keys=True).encode()).hexdigest()
    data = dict(schema=1, runtime='Proton-Fusion', build_id='fusion-' + digest[:16],
                kind=kind, architectures=['x86_64'],
                source_repository='https://github.com/Ibot-11/Proton-Fusion',
                source_commit=revision,
                proton_base=upstream['proton']['commit'],
                features=dict(child_damage=1, managed_qt_panels=1, bcp47_user_languages=1, profile_defaults=1),
                files=files)
    (runtime / 'fusion-runtime.json').write_text(json.dumps(data, indent=2) + '\n')
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runtime', type=Path)
    parser.add_argument('--kind', choices=('sdk', 'native-overlay'), required=True)
    args = parser.parse_args()
    print(json.dumps(write(args.runtime, args.kind)))
