import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import ci
import cache_keys
import legacy_batches
import publish_release
from source import prepare, stages
from test_resource_reuse import manifest


class PipelineCacheTests(unittest.TestCase):
    def test_dependency_closure_ignores_native_build_helpers_but_tracks_generators_and_layouts(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            files={'dm/ios/tools/gen_assets.py':"STEPS = [('art', ['gen_image.py'])]\n",
                   'dm/ios/tools/gen_image.py':'import image_helper\n',
                   'dm/ios/tools/image_helper.py':'value=1\n',
                   'dm/ios/tools/project_free.py':'native project',
                   'dm/tools/patch_nso.py':'import struct\n',
                   'dm/tools/astc_pack.py':'texture converter',
                   'dm/data/layout.json':'original layout'}
            for name,value in files.items():
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value)
            config=dict(ci.CONFIG,nso_sha256={'main':'a'*64})
            first=cache_keys.generation_keys(root,config)
            (root/'dm/ios/tools/project_free.py').write_text('new native helper')
            (root/'dm/tools/astc_pack.py').write_text('new converter')
            self.assertEqual(first,cache_keys.generation_keys(root,config))
            (root/'dm/ios/tools/image_helper.py').write_text('value=2\n')
            second=cache_keys.generation_keys(root,config)
            self.assertNotEqual(first['assets'],second['assets'])
            self.assertEqual(first['rewrite'],second['rewrite'])
            (root/'dm/data/layout.json').write_text('fixed layout')
            self.assertNotEqual(second['assets'],cache_keys.generation_keys(root,config)['assets'])

    def test_completed_stage_receipt_detects_missing_or_modified_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);file=root/'out.bin';file.write_bytes(b'generated')
            receipt=root/'receipt.json'
            stages.receipt(receipt,'key',[file],save=True)
            self.assertTrue(stages.receipt(receipt,'key',[file]))
            self.assertFalse(stages.receipt(receipt,'other-key',[file]))
            file.write_bytes(b'corrupt')
            self.assertFalse(stages.receipt(receipt,'key',[file]))
            file.unlink()
            self.assertFalse(stages.receipt(receipt,'key',[file]))

    def test_payload_reuse_keeps_current_native_sources_and_new_run_context_without_game_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);dm=root/'upstream/dm';dm.mkdir(parents=True)
            (dm/'PRODUCT').write_text('r44');(dm/'runtime.c').write_text('runtime v1')
            cache=root/'work/build/payload-cache';cache.mkdir(parents=True)
            (cache/'source-payload.zip').write_bytes(b'validated common payload')
            files={'source-payload.zip':ci.sha256(cache/'source-payload.zip')}
            for name in prepare.GENERATED:
                p=cache/'generated'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('generated data')
                files['generated/'+name]=ci.sha256(p)
            (cache/'receipt.json').write_text(json.dumps({'key':'payload-key','files':files,'chain':'chain','product':'r44','shader_source_sha16':'shader-digest'}))
            pack=root/'pack';pack.mkdir();(pack/'pack.json').write_text('{}')
            env={'PAYLOAD_KEY':'payload-key','D2RM_ASTC_PACK':str(pack),'SOURCE_REPOSITORY':'owner/source'}
            def run(*args,**kwargs):
                if 'dmsh_chain.py' in str(args[-1]):return 'chain'
                if args[0]=='git':return 'a'*40
                return ''
            with patch.object(ci,'ROOT',root),patch.object(ci,'DM',root/'work'),patch.object(prepare,'CACHE',cache),patch.dict(os.environ,env),patch.object(prepare,'run',side_effect=run),patch.object(prepare,'generate_payload') as generate:
                for number in ('7.1','7.2'):
                    (dm/'runtime.c').write_text('runtime '+number)
                    with patch.dict(ci.CONFIG,build_number=number):prepare.main()
                    self.assertEqual(json.loads((root/'outputs/build-context.json').read_text())['build_number'],number)
                    with tarfile.open(root/'outputs/native-inputs.tar.gz') as tf:
                        self.assertEqual(tf.extractfile('upstream/dm/runtime.c').read().decode(),'runtime '+number)
                    self.assertTrue(json.loads((root/'outputs/source-input-report.json').read_text())['payload_reused'])
                generate.assert_not_called()
                (cache/'source-payload.zip').write_bytes(b'corrupt')
                self.assertIsNone(prepare.cached_payload('payload-key'))

    def test_data_probe_reuses_release_without_reading_or_downloading_game_input(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'resource-manifest.json').write_text(json.dumps(manifest()))
            output=root/'step-output';ref={'resource_id':'existing','source_release':{'url':'https://github.com/owner/repo/releases/tag/data'}}
            with patch.object(publish_release,'OUT',root),patch.object(publish_release,'require_private',return_value='owner/repo'),patch.object(publish_release,'find_resources',return_value=ref),patch.object(publish_release,'write_install_guide'),patch.object(publish_release,'publish_resources') as create,patch.object(ci,'download') as download,patch.dict(os.environ,GITHUB_OUTPUT=str(output)):
                self.assertEqual(publish_release.probe_resources(),ref)
                create.assert_not_called();download.assert_not_called()
            self.assertIn('reused=true',output.read_text())

    def test_missing_conversion_worker_and_unsafe_paths_are_rejected(self):
        for name in ('../escape','/etc/passwd','files\\escape'):
            with self.assertRaises(ValueError):legacy_batches.safe_path(name)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'batch-plan.json').write_text(json.dumps({'index':0}))
            with self.assertRaisesRegex(ValueError,'Missing or duplicated'):
                legacy_batches.merge([root],root/'merged','recipe')


if __name__=='__main__':unittest.main()
