#!/usr/bin/env python3
"""Verify first-paint visibility for buffered GDI and directly rendered GPU panels."""
import argparse
import ctypes as C
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('checker', Path(__file__).with_name('run-child-present.py'))
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--runtime', required=True, type=Path)
parser.add_argument('--steam', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
parser.add_argument('--dpi', type=int, choices=(96,144), default=96)
parser.add_argument('--unaware', action='store_true')
parser.add_argument('--gpu', choices=('before', 'after'), help='Create a GPU client before or after showing the panel')
parser.add_argument('--expect-gpu-hidden', action='store_true', help='Require the previous build to reproduce the hidden GPU panel')
args = parser.parse_args()
if args.expect_gpu_hidden and not args.gpu:
    parser.error('--expect-gpu-hidden requires --gpu')
args.output.mkdir(parents=True, exist_ok=True)
prefix = args.output.resolve()/'prefix'
marker = prefix/'.proton-fusion-test-prefix'
if (prefix/'pfx').exists() and not marker.exists():
    raise RuntimeError('Refusing to use an existing non-test prefix')
prefix.mkdir(exist_ok=True)
marker.touch()
env = os.environ.copy()
for key in ('WINEDLLOVERRIDES', 'VK_INSTANCE_LAYERS', 'VK_LAYER_PATH', 'WINE_FUSION_PANEL_FIRST_PAINT'):
    env.pop(key, None)
env.update(STEAM_COMPAT_DATA_PATH=str(prefix),
           STEAM_COMPAT_CLIENT_INSTALL_PATH=str(args.steam.resolve()), WINEDEBUG=os.environ.get('FUSION_PROBE_DEBUG','-all'))
for key in ('FUSION_PAINT_PROBE_UNAWARE', 'FUSION_PAINT_PROBE_GPU'):
    env.pop(key, None)
if args.unaware: env['FUSION_PAINT_PROBE_UNAWARE'] = '1'
if args.gpu: env['FUSION_PAINT_PROBE_GPU'] = args.gpu
with (args.output/'dpi.log').open('w') as log:
    subprocess.run([str(args.runtime.resolve()/'proton'), 'run', 'reg.exe', 'add',
                    r'HKCU\Control Panel\Desktop', '/v', 'LogPixels', '/t', 'REG_DWORD', '/d', str(args.dpi), '/f'],
                   env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=60)
results = []
cases = ((False,False,False),) if args.gpu else ((True,False,False), (False,False,False), (False,True,False), (False,False,True))
for disabled, alpha, black in cases:
    run_env = dict(env, WINE_FUSION_PANEL_FIRST_PAINT='0' if disabled else '1')
    for key, enabled in (('FUSION_PAINT_PROBE_ALPHA',alpha), ('FUSION_PAINT_PROBE_BLACK',black)):
        run_env.pop(key, None)
        if enabled: run_env[key] = '1'
    case = f'{disabled}-{alpha}-{black}'
    with (args.output/f'first-paint-{case}.log').open('w') as log:
        process = subprocess.Popen([str(args.runtime.resolve()/'proton'), 'run', str(ROOT/'.build/tests/first-paint-probe.exe')],
                                   env=run_env, stdout=log, stderr=subprocess.STDOUT)
        x = checker.X11()
        x.lib.XInternAtom.argtypes = [C.c_void_p, C.c_char_p, C.c_int]
        x.lib.XInternAtom.restype = C.c_ulong
        x.lib.XGetWindowProperty.argtypes = [C.c_void_p, C.c_ulong, C.c_ulong, C.c_long, C.c_long,
                                            C.c_int, C.c_ulong, C.POINTER(C.c_ulong), C.POINTER(C.c_int),
                                            C.POINTER(C.c_ulong), C.POINTER(C.c_ulong), C.POINTER(C.c_void_p)]
        atom = x.lib.XInternAtom(x.display, b'_NET_WM_WINDOW_OPACITY', 0)
        samples = []
        deadline = time.monotonic() + 60
        window = None
        try:
            while process.poll() is None and time.monotonic() < deadline:
                if window is None:
                    window = next((w for w, _ in x.windows() if x.name(w) == 'FusionPaintProbe-Waiting'), None)
                if window:
                    name = x.name(window)
                    if name in ('FusionPaintProbe-Waiting', 'FusionPaintProbe-Painted'):
                        actual_type, count, remaining = C.c_ulong(), C.c_ulong(), C.c_ulong()
                        fmt, data = C.c_int(), C.c_void_p()
                        opacity = 0xffffffff
                        x.lib.XGetWindowProperty(x.display, window, atom, 0, 1, 0, 0,
                                                C.byref(actual_type), C.byref(fmt), C.byref(count), C.byref(remaining), C.byref(data))
                        if data:
                            if count.value and fmt.value == 32: opacity = C.cast(data, C.POINTER(C.c_ulong))[0] & 0xffffffff
                            x.lib.XFree(data)
                        samples.append(dict(phase=name.removeprefix('FusionPaintProbe-'), opacity=opacity,
                                            pixel=x.pixel(window)))
                time.sleep(.005)
            if process.wait(timeout=5): raise RuntimeError('First-paint probe failed')
            waiting = [s for s in samples if s['phase'] == 'Waiting']
            painted = [s for s in samples if s['phase'] == 'Painted' and
                       s['opacity'] == (0 if args.expect_gpu_hidden else 0x80808080 if alpha else 0xffffffff) and
                       s['pixel'] == (0 if black else 0x3377bb)]
            (args.output/f'samples-{case}.json').write_text(json.dumps(samples))
            if len(waiting) < 10 or len(painted) < 10:
                raise RuntimeError(f'Missing waiting/painted samples for {case}: {len(waiting)}/{len(painted)}')
            exposed = sum(s['opacity'] != 0 for s in waiting)
            if disabled and not exposed: raise RuntimeError('Control did not reproduce premature visibility')
            if not disabled and args.gpu != 'before' and exposed:
                raise RuntimeError(f'Unpainted panel exposed in {exposed} samples')
            if args.expect_gpu_hidden and any(s['opacity'] != 0 for s in samples if s['phase'] == 'Painted'):
                raise RuntimeError('Previous build did not reproduce the hidden GPU panel')
            results.append(dict(disabled=disabled, alpha=alpha, black=black, waiting_samples=len(waiting), prematurely_visible=exposed,
                                painted_samples=len(painted)))
        finally:
            if process.poll() is None: process.terminate(); process.wait(timeout=10)
            x.lib.XCloseDisplay(x.display)
summary = dict(runtime=str(args.runtime.resolve()), dpi=args.dpi, unaware=args.unaware, gpu=args.gpu,
               expected_gpu_hidden=args.expect_gpu_hidden, cases=results)
(args.output/'result.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps(summary))
