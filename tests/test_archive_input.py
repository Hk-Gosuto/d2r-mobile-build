import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import archive_input as inputs
import ci
import repository_access


def fixture(path, prefix=''):
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr(prefix + 'ExeFS/main', b'own-test-program')
        z.writestr(prefix + 'RomFS/data/test.data', b'own-test-resource')
        z.writestr(prefix + 'RomFS/data/build_manifest.psv', b'test-manifest')
        z.writestr('unrelated.txt', b'not part of the game input')


class ArchiveInputTests(unittest.TestCase):
    def test_requires_direct_https_url_and_full_digest(self):
        for url, digest in (('http://storage.invalid/input.zip', 'a'*64),
                            ('https://user:password@storage.invalid/input.zip', 'a'*64),
                            ('https://storage.invalid/input.zip', 'bad')):
            with patch.dict(os.environ, GAME_ARCHIVE_URL=url, GAME_ARCHIVE_SHA256=digest):
                with self.assertRaises(ValueError):
                    inputs.settings()

    def test_download_is_cached_before_failed_extraction_and_can_be_retried(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, archive, game = root/'source.zip', root/'raw/input', root/'game'
            fixture(source, 'wrapper/')
            digest = ci.sha256(source)
            def fetch(url, dest, expected):
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(source.read_bytes())
                self.assertEqual(expected, digest)
            with patch.dict(os.environ, GAME_ARCHIVE_URL='https://storage.invalid/input.zip', GAME_ARCHIVE_SHA256=digest), patch.object(inputs, 'ARCHIVE', archive), patch.object(inputs.ci, 'GAME', game):
                with patch.object(ci, 'download', side_effect=fetch) as download:
                    inputs.download()
                    with patch.object(ci, 'validate_game', side_effect=ValueError('wrong program')):
                        with self.assertRaisesRegex(ValueError, 'wrong program'):
                            inputs.prepare()
                    self.assertTrue(archive.is_file())
                    self.assertFalse(game.exists())
                    inputs.download()
                    self.assertEqual(download.call_count, 1)
                with patch.object(ci, 'validate_game'):
                    inputs.prepare()
                    self.assertEqual((game/'ExeFS/main').read_bytes(), b'own-test-program')
                    self.assertFalse((game/'unrelated.txt').exists())
                    with patch.object(inputs, 'extract') as extract:
                        inputs.prepare()
                        extract.assert_not_called()
                archive.write_bytes(b'corrupt')
                with patch.object(ci, 'download', side_effect=fetch) as download:
                    inputs.download()
                    download.assert_called_once()

    def test_failed_download_cannot_be_used(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp)/'missing'
            with patch.dict(os.environ, GAME_ARCHIVE_URL='https://storage.invalid/input.zip', GAME_ARCHIVE_SHA256='a'*64), patch.object(inputs, 'ARCHIVE', archive), patch.object(ci, 'GAME', Path(temp)/'game'), patch.object(ci, 'download', side_effect=RuntimeError('interrupted')):
                with self.assertRaises(RuntimeError):
                    inputs.download()
                with self.assertRaisesRegex(ValueError, 'archive missing'):
                    inputs.prepare()

    def test_wrong_prepared_cache_is_not_silently_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            game=Path(temp)
            (game/'.input-archive-sha256').write_text('b'*64)
            with patch.dict(os.environ, GAME_ARCHIVE_URL='https://storage.invalid/input.zip', GAME_ARCHIVE_SHA256='a'*64), patch.object(ci, 'GAME', game):
                with self.assertRaisesRegex(ValueError, 'different input'):
                    inputs.prepare()

    def test_rejects_zip_traversal_links_duplicates_and_oversized_inputs(self):
        for name in ('../escape', '/escape', 'C:/escape', 'a\\escape'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root=Path(temp)
                with zipfile.ZipFile(root/'input.zip', 'w') as z:
                    z.writestr(name, b'bad')
                with self.assertRaisesRegex(ValueError, 'Unsafe'):
                    inputs.extract(root/'input.zip', root/'extracted')
                self.assertFalse((root/'escape').exists())
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with zipfile.ZipFile(root/'link.zip', 'w') as z:
                member=zipfile.ZipInfo('link');member.external_attr=(stat.S_IFLNK|0o777)<<16
                z.writestr(member, '../escape')
            with self.assertRaisesRegex(ValueError, 'link'):
                inputs.extract(root/'link.zip', root/'out')
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            inputs.safe_members([('a/file', 1, False, True), ('a/FILE', 1, False, True)])
        with self.assertRaisesRegex(ValueError, 'size'):
            inputs.safe_members([('file', inputs.MAX_EXPANDED_BYTES+1, False, True)])

    def test_tar_root_directory_and_files_work_but_links_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with tarfile.open(root/'input.tar.gz', 'w:gz') as t:
                directory=tarfile.TarInfo('.');directory.type=tarfile.DIRTYPE;t.addfile(directory)
                file=tarfile.TarInfo('./ExeFS/main');file.size=4;t.addfile(file,io.BytesIO(b'test'))
            inputs.extract(root/'input.tar.gz', root/'out')
            self.assertEqual((root/'out/ExeFS/main').read_bytes(), b'test')
            with tarfile.open(root/'link.tar', 'w') as t:
                link=tarfile.TarInfo('link');link.type=tarfile.SYMTYPE;link.linkname='../escape';t.addfile(link)
            with self.assertRaisesRegex(ValueError, 'link'):
                inputs.extract(root/'link.tar', root/'bad')

    def test_public_repository_and_failed_visibility_lookup_are_rejected(self):
        for metadata in ({'private':False,'full_name':'owner/repo'},
                         {'private':True,'full_name':'other/repo'}):
            with patch.object(repository_access.subprocess, 'check_output', return_value=json.dumps(metadata)):
                with self.assertRaisesRegex(ValueError, 'private repository'):
                    repository_access.require_private('owner/repo')
        with patch.object(repository_access.subprocess, 'check_output', return_value=json.dumps({'private':True,'full_name':'owner/repo'})):
            self.assertEqual(repository_access.require_private('owner/repo'), 'owner/repo')


if __name__ == '__main__':
    unittest.main()
