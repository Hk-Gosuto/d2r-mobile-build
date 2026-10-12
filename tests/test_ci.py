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

    def test_torrent_requires_pinned_metadata_and_explicit_selection(self):
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            ci.download_torrent(Path('game.torrent'), {'select': [1, 2]})
        with self.assertRaisesRegex(ValueError, 'positive file indices'):
            ci.download_torrent(Path('game.torrent'), {'sha256': '0' * 64, 'select': [0]})

    def test_failed_torrent_cannot_continue_to_game_validation(self):
        with patch.object(ci.subprocess, 'run') as run:
            run.return_value.returncode = 1
            with self.assertRaisesRegex(RuntimeError, 'did not finish'):
                ci.download_torrent(Path('game.torrent'), {'sha256': '0' * 64, 'select': [1, 2]})

    def test_ticket_extracts_common_encrypted_key_and_rights_id(self):
        data = bytearray(0x400)
        data[:4] = (0x10004).to_bytes(4, 'big')
        data[0x180:0x190] = bytes(range(16))
        data[0x2A0:0x2B0] = bytes(range(16, 32))
        self.assertEqual(ci.ticket_title_key(data), (bytes(range(16, 32)).hex(), bytes(range(16)).hex()))
        data[0x281] = 1
        with self.assertRaisesRegex(ValueError, 'Personalized'):
            ci.ticket_title_key(data)
        with self.assertRaisesRegex(ValueError, 'truncated'):
            ci.ticket_title_key(data[:300])

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

    def test_extracts_shell_version_from_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            shell = Path(temp) / 'shell.ipa'
            with zipfile.ZipFile(shell, 'w') as z:
                z.writestr('Payload/DmIOS.app/dm/shell_info.txt', 'PRODUCT=test\nCHAIN=abc\n')
            self.assertEqual(ci.shell_info(shell)['CHAIN'], 'abc')


if __name__ == '__main__':
    unittest.main()
