import importlib.util
import json
import struct
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('ci', Path(__file__).parents[1] / 'scripts/ci.py')
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


class InputVerificationTests(unittest.TestCase):
    def test_build_context_is_loaded_without_changing_static_defaults(self):
        source=(Path(__file__).parents[1]/'scripts/ci.py').read_text()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'config').mkdir();(root/'outputs').mkdir()
            static=root/'config/build-pins.json'
            static.write_text(json.dumps({'game_version':'test-game','spirv_commit':'fixed-tool'}))
            original=static.read_bytes()
            for number in ('7.1','7.2'):
                context={'upstream_commit':'selected-source','app_version':'1.0.20','build_number':number}
                (root/'outputs/build-config.json').write_text(json.dumps(context))
                namespace={'__file__':str(root/'scripts/ci.py'),'__name__':'test_build_context'}
                exec(compile(source,'ci-context','exec'),namespace)
                self.assertEqual(namespace['CONFIG']['build_number'],number)
                self.assertEqual(namespace['CONFIG']['spirv_commit'],'fixed-tool')
                self.assertEqual(static.read_bytes(),original)

    def test_macho_minimum_rejects_wrong_platform_and_malformed_commands(self):
        def binary(platform=2, count=1, size=24, command_size=24):
            return struct.pack('<8I6I', 0xfeedfacf, 0x0100000c, 0, 2, count, size, 0, 0,
                               0x32, command_size, platform, 18 << 16, 18 << 16, 0)
        self.assertEqual(ci.macho_minimum_os(binary()), (18, 0, 0))
        for data in (binary(platform=7), binary(size=32), binary(count=2),
                     binary(command_size=0), binary(command_size=16), binary()[:40],
                     bytes(56)):
            with self.subTest(data=data.hex()), self.assertRaises(ValueError):
                ci.macho_minimum_os(data)


    def test_rejects_wrong_program_even_if_cache_directory_exists(self):
        with tempfile.TemporaryDirectory() as temp:
            game = Path(temp)
            (game / 'ExeFS').mkdir()
            (game / 'ExeFS/main').write_bytes(b'wrong-version')
            with self.assertRaisesRegex(ValueError, 'original 3.3.94012'):
                ci.validate_game(game)

    def test_rejects_truncated_resource(self):
        with tempfile.TemporaryDirectory() as temp:
            game = Path(temp)
            (game / 'ExeFS').mkdir()
            (game / 'RomFS/data').mkdir(parents=True)
            config = dict(ci.CONFIG, nso_sha256={})
            (game / 'RomFS/data/test.data').write_bytes(b'123')
            with patch.object(ci, 'CONFIG', config), patch.object(ci, 'resource_sizes', return_value={'test.data': 4}):
                with self.assertRaisesRegex(ValueError, 'incomplete'):
                    ci.validate_game(game)


    def test_rejects_non_https_download(self):
        with self.assertRaisesRegex(ValueError, 'HTTPS'):
            ci.download('http://example.invalid/game.zip', '/unused')


    def test_diagnostics_do_not_include_key_values(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            logs = root / 'downloads'
            logs.mkdir()
            secret = '12ab' * 8
            (logs / 'extract.log').write_text('Titlekey (Encrypted) ' + secret + '\nerror: missing RomFS\n')
            with patch.object(ci, 'ROOT', root), patch.object(ci, 'WORK', logs), patch.object(ci, 'DM', root):
                ci.diagnostics()
            saved = next((root / 'outputs/diagnostics').glob('*.log')).read_text()
            self.assertNotIn(secret, saved)
            self.assertIn('error: missing RomFS', saved)


if __name__ == '__main__':
    unittest.main()
