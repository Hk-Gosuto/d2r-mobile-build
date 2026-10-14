import json
from pathlib import Path
import plistlib
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import cache_keys
import ci
from source import native_cache


class BuildEfficiencyTests(unittest.TestCase):
    def test_native_cache_tracks_compiler_contents_and_ios_target_across_runner_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=root/'upstream/dm'; source.mkdir(parents=True)
            (source/'runtime.c').write_text('runtime')
            output=root/'outputs'; env=root/'env'
            compiler=root/'compiler'; compiler.mkdir()
            clang=compiler/'clang'; clangxx=compiler/'clang++'
            clang.write_bytes(b'compiler'); clangxx.write_bytes(b'compiler++')
            def command(args, **kwargs):
                if args[0]=='xcodebuild': return 'Xcode 26.6\nBuild version 17F113\n'
                if args[:2]==('xcrun','--find'): return str(compiler/args[2])+'\n'
                if args[0]=='xcrun': return '23F100\n'
                if args[0]=='ccache': return 'ccache version 4.14\nextra build information\n'
                self.fail('Unexpected compiler identification command: '+str(args))
            def configure(minimum):
                output.write_text(''); env.write_text('')
                native_cache.configure(root,minimum)
                return dict(line.split('=',1) for line in output.read_text().splitlines())
            with patch.dict(ci.os.environ,GITHUB_OUTPUT=str(output),GITHUB_ENV=str(env)),patch.object(native_cache.shutil,'which',return_value='ccache'),patch.object(native_cache.subprocess,'check_output',side_effect=command):
                first=configure('26.0')
                moved=root/'another-runner-path'; compiler.rename(moved); compiler=moved
                self.assertEqual(first,configure('26.0'))
                self.assertNotEqual(first['prefix'],configure('18.0')['prefix'])
                (compiler/'clang').write_bytes(b'new compiler')
                self.assertNotEqual(first['prefix'],configure('26.0')['prefix'])

    def setUp(self):
        runtime = patch.dict(ci.CONFIG, nso_sha256={'main': 'a' * 64})
        runtime.start(); self.addCleanup(runtime.stop)

    def test_runtime_only_changes_reuse_generation_but_generator_changes_invalidate_it(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            files={'dm/PRODUCT':'r44', 'dm/tools/patch_nso.py':'rewrite',
                   'dm/tools/dmx.py':'reader', 'dm/data/bootlist.tsv':'blocks',
                   'dm/ios/tools/gen_assets.py':'art generator',
                   'dm/ios/Sources/TouchArt/native_art_manifest.json':'frozen hashes',
                   'dm/ios/Sources/cloud_ios.m':'runtime', 'dm/host/hle_fs.c':'runtime'}
            for name,value in files.items():
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value)
            with patch.dict(ci.os.environ,INPUT_REVISION='input-one'):
                first=cache_keys.generation_keys(root,ci.CONFIG)
                (root/'dm/ios/Sources/cloud_ios.m').write_text('fixed sync')
                changed=dict(ci.CONFIG,upstream_commit='new',build_label='v1.0.99',
                             build_number='7.2',release_tag='v1.0.99-build.7.2')
                self.assertEqual(first,cache_keys.generation_keys(root,changed))
                (root/'dm/ios/tools/gen_assets.py').write_text('fixed generator')
                second=cache_keys.generation_keys(root,changed)
                self.assertNotEqual(first['assets'],second['assets'])
                self.assertEqual(first['rewrite'],second['rewrite'])
                (root/'dm/tools/patch_nso.py').write_text('new cuts')
                self.assertNotEqual(second['rewrite'],cache_keys.generation_keys(root,changed)['rewrite'])
                with patch.dict(ci.os.environ,INPUT_REVISION='input-two'):
                    self.assertNotEqual(second['assets'],cache_keys.generation_keys(root,changed)['assets'])

    def test_shader_cache_depends_on_shader_inputs_not_app_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entries = {'dm/gfx/tools/dmsh_chain.py': "FILES = ['tools/dmsh_chain.py', 'tools/kernel.py']\n",
                       'dm/gfx/tools/kernel.py':'shader generation',
                       'dm/gfx/tools/nometal_run.py':'no metal', 'dm/tools/dmx.py':'reader',
                       'dm/third_party/ryujinx/src/Shader.cs':'translator'}
            for name,data in entries.items():
                p=root/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(data)
            with patch.dict(ci.os.environ, {'INPUT_REVISION':'game-v1'}):
                first=cache_keys.keys(root,ci.CONFIG,'10.0.100')
                changed=dict(ci.CONFIG, upstream_commit='different', build_label='v1.0.20')
                self.assertEqual(first,cache_keys.keys(root,changed,'10.0.100'))
                self.assertNotEqual(first['shaders'],cache_keys.keys(root,changed,'10.0.101')['shaders'])
                (root/'dm/gfx/tools/kernel.py').write_text('changed generation')
                newer=cache_keys.keys(root,ci.CONFIG,'10.0.100')
                self.assertNotEqual(first['shaders'],newer['shaders'])
                self.assertEqual(first['tools'],newer['tools'])
                (root/'dm/third_party/ryujinx/src/Shader.cs').write_text('changed translator')
                self.assertNotEqual(newer['shaders'],cache_keys.keys(root,ci.CONFIG,'10.0.100')['shaders'])
                self.assertNotEqual(cache_keys.keys(root,ci.CONFIG,'10.0.100','toolchain-a')['shaders'],
                                    cache_keys.keys(root,ci.CONFIG,'10.0.100','toolchain-b')['shaders'])
                changed=dict(ci.CONFIG,spirv_commit='new compiler')
                self.assertNotEqual(first['tools'],cache_keys.keys(root,changed,'10.0.100')['tools'])
