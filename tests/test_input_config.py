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


if __name__=='__main__':unittest.main()
