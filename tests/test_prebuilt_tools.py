import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import prebuilt_tools as tools
import publish_tools


class PrebuiltToolTests(unittest.TestCase):
    def spec(self, kind='spirv'):
        return tools.recipe(kind, {'spirv_commit': 'a' * 40}, Path('/missing'), '10.0.100')

    def package(self, root, spec):
        root = Path(root)
        (root / 'bin').mkdir(parents=True)
        (root / 'licenses').mkdir()
        (root / 'bin/spirv-cross').write_bytes(b'open source executable')
        (root / 'bin/spirv-cross').chmod(0o755)
        (root / 'licenses/LICENSE.txt').write_text('notice')
        files = {p.relative_to(root).as_posix(): tools.sha(p) for p in root.rglob('*') if p.is_file()}
        (root / 'manifest.json').write_text(json.dumps({'identity': tools.identity(spec), 'recipe': spec, 'files': files}))

    def test_program_inputs_and_app_versions_do_not_select_a_tool_package(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            p = root / 'dm/gfx/tools/dmsh_xlate/Program.cs'
            p.parent.mkdir(parents=True); p.write_text('translator')
            first = tools.recipe('xlate', {}, root, '10.0.100')
            for name in ('dm/host/audio.c', 'ExeFS/main', 'RomFS/data/game.data',
                         'dm/gfx/tools/dmsh_xlate/bin/generated.dll'):
                path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('game')
            self.assertEqual(first, tools.recipe('xlate', {'build_label': 'v9'}, root, '10.0.100'))
            self.assertNotEqual(first, tools.recipe('xlate', {}, root, '10.0.101'))
            p.write_text('new translator')
            self.assertNotEqual(first, tools.recipe('xlate', {}, root, '10.0.100'))

    def test_game_payload_cannot_be_added_even_with_a_valid_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); spec = self.spec(); self.package(root, spec)
            tools.validate(root, spec)
            p = root / 'RomFS/data/game.data'; p.parent.mkdir(parents=True); p.write_text('game')
            manifest = json.loads((root / 'manifest.json').read_text())
            manifest['files']['RomFS/data/game.data'] = tools.sha(p)
            (root / 'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'allowlist'):
                tools.validate(root, spec)

    def test_cached_package_is_verified_and_corruption_is_not_reused(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(tools, 'ROOT', Path(temp)):
            spec = {'kind': 'spirv', 'schema': 1}
            cache = tools.ROOT / '.tools/packages' / tools.tag(spec)
            self.package(cache, spec)
            with patch.object(tools, 'restore') as restore, patch.object(tools, 'build') as build:
                tools.ensure(spec)
                restore.assert_not_called(); build.assert_not_called()
            (cache / 'bin/spirv-cross').write_bytes(b'corrupt')
            with patch.object(tools, 'restore', side_effect=OSError('offline')), patch.object(tools, 'build', side_effect=lambda dest, s:self.package(dest,s)) as build:
                tools.ensure(spec)
                build.assert_called_once()
            self.assertEqual((tools.ROOT / '.tools/bin/spirv-cross').read_bytes(), b'open source executable')

    def test_absent_prebuild_compiles_locally_and_warm_run_reuses_it(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(tools, 'ROOT', Path(temp)):
            spec = {'kind': 'spirv', 'schema': 1}
            with patch.object(tools, 'restore', side_effect=ValueError('bad checksum')), patch.object(tools, 'build', side_effect=lambda dest,s:self.package(dest,s)) as build:
                tools.ensure(spec); tools.ensure(spec)
                build.assert_called_once()

    def test_download_smoke_test_cannot_silently_fall_back_to_compiling(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(tools, 'ROOT', Path(temp)):
            with patch.object(tools, 'restore', side_effect=OSError('offline')), patch.object(tools, 'build') as build:
                with self.assertRaises(OSError):
                    tools.ensure({'kind': 'spirv', 'schema': 1}, require_prebuilt=True)
                build.assert_not_called()

    def test_public_release_checksum_is_checked_before_extraction(self):
        spec = self.spec()
        asset = {'name': 'tool.tar.gz', 'digest': 'sha256:' + '0' * 64,
                 'browser_download_url': f'https://github.com/{tools.REPOSITORY}/releases/download/{tools.tag(spec)}/tool.tar.gz'}
        responses = [io.BytesIO(json.dumps({'draft': False, 'tag_name': tools.tag(spec), 'assets': [asset]}).encode()), io.BytesIO(b'corrupt')]
        with tempfile.TemporaryDirectory() as temp, patch.object(tools, 'request', side_effect=responses):
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                tools.restore(temp, spec)
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_verified_prebuild_is_installed_without_compiling_and_keeps_licenses(self):
        spec = self.spec()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.package(root / 'source', spec)
            archive = root / 'tool.tar.gz'
            with tarfile.open(archive, 'w:gz') as tf:
                for p in (root / 'source').rglob('*'):
                    if p.is_file(): tf.add(p, arcname=p.relative_to(root / 'source').as_posix())
            asset = {'name': 'tool.tar.gz', 'digest': 'sha256:' + tools.sha(archive),
                     'browser_download_url': f'https://github.com/{tools.REPOSITORY}/releases/download/{tools.tag(spec)}/tool.tar.gz'}
            responses = [io.BytesIO(json.dumps({'draft': False, 'tag_name': tools.tag(spec), 'assets': [asset]}).encode()), io.BytesIO(archive.read_bytes())]
            with patch.object(tools, 'ROOT', root / 'caller'), patch.object(tools, 'request', side_effect=responses), patch.object(tools, 'build') as build:
                tools.ensure(spec)
                build.assert_not_called()
                self.assertTrue((tools.ROOT / '.tools/bin/spirv-cross').stat().st_mode & 0o111)
                self.assertTrue((tools.ROOT / '.tools/packages' / tools.tag(spec) / 'licenses/LICENSE.txt').is_file())

    def test_restore_rejects_links_traversal_and_duplicate_entries(self):
        spec = self.spec()
        for names, link in ((['../escaped'], False), (['licenses/link'], True), (['manifest.json', 'manifest.json'], False)):
            with self.subTest(names=names, link=link), tempfile.TemporaryDirectory() as temp:
                archive = Path(temp) / 'source.tar.gz'
                with tarfile.open(archive, 'w:gz') as tf:
                    for name in names:
                        item = tarfile.TarInfo(name)
                        if link:
                            item.type = tarfile.SYMTYPE; item.linkname = '/etc/passwd'
                            tf.addfile(item)
                        else:
                            item.size = 2; tf.addfile(item, io.BytesIO(b'{}'))
                asset = {'name': 'tool.tar.gz', 'digest': 'sha256:' + tools.sha(archive),
                         'browser_download_url': f'https://github.com/{tools.REPOSITORY}/releases/download/{tools.tag(spec)}/tool.tar.gz'}
                responses = [io.BytesIO(json.dumps({'draft': False, 'tag_name': tools.tag(spec), 'assets': [asset]}).encode()), io.BytesIO(archive.read_bytes())]
                with patch.object(tools, 'request', side_effect=responses), self.assertRaisesRegex(ValueError, 'Unsafe'):
                    tools.restore(Path(temp) / 'extracted', spec)

    def license_fixture(self, root, expression='MIT'):
        entries = {'upstream/LICENSE': 'upstream notice', 'dotnet/LICENSE.txt': 'dotnet notice',
                   'dotnet/ThirdPartyNotices.txt': 'dotnet third parties',
                   'package/dmsh_xlate/Used.dll': 'library',
                   'nuget/used/1.0/used.nuspec': f'<package><metadata><license type="expression">{expression}</license><copyright>Author</copyright></metadata></package>',
                   'nuget/used/1.0/THIRD-PARTY-NOTICES.txt': 'dependency notice',
                   'nuget/compile-only/1.0/compile-only.nuspec': '<package><metadata/></package>'}
        for name, value in entries.items():
            p=root/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(value)
        assets = {'packageFolders': {str(root/'nuget'): {}}, 'libraries': {
            'Used/1.0': {'type': 'package', 'path': 'used/1.0'},
            'CompileOnly/1.0': {'type': 'package', 'path': 'compile-only/1.0'}}}
        p=root/'upstream/dm/gfx/tools/dmsh_xlate/obj/project.assets.json'
        p.parent.mkdir(parents=True); p.write_text(json.dumps(assets))
        deps = {'targets': {'net10.0': {'Used/1.0': {'runtime': {'lib/net10.0/Used.dll': {}}},
                                        'CompileOnly/1.0': {'compile': {'ref/Reference.dll': {}}}}}}
        (root/'package/dmsh_xlate/dmsh_xlate.deps.json').write_text(json.dumps(deps))

    def test_public_package_includes_notices_for_deployed_dependencies_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); self.license_fixture(root)
            with patch.object(tools, 'ROOT', root), patch.dict(tools.os.environ, DOTNET_ROOT=str(root/'dotnet')), patch.object(tools, 'request', return_value=io.BytesIO(b'MIT text')):
                tools.licenses(root/'package/licenses')
            target=root/'package/licenses/nuget/Used/1.0'
            self.assertEqual((target/'THIRD-PARTY-NOTICES.txt').read_text(), 'dependency notice')
            self.assertIn('Author', (target/'used.nuspec').read_text())
            self.assertFalse((root/'package/licenses/nuget/CompileOnly').exists())

    def test_unreviewed_runtime_license_stops_public_package(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); self.license_fixture(root, 'LicenseRef-Unknown')
            with patch.object(tools, 'ROOT', root), patch.dict(tools.os.environ, DOTNET_ROOT=str(root/'dotnet')):
                with self.assertRaisesRegex(ValueError, 'Review NuGet license'):
                    tools.licenses(root/'package/licenses')


if __name__ == '__main__':
    unittest.main()
