import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
from source.compatibility import verify_generation
from source.romfs_input import create, restore
from fixtures import source


def key(offset):
    return (bytes(11) + offset.to_bytes(5, 'big')).hex()


class RuntimeInputTests(unittest.TestCase):
    def test_small_input_preserves_original_addresses_and_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = root / 'original.zip'
            rows = []
            for path, offset, size in (('data/global/ui/layouts/settings.json', 64, 8),
                                       ('data/hd/world/huge.texture', 80, 16)):
                rows.append(f'1|0|0|0|unused|{size}|{key(offset)}|{size}|n|data:{path}|0')
            manifest = '\n'.join(rows) + '\n'
            config = f'vfs-1 = unused {key(128)}\nvfs-1-size = 8 8\nvfs-root = unused {key(144)}\nvfs-root-size = 4 4\n'
            data = bytearray(1024 * 1024)
            data[64:72] = b'original'; data[80:96] = b'not needed large'; data[128:136] = b'tvfs-one'; data[144:148] = b'root'
            with zipfile.ZipFile(original, 'w', zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('Update/RomFS/data/build_manifest.psv', manifest)
                archive.writestr('Update/RomFS/data/.build.config', config)
                archive.writestr('Update/RomFS/data/00-00000000.data', data)
            package = root / 'inputs.zip'
            self.assertEqual(create(original, package), 20)
            romfs = restore(package, root / 'RomFS')
            self.assertEqual((romfs / 'data/build_manifest.psv').read_text(), manifest)
            self.assertEqual((romfs / 'data/.build.config').read_text(), config)
            with (romfs / 'data/00-00000000.data').open('rb') as stream:
                stream.seek(64); self.assertEqual(stream.read(8), b'original')
                stream.seek(80); self.assertEqual(stream.read(16), bytes(16))
                stream.seek(128); self.assertEqual(stream.read(8), b'tvfs-one')
                stream.seek(144); self.assertEqual(stream.read(4), b'root')
            self.assertLess(package.stat().st_size, 2048)
            self.assertEqual((romfs / 'data/00-00000000.data').stat().st_size, len(data))

    def test_invalid_range_index_cannot_write_outside_resource_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / 'bad.zip'
            with zipfile.ZipFile(archive, 'w') as output:
                output.writestr('ranges.json', json.dumps({'sizes': {'../escape': 8}, 'ranges': {}}))
            with self.assertRaisesRegex(ValueError, 'Invalid original resource'):
                restore(archive, root / 'RomFS')
            self.assertFalse((root / 'escape').exists())

    def test_ui_updates_reuse_heavy_outputs_but_game_rewrite_changes_do_not(self):
        with tempfile.TemporaryDirectory() as temporary:
            upstream, commit, _, _ = source(Path(temporary))
            path = upstream / 'dm/ios/tools/touch_layout.py'
            path.write_text('new_quality_setting = True\n')
            verify_generation(upstream, commit, heavy=True)
            (upstream / 'dm/tools/helper.py').write_text('changed_program_rewrite = True\n')
            with self.assertRaisesRegex(ValueError, 'updated prepared package'):
                verify_generation(upstream, commit, heavy=True)
