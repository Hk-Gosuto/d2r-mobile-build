import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import ci
import input_config as inputs


class InputConfigTests(unittest.TestCase):
    def test_drive_file_urls_are_supported_but_folder_links_are_rejected(self):
        for url in ('https://drive.google.com/file/d/file_123/view?usp=sharing',
                    'https://drive.google.com/uc?export=download&id=file_123',
                    'https://docs.google.com/uc?id=file_123'):
            self.assertEqual(inputs.drive_file_id(url), 'file_123')
        self.assertIsNone(inputs.drive_file_id('https://storage.invalid/file.zip'))
        self.assertIsNone(inputs.drive_file_id('https://drive.google.com.attacker.invalid/file/d/id/view'))
        with self.assertRaisesRegex(ValueError, 'folder'):
            inputs.drive_file_id('https://drive.google.com/drive/folders/folder_123')

    def test_checksum_formats_and_ambiguity(self):
        digest='a'*64
        for text in (digest, digest.upper()+'  input.zip\n', digest+' *input.zip\n', '# comment\n'+digest):
            self.assertEqual(inputs.parse_checksum(text),digest)
        for text in ('', '<html>login</html>', digest+'\n'+'b'*64, '123 input.zip'):
            with self.assertRaises(ValueError):inputs.parse_checksum(text)

    def test_external_checksum_drives_cache_identity_and_detects_changed_input(self):
        config={'url':'https://drive.google.com/file/d/game/view',
                'sha256_url':'https://drive.google.com/file/d/sums/view'}
        def fetch(url,path,**kwargs):
            self.assertEqual(url,config['sha256_url'])
            path.write_text('a'*64+'  input.zip\n')
        with patch.dict(os.environ,GAME_ARCHIVE=json.dumps(config)), patch.object(inputs,'download_file',side_effect=fetch):
            self.assertEqual(inputs.settings(),(config['url'],'a'*64))
            with patch.dict(os.environ,INPUT_REVISION='wrong'):
                with self.assertRaisesRegex(ValueError,'checksum changed'):inputs.settings()
        with patch.dict(os.environ,GAME_ARCHIVE=json.dumps(dict(config,sha256='a'*64))):
            with self.assertRaisesRegex(ValueError,'not both'):inputs.settings()

    def test_drive_download_checks_streamed_hash_and_retries_without_reading_cookies(self):
        body=b'fixture archive'
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/'game.archive'
            calls=[]
            def fetch(**kwargs):
                calls.append(kwargs)
                kwargs['hasher'].update(body)
                Path(kwargs['output']).write_bytes(body)
                kwargs['progress'](len(body),len(body))
                return kwargs['output']
            module=types.SimpleNamespace(download=fetch)
            with patch.dict(sys.modules,gdown=module):
                inputs.download_file('https://drive.google.com/file/d/game/view',dest,hashlib.sha256(body).hexdigest())
                self.assertEqual(dest.read_bytes(),body)
                self.assertFalse(calls[0]['use_cookies'])
                self.assertTrue(calls[0]['resume'])
                self.assertEqual(calls[0]['retries'],4)
                with self.assertRaisesRegex(ValueError,'SHA256 mismatch'):
                    inputs.download_file('https://drive.google.com/file/d/game/view',dest,'0'*64)
                self.assertEqual(dest.read_bytes(),body)
                self.assertFalse(dest.with_suffix('.archive.part').exists())

    def test_downloader_errors_do_not_expose_input_urls(self):
        url='https://drive.google.com/file/d/private/view?resourcekey=secret'
        def fail(**kwargs):raise OSError(url)
        with tempfile.TemporaryDirectory() as temp, patch.dict(sys.modules,gdown=types.SimpleNamespace(download=fail)):
            with self.assertRaises(RuntimeError) as exc:inputs.download_file(url,Path(temp)/'input')
            self.assertNotIn(url,str(exc.exception))
            self.assertNotIn('secret',str(exc.exception))

    def test_direct_checksum_download_is_bounded_before_consuming_a_large_file(self):
        response=io.BytesIO(b'huge')
        response.headers={'Content-Type':'application/octet-stream','Content-Length':'1000000000'}
        with tempfile.TemporaryDirectory() as temp, patch.object(ci.urllib.request,'urlopen',return_value=response), patch.object(response,'read',wraps=response.read) as read:
            with self.assertRaisesRegex(ValueError,'too large'):
                inputs.download_file('https://storage.invalid/sums',Path(temp)/'sums',max_bytes=65536)
            read.assert_not_called()

    def test_named_prepared_secret_uses_the_same_json_and_checksum_validation(self):
        value = {'url': 'https://storage.invalid/prepared.zip', 'sha256': 'a' * 64}
        with patch.dict(os.environ, PREPARED_INPUT=json.dumps(value)):
            self.assertEqual(inputs.settings('PREPARED_INPUT'), (value['url'], value['sha256']))
        with patch.dict(os.environ, PREPARED_INPUT='bad JSON'):
            with self.assertRaisesRegex(ValueError, 'PREPARED_INPUT'):
                inputs.settings('PREPARED_INPUT')

    def test_private_asset_credentials_are_used_only_for_the_callers_repository(self):
        content = b'private prepared package'
        def fetch(args, stdout=None, **kwargs):
            self.assertEqual(args[0:2], ['gh', 'api'])
            stdout.write(content)
            return types.SimpleNamespace(returncode=0)
        import subprocess
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, GITHUB_REPOSITORY='owner/repo'), patch.object(subprocess, 'run', side_effect=fetch) as gh, patch.object(ci, 'download') as generic:
            dest = Path(temporary) / 'package'
            inputs.download_file('https://api.github.com/repos/owner/repo/releases/assets/123', dest, hashlib.sha256(content).hexdigest())
            self.assertEqual(dest.read_bytes(), content)
            self.assertEqual(gh.call_count, 1)
            inputs.download_file('https://api.github.com/repos/other/repo/releases/assets/123', dest)
            self.assertEqual(gh.call_count, 1)
            generic.assert_called_once()


if __name__=='__main__':unittest.main()
