#!/usr/bin/env python3
"""Compare fatal X11 resource races in old and fixed runtimes using private prefixes."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline', required=True, type=Path)
parser.add_argument('--runtime', required=True, type=Path)
parser.add_argument('--steam', required=True, type=Path)
parser.add_argument('--shims', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
args.output = args.output.resolve()
args.output.mkdir(parents=True, exist_ok=True)
cases = [('create', 'FUSION_TEST_BAD_DRAWABLE', 'BadDrawable'),
         ('destroy', 'FUSION_TEST_BAD_DAMAGE_DESTROY', 'BadDamage'),
         ('subtract', 'FUSION_TEST_BAD_DAMAGE_SUBTRACT', 'BadDamage'),
         ('crtc', 'FUSION_TEST_BAD_CRTC', 'BadRRCrtc'),
         ('unexpected', 'FUSION_TEST_UNEXPECTED_XERROR', 'BadAtom')]
results = []


def stop_test_server(runtime, prefix):
    if not (prefix/'.proton-fusion-test-prefix').is_file():
        raise RuntimeError('Refusing to stop a non-test Wine server')
    env = dict(os.environ, WINEPREFIX=str(prefix/'pfx'))
    server = str(runtime/'files/bin/wineserver')
    # -k returns 1 when the last crashed client has already stopped the server.
    killed = subprocess.run([server, '-k'], env=env, capture_output=True, timeout=15)
    if killed.returncode not in (0, 1):
        raise RuntimeError('Unable to stop test server: ' + killed.stderr.decode(errors='replace'))
    subprocess.run([server, '-w'], env=env, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=15, check=True)


for label, runtime in (('baseline', args.baseline.resolve()), ('patched', args.runtime.resolve())):
    prefix = args.output/('prefix-'+label)
    for name, setting, error in cases:
        output = args.output/(label+'-'+name)
        output.mkdir(exist_ok=True)
        if prefix.exists(): stop_test_server(runtime, prefix)
        env = {k:v for k,v in os.environ.items() if not k.startswith('FUSION_TEST_')}
        env.update({setting:'1', 'WINEDEBUG':'+fusion',
                    'LD_LIBRARY_PATH':str(args.shims.resolve()) + ':' + env.get('LD_LIBRARY_PATH','')})
        cmd = [sys.executable, str(ROOT/'fusion/tests/run-child-present.py'),
               '--proton', str(runtime), '--steam', str(args.steam.resolve()),
               '--exe', str(ROOT/'.build/tests/child-present.exe'), '--prefix', str(prefix),
               '--config', str(ROOT/'fusion/tests/dxvk.conf'), '--output', str(output),
               '--bursts', '12', '--resize', '--minimize', '--timeout', '45']
        try:
            with (output/'runner.log').open('w') as log:
                process = subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=65)
            text = (output/'runtime.log').read_text(errors='replace')
            if 'FUSION_FAULT:' not in text: raise RuntimeError(f'Fault injection was not exercised: {label}-{name}')
            fatal_lines = [line for line in text.splitlines() if line.startswith('X Error of failed request:')]
            fatal = bool(fatal_lines)
            expected_fatal = label == 'baseline' or name == 'unexpected'
            if fatal != expected_fatal or bool(process.returncode) != expected_fatal:
                raise RuntimeError(f'Unexpected result in {label}-{name}: exit={process.returncode}, fatal={fatal}')
            if fatal and not any(error in line for line in fatal_lines):
                raise RuntimeError(f'Unexpected fatal X11 error in {label}-{name}: {fatal_lines}')
            result = dict(runtime=label, case=name, fault=error, exit=process.returncode, fatal=fatal)
            if not fatal:
                detail = json.loads((output/'result.json').read_text())
                if detail['stale_30ms'] or detail['stale_200ms']:
                    raise RuntimeError(f'Frame recovery failed in {label}-{name}')
                result.update(samples=detail['samples'], stale_30ms=detail['stale_30ms'],
                              stale_200ms=detail['stale_200ms'], module_hashes=detail['module_hashes'])
            results.append(result)
            (args.output/'result.json').write_text(json.dumps(results, indent=2)+'\n')
            print(json.dumps(result), flush=True)
        finally:
            if prefix.exists(): stop_test_server(runtime, prefix)
