"""Fusion-specific runtime defaults shared by Proton and direct Wine helpers."""
from pathlib import Path


def apply(environment, runtime):
    environment.setdefault('PROTON_USE_WINED3D', '0')
    environment.setdefault('PROTON_USE_XALIA', '0')
    environment.setdefault('NO_AT_BRIDGE', '1')
    environment.setdefault('WINE_FUSION_CHILD_DAMAGE', '1')
    environment.setdefault('WINE_FUSION_MANAGED_PANELS', '1')
    environment.setdefault('WINE_FUSION_PANEL_FIRST_PAINT', '1')
    environment.setdefault('DXVK_CONFIG_FILE', str(Path(runtime) / 'fusion/dxvk.conf'))
    overrides = environment.get('WINEDLLOVERRIDES', '')
    native = ('icuuc', 'icuin', 'icudt', 'd3dcompiler_47')
    configured = {dll.lower() for group in overrides.split(';')
                  for dll in group.split('=', 1)[0].split(',') if dll}
    missing = [dll for dll in native if dll not in configured]
    if missing:
        environment['WINEDLLOVERRIDES'] = ';'.join(filter(None, (overrides, ','.join(missing) + '=n,b')))
    return environment
