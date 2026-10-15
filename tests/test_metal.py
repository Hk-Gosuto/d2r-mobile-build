import hashlib
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
from source import metal


def fixture(root):
    out = root / 'outputs'; out.mkdir()
    dm = root / 'upstream/dm'
    tools = dm / 'gfx/tools'; tools.mkdir(parents=True)
    (dm / 'gfx/nvn').mkdir()
    (tools / 'dmsh_chain.lock').write_text('translator\tfrozen\nmetal_macosx\tnone\nmetal_iphoneos\tnone\n')
    (tools / 'dmsh_chain.py').write_text('''import hashlib,pathlib
p=pathlib.Path(__file__).parent
chain=hashlib.sha256((p/'dmsh_chain.lock').read_bytes()).hexdigest()[:12]
(p.parent/'nvn/dmsh_chain.h').write_text('#define DMSH_CHAIN "'+chain+'"\\n')
print(chain)
''')
    chain = 'a' * 12
    prefix = metal.BASE + 'msl/b-' + chain + '/'
    entries = {metal.BASE + 'Info.plist': b'original plist',
               metal.BASE + 'dm/shell_info.txt': f'PRODUCT=r44\nCHAIN={chain}\nKIND=ios\n'.encode(),
               metal.BASE + 'dm/shell_manifest.txt': f'msl/b-{chain}/\ndm/derived.tsv\n'.encode(),
               metal.BASE + 'dm/c1_full.tsv': f'# chain b-{chain} timestamp\nshader-key\n'.encode(),
               metal.BASE + 'dm/derived.tsv': b'unchanged game table',
               prefix + 'one_b.metallib': b'first shader', prefix + 'one_bf.metallib': b'first shader',
               prefix + 'two_b.metallib': b'second shader'}
    for key in ('one', 'two'):
        entries[prefix + key + '_b.json'] = json.dumps({'chain': chain, 'chain_metal': 'ios flags', 'entry': 'shader_entry', 'bindings': [1, 2]}).encode()
    with zipfile.ZipFile(out / 'source-payload.zip', 'w') as z:
        for name, data in entries.items(): z.writestr(name, data)
    identity = {'metal': 'Apple Metal fixture', 'compile_record': 'ios flags'}
    family = metal.digest(json.dumps(identity, sort_keys=True).encode())
    report = {'shader_chain': chain, 'product': 'r44', 'payload_sha256': metal.ci.sha256(out / 'source-payload.zip')}
    (out / 'source-input-report.json').write_text(json.dumps(report))
    (out / 'metal-plan.json').write_text(json.dumps({'toolchain': identity, 'family': family, 'input_sha256': report['payload_sha256']}))
    return entries, report, identity, dm


class MetalTests(unittest.TestCase):
    def test_object_cache_checks_source_toolchain_and_binary_digest(self):
        calls = []
        def compile_fn(src, air, output):
            calls.append(Path(src).read_bytes()); Path(output).write_bytes(b'MTLB' + calls[-1])
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            first = metal.compile_object(b'shader', 'compiler-one', cache, compile_fn)
            self.assertEqual(first, (b'MTLBshader', False))
            self.assertEqual(metal.compile_object(b'shader', 'compiler-one', cache, compile_fn), (b'MTLBshader', True))
            self.assertEqual(len(calls), 1)
            library = next(cache.glob('objects/*/library.metallib')); library.write_bytes(b'MTLBcorrupt')
            self.assertFalse(metal.compile_object(b'shader', 'compiler-one', cache, compile_fn)[1])
            self.assertFalse(metal.compile_object(b'changed shader', 'compiler-one', cache, compile_fn)[1])
            self.assertFalse(metal.compile_object(b'shader', 'compiler-two', cache, compile_fn)[1])
            self.assertEqual(len(calls), 4)

    def test_failed_or_nonbinary_output_cannot_be_cached(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            def bad(src, air, output): Path(output).write_bytes(b'source, not a library')
            with self.assertRaisesRegex(ValueError, 'binary library'):
                metal.compile_object(b'shader', 'compiler', cache, bad)
            self.assertFalse(list(cache.glob('objects/*/receipt.json')))
            self.assertFalse(list(cache.glob('compile-*')))

    def test_full_precompile_preserves_payload_and_synchronizes_all_chain_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            entries, original, identity, dm = fixture(root)
            payload = root / 'outputs/source-payload.zip'; translated = payload.read_bytes()
            calls = []
            def compile_fn(src, air, output):
                calls.append(Path(src).read_bytes()); Path(output).write_bytes(b'MTLB' + calls[-1])
            ios = types.SimpleNamespace(RECORD='ios flags', compile=compile_fn)
            with patch.object(metal, 'toolchain', return_value=(identity, ios)):
                for run in ('first', 'second'):
                    payload.write_bytes(translated)
                    (root / 'outputs/source-input-report.json').write_text(json.dumps(original))
                    (dm / 'runtime.c').write_text(run)
                    metal.compile_payload(root, root / 'cache')
                    report = json.loads((root / 'outputs/source-input-report.json').read_text())
                    self.assertTrue(report['metal_precompiled'])
                    self.assertFalse(report['phone_shader_compilation_required'])
                    self.assertEqual(report['metal_libraries'], 3)
                    self.assertEqual(report['metal_unique_libraries'], 2)
                    self.assertEqual(report['metal_compiled_count'], 2 if run == 'first' else 0)
                    self.assertEqual(report['metal_cache_hits'], 0 if run == 'first' else 2)
                    self.assertEqual(len(calls), 2)
                    self.assertNotEqual(report['shader_chain'], original['shader_chain'])
                    self.assertIn(report['shader_chain'], (dm / 'gfx/nvn/dmsh_chain.h').read_text())
                    with zipfile.ZipFile(payload) as z:
                        for name in ('Info.plist', 'dm/derived.tsv'):
                            self.assertEqual(z.read(metal.BASE + name), entries[metal.BASE + name])
                        reflection = json.loads(z.read(metal.BASE + 'msl/b-' + report['shader_chain'] + '/one_b.json'))
                        self.assertEqual(reflection['bindings'], [1, 2])
                    with tarfile.open(root / 'outputs/native-inputs.tar.gz') as tf:
                        self.assertEqual(tf.extractfile('upstream/dm/runtime.c').read().decode(), run)
                        self.assertIn(report['shader_chain'].encode(), tf.extractfile('upstream/dm/gfx/nvn/dmsh_chain.h').read())
                    metal.verify_payload(payload, report)

    def test_final_verification_rejects_source_shader_missing_library_and_stale_reflection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            entries, report, identity, _ = fixture(root)
            chain = report['shader_chain']
            report.update(metal_precompiled=True, metal_libraries=3, metal_toolchain=identity)
            compiled = {n: b'MTLB' + b for n, b in entries.items() if n.endswith('.metallib')}
            destination = root / 'compiled.zip'
            metal.rewrite_payload(root / 'outputs/source-payload.zip', destination, report, compiled, chain, 'ios flags')
            metal.verify_payload(destination, report)
            with zipfile.ZipFile(destination) as z: good = {n: z.read(n) for n in z.namelist()}
            library = next(n for n in good if n.endswith('_b.metallib'))
            reflection = library.removesuffix('.metallib') + '.json'
            for name, value in ((library, b'not compiled'), (library, None),
                                (reflection, json.dumps({'chain': 'stale', 'chain_metal': 'ios flags'}).encode())):
                bad = dict(good)
                if value is None: bad.pop(name)
                else: bad[name] = value
                with zipfile.ZipFile(destination, 'w') as z:
                    for n, b in bad.items(): z.writestr(n, b)
                with self.assertRaises(ValueError): metal.verify_payload(destination, report)


if __name__ == '__main__': unittest.main()
