#!/usr/bin/env python3
"""Exercise language APIs and native X11 panel policy in an isolated prefix."""
import argparse
import ctypes as C
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('child_checker', Path(__file__).with_name('run-child-present.py'))
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class Attributes(C.Structure):
    _fields_ = [(name, C.c_int) for name in ('x','y','width','height','border_width','depth')] + [
        ('visual',C.c_void_p), ('root',C.c_ulong),
        *[(name,C.c_int) for name in ('window_class','bit_gravity','win_gravity','backing_store')],
        ('backing_planes',C.c_ulong), ('backing_pixel',C.c_ulong), ('save_under',C.c_int),
        ('colormap',C.c_ulong), ('map_installed',C.c_int), ('map_state',C.c_int),
        ('all_event_masks',C.c_long), ('your_event_mask',C.c_long), ('do_not_propagate_mask',C.c_long),
        ('override_redirect',C.c_int), ('screen',C.c_void_p)]


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--runtime', required=True, type=Path)
parser.add_argument('--steam', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
prefix = args.output.resolve()/'prefix'
prefix.mkdir(exist_ok=True)
env = os.environ.copy()
for name in ('WINEDLLOVERRIDES','VK_INSTANCE_LAYERS','VK_LAYER_PATH','WINE_FUSION_MANAGED_PANELS'):
    env.pop(name,None)
env.update(STEAM_COMPAT_DATA_PATH=str(prefix), STEAM_COMPAT_CLIENT_INSTALL_PATH=str(args.steam.resolve()), WINEDEBUG='+fusion')
proton = args.runtime.resolve()/'proton'
with (args.output/'language.log').open('w') as log:
    result = subprocess.run([str(proton),'run',str(ROOT/'.build/tests/bcp47-probe.exe')],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=60)
    if result.returncode: raise SystemExit(f'Language API probe failed: {result.returncode}')
cases = []
for disabled in (False, True):
    run_env = dict(env)
    if disabled: run_env['WINE_FUSION_MANAGED_PANELS']='0'
    with (args.output/f'panels-{disabled}.log').open('w') as log:
        process = subprocess.Popen([str(proton),'run',str(ROOT/'.build/tests/panel-probe.exe')],env=run_env,stdout=log,stderr=subprocess.STDOUT)
        x = checker.X11()
        x.lib.XGetWindowAttributes.argtypes=[C.c_void_p,C.c_ulong,C.POINTER(Attributes)]
        x.lib.XGetWindowAttributes.restype=C.c_int
        actual={}
        deadline=time.monotonic()+15
        try:
            while time.monotonic()<deadline and process.poll() is None:
                for window,_ in x.windows():
                    name=x.name(window)
                    if name and name.startswith('FusionPanelProbe-') and name!='FusionPanelProbe-Owner':
                        attr=Attributes()
                        if x.lib.XGetWindowAttributes(x.display,window,C.byref(attr)) and attr.map_state==2:
                            actual[name.removeprefix('FusionPanelProbe-')]=bool(attr.override_redirect)
                if len(actual)==4: break
                time.sleep(.02)
            expected=dict(Panel=disabled,Bar=disabled,HUD=True,Other=True)
            if actual!=expected: raise RuntimeError(f'Panel policy mismatch: {actual}, expected {expected}')
            if process.wait(timeout=10): raise RuntimeError('Panel probe modified Win32 styles or failed')
            cases.append(dict(disabled=disabled,override_redirect=actual))
        finally:
            if process.poll() is None: process.terminate();process.wait(timeout=10)
            x.lib.XCloseDisplay(x.display)
summary=dict(language_api='passed', panel_cases=cases, runtime=str(args.runtime.resolve()))
(args.output/'result.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary))
