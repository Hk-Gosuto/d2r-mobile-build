from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
from source.build import package_ipa
from source.metal import verify_payload
from fixtures import BASE, package


class IOSPackageTests(unittest.TestCase):
    def test_ipa_contains_source_runtime_resources_and_prepared_art(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            upstream, prepared, info = package(root)
            app = root / 'DmIOS.app'
            app.mkdir()
            (app / 'DmIOS').write_bytes(b'compiled executable')
            (app / 'Info.plist').write_bytes(b'compiled app metadata')
            payload = prepared / 'source-payload.zip'
            with zipfile.ZipFile(payload, 'a') as archive:
                archive.writestr(BASE + 'native_art_manifest.json', b'prepared art metadata')
                archive.writestr(BASE + 'dm_touch_joy.png', b'prepared joystick image')
            destination = root / 'test.ipa'
            resources = package_ipa(app, payload, destination, upstream / 'dm')
            verify_payload(destination, info['payload'])
            with zipfile.ZipFile(destination) as archive:
                self.assertEqual(archive.read(BASE + 'DmIOS'), b'compiled executable')
                self.assertEqual(archive.read(BASE + 'Info.plist'), b'compiled app metadata')
                self.assertEqual(archive.read(BASE + 'native_art_manifest.json'), b'prepared art metadata')
                self.assertEqual(archive.read(BASE + 'dm/shader_map.tsv'), b'fixture shader map\n')
                self.assertEqual(archive.read(BASE + 'dm/pso_manifest.tsv'), b'# fixture pipeline seed\n')
                self.assertEqual(archive.read(BASE + 'dm/asset_pointers.txt'), b'# fixture download pointers\n')
                self.assertEqual(archive.read(BASE + 'dm_touch_joy.png'), b'prepared joystick image')
                manifest = archive.read(BASE + 'dm/shell_manifest.txt').decode().splitlines()
                self.assertTrue(set(resources) <= set(manifest))
                self.assertEqual(len(archive.namelist()), len(set(archive.namelist())))

    def test_missing_runtime_table_stops_packaging(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            upstream, prepared, _ = package(root)
            (upstream / 'dm/gfx/nvn/shader_map.tsv').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing upstream runtime resource: dm/shader_map.tsv'):
                package_ipa(root / 'DmIOS.app', prepared / 'source-payload.zip', root / 'test.ipa', upstream / 'dm')
