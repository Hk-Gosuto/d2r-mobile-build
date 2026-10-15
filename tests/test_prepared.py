import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import ci
from source import metal, prepared
import publish_release as publish
from test_metal import fixture as metal_fixture
from test_resource_reuse import manifest, FakeGitHub


def fixture(root):
    _, original, identity, dm = metal_fixture(root)
    (dm / 'PRODUCT').write_text('r44')
    chain_script = dm / 'gfx/tools/dmsh_chain.py'
    chain_script.write_text("FILES = ['tools/dmsh_chain.py', 'tools/dmsh_chain.lock']\n" + chain_script.read_text())
    config = dict(ci.CONFIG, nso_sha256={n: 'a' * 64 for n in ('main', 'sdk', 'subsdk0')},
                  upstream_commit='a' * 40, build_number='1.1')
    payload = root / 'outputs/source-payload.zip'
    with zipfile.ZipFile(payload, 'a') as z:
        z.writestr(metal.BASE + 'Frameworks/Guest.framework/Guest', bytes.fromhex('cffaedfe0c000001') + b'fixture')
        z.writestr(metal.BASE + 'romfs_overlay_astc/pack.json', json.dumps({'name': 'fixture.data', 'sha256': 'a' * 64}))
    original['payload_sha256'] = ci.sha256(payload)
    prepared.write(root / 'outputs/source-input-report.json', original)
    plan = prepared.read(root / 'outputs/metal-plan.json')
    plan['input_sha256'] = original['payload_sha256']
    prepared.write(root / 'outputs/metal-plan.json', plan)
    def compile_fn(src, air, output):
        Path(output).write_bytes(b'MTLB' + Path(src).read_bytes())
    ios = types.SimpleNamespace(RECORD='ios flags', compile=compile_fn)
    with patch.object(metal, 'toolchain', return_value=(identity, ios)):
        metal.compile_payload(root, root / 'metal-cache')
    report = prepared.read(root / 'outputs/source-input-report.json')
    report.update(input_identity='c' * 64, source_commit='a' * 40, tools_commit='b' * 40,
                  shader_source_sha16='d' * 16, legacy_pack={'name': 'fixture.data', 'sha256': 'a' * 64})
    prepared.write(root / 'outputs/source-input-report.json', report)
    for name in prepared.GENERATED:
        path = dm / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('generated fixture')
    (dm / 'runtime.c').write_text('initial runtime')
    (dm / 'ios/tools').mkdir(exist_ok=True)
    (dm / 'ios/tools/shell_stubs.py').write_text('print("fixture stubs")\n')
    m = manifest()
    m['resource_id'] = prepared.export_resources.resource_identity(m)
    data = {k: m[k] for k in ('resource_id', 'game_version', 'switch_version', 'archive_count', 'resource_bytes')}
    data.update(source_release={'url': 'https://storage.invalid/data'}, zip_bytes=5, zip_sha256='a' * 64, assets=[])
    names = [f'D2R-Mobile-Resources.zip.{n:03d}' for n in range(1, 4)]
    names += ['Resources-SHA256SUMS.txt', 'Resources-Parts-SHA256SUMS.txt']
    for name, size in zip(names, (2, 2, 1, 10, 10)):
        data['assets'].append({'name': name, 'bytes': size, 'sha256': 'e' * 64, 'url': 'https://storage.invalid/' + name})
    legacy = {'recipe_id': 'f' * 64, 'pack': report['legacy_pack'],
              'source_release': {'url': 'https://drive.google.com/file/d/legacy/view'},
              'assets': [{'name': 'Legacy-Device-Pack.zip', 'bytes': 10, 'sha256': 'e' * 64,
                          'url': 'https://drive.google.com/file/d/legacy/view'}]}
    for name, value in (('resource-manifest.json', m), ('resources.json', data), ('legacy-resources.json', legacy)):
        prepared.write(root / 'outputs' / name, value)
    return config, m, report


class PreparedTests(unittest.TestCase):
    def test_export_and_consume_preserve_payload_but_use_fresh_runtime_and_run_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config, m, report = fixture(root)
            destination = root / '.prepared-downloads/prepared-input.archive'
            with patch.object(ci, 'CONFIG', config), patch.object(ci, 'resource_sizes', return_value={f['name']: f['bytes'] for f in m['files']}):
                prepared.export(root, root / 'outputs/source-payload.zip', root / 'outputs/source-input-report.json', root / 'outputs', destination)
                original = (root / 'outputs/source-payload.zip').read_bytes()
                for number in ('7.1', '7.2'):
                    config.update(upstream_commit='e' * 40, build_number=number)
                    (root / 'upstream/dm/runtime.c').write_text('latest runtime ' + number)
                    prepared.write(root / 'outputs/build-context.json', config)
                    with patch.dict(os.environ, SOURCE_REPOSITORY='owner/fork', INPUT_REVISION='f' * 64, TOOLS_COMMIT='9' * 40):
                        prepared.prepare(root)
                    current = prepared.read(root / 'outputs/source-input-report.json')
                    self.assertEqual(current['source_commit'], 'e' * 40)
                    self.assertEqual(current['source_repository'], 'owner/fork')
                    self.assertEqual(current['tools_commit'], '9' * 40)
                    self.assertEqual(current['prepared_from_source'], 'a' * 40)
                    self.assertEqual(current['metal_compiled_count'], 0)
                    self.assertEqual(current['metal_cache_hits'], 2)
                    self.assertNotIn('build_number', current)
                    self.assertEqual((root / 'outputs/source-payload.zip').read_bytes(), original)
                    self.assertEqual(prepared.read(root / 'outputs/build-context.json')['build_number'], number)
                    with tarfile.open(root / 'outputs/native-inputs.tar.gz') as tf:
                        self.assertEqual(tf.extractfile('upstream/dm/runtime.c').read().decode(), 'latest runtime ' + number)
                self.assertFalse(ci.GAME.exists())

    def test_generator_changes_require_a_new_package_and_never_silently_use_old_art(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config, m, _ = fixture(root)
            with patch.object(ci, 'CONFIG', config), patch.object(ci, 'resource_sizes', return_value={f['name']: f['bytes'] for f in m['files']}):
                destination = root / 'prepared.zip'
                prepared.export(root, root / 'outputs/source-payload.zip', root / 'outputs/source-input-report.json', root / 'outputs', destination)
                directory = root / 'expanded'; prepared.extract(destination, directory)
                info = prepared.verify_directory(directory)
                generator = root / 'upstream/dm/tools/patch_nso.py'
                generator.parent.mkdir(exist_ok=True); generator.write_text('new_rewrite_rules = True\n')
                with self.assertRaisesRegex(ValueError, 'updated prepared package'):
                    prepared.verify_source(directory, info, root / 'upstream', config)
                with self.assertRaisesRegex(ValueError, 'nso_sha256'):
                    prepared.verify_source(directory, info, root / 'upstream', dict(config, nso_sha256={'main': '0' * 64}))

    def test_missing_modified_and_extra_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config, m, _ = fixture(root)
            with patch.object(ci, 'CONFIG', config), patch.object(ci, 'resource_sizes', return_value={f['name']: f['bytes'] for f in m['files']}):
                destination = root / 'prepared.zip'
                prepared.export(root, root / 'outputs/source-payload.zip', root / 'outputs/source-input-report.json', root / 'outputs', destination)
            for operation in ('missing', 'modified', 'extra'):
                directory = root / operation; prepared.extract(destination, directory)
                if operation == 'missing': (directory / 'source-payload.zip').unlink()
                if operation == 'modified': (directory / 'source-payload.zip').write_bytes(b'corrupt')
                if operation == 'extra': (directory / 'runtime.c').write_text('replace the real runtime')
                with self.assertRaises(ValueError): prepared.verify_directory(directory)

    def test_resource_links_must_describe_complete_matching_data_and_legacy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, m, report = fixture(root)
            data = prepared.read(root / 'outputs/resources.json')
            legacy = prepared.read(root / 'outputs/legacy-resources.json')
            prepared.verify_references(m, data, legacy, report['legacy_pack'])
            invalid = copy.deepcopy(data); invalid['assets'].pop(0)
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                prepared.verify_references(m, invalid, legacy, report['legacy_pack'])
            invalid = copy.deepcopy(data); invalid['resource_id'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'resource manifest'):
                prepared.verify_references(m, invalid, legacy, report['legacy_pack'])
            invalid = copy.deepcopy(legacy); invalid['pack'] = {'name': 'different'}
            with self.assertRaisesRegex(ValueError, 'Legacy reference'):
                prepared.verify_references(m, data, invalid, report['legacy_pack'])
            invalid = copy.deepcopy(data); invalid['assets'][0]['url'] = 'http://unsafe.invalid/data'
            with self.assertRaisesRegex(ValueError, 'HTTPS'):
                prepared.verify_references(m, invalid, legacy, report['legacy_pack'])

    def test_archive_paths_cannot_escape_and_completed_download_is_preserved_on_bad_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); archive = root / '.prepared-downloads/prepared-input.archive'
            archive.parent.mkdir()
            with zipfile.ZipFile(archive, 'w') as z: z.writestr('../escape', b'unsafe')
            before = archive.read_bytes()
            with self.assertRaisesRegex(ValueError, 'Unsafe archive'):
                prepared.prepare(root)
            self.assertEqual(archive.read_bytes(), before)
            self.assertFalse((root / 'escape').exists())

    def test_download_cache_is_verified_by_bytes_and_not_source_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); content = b'prepared fixture'
            digest = hashlib.sha256(content).hexdigest()
            def fetch(url, destination, *args, **kwargs):
                destination.parent.mkdir(parents=True, exist_ok=True); destination.write_bytes(content)
            with patch.object(prepared, 'settings', return_value=('https://storage.invalid/prepared.zip', digest)), patch.object(prepared, 'download_file', side_effect=fetch) as download:
                prepared.download(root); prepared.download(root)
                self.assertEqual(download.call_count, 1)
                (root / '.prepared-downloads/prepared-input.archive').write_bytes(b'corrupted')
                prepared.download(root)
                self.assertEqual(download.call_count, 2)

    def test_publish_uses_bound_external_resource_links_without_fetching_or_republishing_resources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config, m, report = fixture(root)
            config.update(build_label='v1.0.15', release_tag='v1.0.15-build.7.1',
                          app_version='1.0.15', build_number='7.1')
            output, stage = root / 'outputs', root / 'release'
            report.update(prepared_input=True, game_version=config['game_version'],
                          switch_version=config['switch_version'], upstream_commit=config['upstream_commit'],
                          input_revision='f' * 64,
                          prepared_metadata_sha256={n: ci.sha256(output / n) for n in
                              ('resource-manifest.json', 'resources.json', 'legacy-resources.json')})
            packages = []
            for name, minimum in zip(ci.ipa_names(config), ('26.0', '18.0')):
                (output / name).write_bytes(b'fixture IPA')
                packages.append(dict(report, ipa_name=name, minimum_os=minimum,
                    ipa_bytes=(output / name).stat().st_size, ipa_sha256=ci.sha256(output / name),
                    native_built_from_source=True, payload_verified=True,
                    **{k: config[k] for k in ('app_version', 'build_number', 'release_tag')}))
            prepared.write(output / 'build-report.json', dict(report, packages=packages))
            (output / 'SHA256SUMS.txt').write_text(''.join(f"{p['ipa_sha256']}  {p['ipa_name']}\n" for p in packages))
            store = FakeGitHub()
            with patch.object(ci, 'CONFIG', config), patch.object(publish, 'OUT', output), patch.object(publish, 'STAGE', stage), patch.object(publish, 'require_private', return_value=store.repo), patch.object(publish, 'gh', side_effect=store.gh), patch.object(publish, 'release_info', side_effect=lambda repo, tag: store.releases.get(tag)), patch.object(publish, 'api', side_effect=AssertionError('Resource API access forbidden')), patch.dict(os.environ, INPUT_REVISION='f' * 64, GITHUB_SHA='a' * 40, GITHUB_STEP_SUMMARY=''):
                release = publish.main('ipa')
                self.assertEqual(release['tag_name'], config['release_tag'])
                self.assertFalse(any(a['name'].endswith(('.zip', '.001', '.002', '.003')) for a in release['assets']))
                self.assertIn('https://storage.invalid/data', (stage / 'RELEASE.md').read_text())
                data = prepared.read(output / 'resources.json')
                data['source_release']['url'] = 'https://other.invalid/data'
                prepared.write(output / 'resources.json', data)
                with self.assertRaisesRegex(ValueError, 'metadata changed'):
                    publish.main('ipa')


if __name__ == '__main__': unittest.main()
