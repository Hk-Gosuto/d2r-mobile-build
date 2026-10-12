import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('ci', Path(__file__).parents[1] / 'scripts/ci.py')
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


class InputVerificationTests(unittest.TestCase):
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

    def test_missing_inputs_cannot_be_reported_as_success(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(ci, 'GAME', Path(temp) / 'absent'), patch.dict(ci.os.environ, {'GAME_INPUT_MANIFEST': ''}):
                with self.assertRaisesRegex(ValueError, 'secret missing'):
                    ci.prepare_game()

    def test_packages_require_keys_before_downloading(self):
        with tempfile.TemporaryDirectory() as temp:
            env = {'GAME_INPUT_MANIFEST': json.dumps({'kind': 'packages', 'files': []}), 'PROD_KEYS': ''}
            with patch.object(ci, 'GAME', Path(temp) / 'absent'), patch.dict(ci.os.environ, env):
                with self.assertRaisesRegex(ValueError, 'PROD_KEYS'):
                    ci.prepare_game()

    def test_rejects_non_https_download(self):
        with self.assertRaisesRegex(ValueError, 'HTTPS'):
            ci.download('http://example.invalid/game.zip', '/unused')

    def test_extracts_shell_version_from_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            shell = Path(temp) / 'shell.ipa'
            with zipfile.ZipFile(shell, 'w') as z:
                z.writestr('Payload/DmIOS.app/dm/shell_info.txt', 'PRODUCT=test\nCHAIN=abc\n')
            self.assertEqual(ci.shell_info(shell)['CHAIN'], 'abc')


if __name__ == '__main__':
    unittest.main()
