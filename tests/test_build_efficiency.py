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


class BuildEfficiencyTests(unittest.TestCase):
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
