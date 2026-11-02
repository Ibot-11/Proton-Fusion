#!/usr/bin/env python3
"""Build isolated X11 fault shims; do not install them into a runtime."""
import argparse
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('output', type=Path)
args = parser.parse_args()
args.output = args.output.resolve()
args.output.mkdir(parents=True, exist_ok=True)
source = Path(__file__).with_name('x11-fault-shim.c')
cache = subprocess.check_output(['ldconfig', '-p'], text=True)
for library, alias, define in (('libXdamage.so.1', 'libZdamage.so.1', 'FUSION_TEST_DAMAGE'),
                               ('libXrandr.so.2', 'libZrandr.so.2', 'FUSION_TEST_RANDR'),
                               ('libxcb-randr.so.0', 'libzcb-randr.so.0', 'FUSION_TEST_XCB_RANDR')):
    matches = [line.split('=>', 1)[1].strip() for line in cache.splitlines()
               if line.strip().startswith(library + ' ') and 'x86-64' in line]
    if not matches:
        raise RuntimeError('Missing native library: ' + library)
    # Same-length SONAME replacement only in the private test copy. This keeps
    # the real dependency separate from the interposer without a patchelf dependency.
    data = Path(matches[0]).read_bytes()
    old, new = library.encode() + b'\0', alias.encode() + b'\0'
    if data.count(old) != 1 or len(old) != len(new):
        raise RuntimeError('Unexpected library SONAME layout: ' + library)
    (args.output/alias).write_bytes(data.replace(old, new))
    subprocess.run(['gcc', '-shared', '-fPIC', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-D'+define, str(source), '-L'+str(args.output), '-Wl,--no-as-needed',
                    '-l:'+alias, '-Wl,-rpath,$ORIGIN', '-lX11', '-ldl',
                    '-Wl,-soname,'+library, '-o', str(args.output/library)], check=True)
print(args.output)
