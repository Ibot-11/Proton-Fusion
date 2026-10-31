import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('profile', Path(__file__).resolve().parents[1] / 'profile.py')
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)


class ProfileTests(unittest.TestCase):
    def test_defaults_live_in_runtime_and_preserve_app_integration(self):
        env = {'WINEDLLOVERRIDES': 'siappdll=n,b;icuuc=b', 'DXVK_CONFIG_FILE': '/user/config'}
        profile.apply(env, '/runtime')
        self.assertEqual(env['DXVK_CONFIG_FILE'], '/user/config')
        self.assertEqual(env['PROTON_USE_WINED3D'], '0')
        self.assertEqual(env['WINE_FUSION_MANAGED_PANELS'], '1')
        self.assertIn('siappdll=n,b', env['WINEDLLOVERRIDES'])
        self.assertIn('icuuc=b', env['WINEDLLOVERRIDES'])
        self.assertNotIn('bcp47langs=', env['WINEDLLOVERRIDES'])
        self.assertNotIn('icuuc,', env['WINEDLLOVERRIDES'])

    def test_diagnostic_opt_out_is_preserved(self):
        env = {'WINE_FUSION_CHILD_DAMAGE': '0', 'WINE_FUSION_MANAGED_PANELS': '0'}
        profile.apply(env, '/runtime')
        self.assertEqual(env['WINE_FUSION_CHILD_DAMAGE'], '0')
        self.assertEqual(env['WINE_FUSION_MANAGED_PANELS'], '0')


if __name__ == '__main__': unittest.main()
