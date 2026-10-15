"""Portable, verified game payloads; native runtime sources always come from the selected ref."""
import argparse
import ast
import contextlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ci
import cache_keys
import export_resources
from archive_input import extract as extract_archive
from input_config import download_file, https_url, input_identity, settings
from repository_access import require_private
from source.metal import verify_payload
from source.prepare import GENERATED

FORMAT = 'd2r-mobile-prepared'
FILES = {'source-payload.zip', 'shader-chain.lock', 'resource-manifest.json',
         'resources.json', 'legacy-resources.json', *('generated/' + p for p in GENERATED)}
MAX_PACKAGE_BYTES = 2 * 1024**3


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def extract(archive, target):
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            sizes = [(i.filename, i.file_size) for i in z.infolist() if not i.is_dir()]
    elif tarfile.is_tarfile(archive):
        with tarfile.open(archive) as tf:
            sizes = [(i.name, i.size) for i in tf.getmembers() if not i.isdir()]
    else:
        raise ValueError('Expected a ZIP, tar.gz or tar.xz prepared package')
    if len(sizes) > 32 or sum(size for _, size in sizes) > MAX_PACKAGE_BYTES:
        raise ValueError('Prepared package exceeds the supported extracted size')
    if any(Path(name).name == 'prepared.json' and size > 1024**2 for name, size in sizes):
        raise ValueError('Prepared manifest is too large')
    extract_archive(archive, target)


@contextlib.contextmanager
def original_input(identity):
    old = os.environ.get('INPUT_REVISION')
    os.environ['INPUT_REVISION'] = identity
    try:
        yield
    finally:
        if old is None:
            os.environ.pop('INPUT_REVISION', None)
        else:
            os.environ['INPUT_REVISION'] = old


def compatibility(upstream, config, identity, source_chain):
    """Track generation dependencies, allowing unrelated runtime/source-version changes."""
    upstream = Path(upstream)
    chain_script = upstream / 'dm/gfx/tools/dmsh_chain.py'
    tree = ast.parse(chain_script.read_text())
    values = [n for n in tree.body if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == 'FILES' for t in n.targets)]
    if len(values) != 1:
        raise ValueError('Cannot determine upstream shader generation dependencies')
    files = {}
    for name in ast.literal_eval(values[0].value):
        path = (upstream / 'dm/gfx' / name).resolve()
        if not path.is_relative_to(upstream.resolve()):
            raise ValueError('Shader generation dependency escapes upstream')
        if path.name != 'dmsh_chain.lock':
            files[path.relative_to(upstream.resolve()).as_posix()] = path
    files.update(cache_keys.collect(upstream, ('dm/third_party/ryujinx', 'dm/tools/dmx.py',
                                               'dm/gfx/tools/nometal_run.py')))
    with original_input(identity):
        return {'generation': cache_keys.generation_keys(upstream, config),
                'payload': cache_keys.payload_key(upstream, config, source_chain),
                'shaders': cache_keys.fingerprint(files, {'spirv': config['spirv_commit'],
                    'nso': config['nso_sha256'], 'game': config['game_version'],
                    'switch': config['switch_version'], 'input': identity})}


def verify_references(manifest, data, legacy, pack):
    """Bind supplied download descriptors to the payload without fetching phone archives."""
    identity = export_resources.resource_identity(manifest)
    if data.get('resource_id') != identity:
        raise ValueError('Prepared Data reference differs from the resource manifest')
    for key in ('game_version', 'switch_version', 'archive_count', 'resource_bytes'):
        if data.get(key) != manifest[key]:
            raise ValueError('Prepared Data reference differs: ' + key)
    if legacy.get('pack') != pack or not re.fullmatch(r'[a-f0-9]{64}', legacy.get('recipe_id', '')):
        raise ValueError('Prepared Legacy reference differs from the IPA payload')
    expected_data = {f'D2R-Mobile-Resources.zip.{n:03d}' for n in range(1, 4)}
    expected_data.update(('Resources-SHA256SUMS.txt', 'Resources-Parts-SHA256SUMS.txt'))
    for reference, required in ((data, expected_data), (legacy, {'Legacy-Device-Pack.zip'})):
        https_url(reference['source_release']['url'], 'resource download page')
        assets = reference['assets']
        names = [a['name'] for a in assets]
        if len(names) != len(set(names)) or not required <= set(names):
            raise ValueError('Prepared resource download links are incomplete or duplicated')
        allowed = expected_data | {'resources-report.json', 'Legacy-Device-Pack.zip', 'pack.json',
                                   'pack_index.tsv', 'legacy-report.json', 'Legacy-SHA256SUMS.txt'}
        for item in assets:
            if (item['name'] not in allowed or type(item['bytes']) is not int or item['bytes'] <= 0
                    or not re.fullmatch(r'[a-f0-9]{64}', item['sha256'])):
                raise ValueError('Invalid prepared resource download descriptor')
            https_url(item['url'], 'resource download URL')
    if not re.fullmatch(r'[a-f0-9]{64}', data.get('zip_sha256', '')):
        raise ValueError('Prepared Data ZIP checksum missing')
    parts = [a for a in data['assets'] if a['name'].startswith('D2R-Mobile-Resources.zip.')]
    if sum(a['bytes'] for a in parts) != data.get('zip_bytes'):
        raise ValueError('Prepared Data volume sizes differ')


def verify_directory(directory):
    directory = Path(directory)
    info = read(directory / 'prepared.json')
    if info.get('format') != FORMAT or info.get('schema_version') != 1:
        raise ValueError('Expected a d2r-mobile prepared input package (schema 1)')
    if set(info['files']) != FILES:
        raise ValueError('Prepared package file manifest is incomplete')
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
    if actual != FILES | {'prepared.json'}:
        raise ValueError('Unexpected or missing prepared package file')
    for name, record in info['files'].items():
        path = directory / name
        if (path.is_symlink() or path.stat().st_size != record['bytes']
                or ci.sha256(path) != record['sha256']):
            raise ValueError('Prepared package checksum mismatch: ' + name)
    report = info['payload']
    if ci.sha256(directory / 'source-payload.zip') != report['payload_sha256']:
        raise ValueError('Prepared payload checksum differs from its report')
    if report.get('phone_shader_compilation_required') is not False:
        raise ValueError('Prepared input requires precompiled Metal libraries')
    with zipfile.ZipFile(directory / 'source-payload.zip') as z:
        members = z.infolist()
        if sum(i.file_size for i in members) > MAX_PACKAGE_BYTES:
            raise ValueError('Prepared payload exceeds the supported size')
        for item in members:
            relative = item.filename.removeprefix('Payload/DmIOS.app/')
            if (not item.filename.startswith('Payload/DmIOS.app/') or '\\' in relative
                    or '..' in relative.split('/') or relative.startswith('/')
                    or stat.S_IFMT(item.external_attr >> 16) not in (0, stat.S_IFREG, stat.S_IFDIR)
                    or relative in ('DmIOS', 'embedded.mobileprovision') or '_CodeSignature' in relative.split('/')):
                raise ValueError('Unexpected path in prepared payload')
        pack = json.loads(z.read('Payload/DmIOS.app/romfs_overlay_astc/pack.json'))
        if pack != report['legacy_pack']:
            raise ValueError('Prepared Legacy descriptor differs from the payload')
        guest = z.read('Payload/DmIOS.app/Frameworks/Guest.framework/Guest')
        if guest[:8] != bytes.fromhex('cffaedfe0c000001'):
            raise ValueError('Prepared game program is not arm64')
    verify_payload(directory / 'source-payload.zip', report)
    verify_references(read(directory / 'resource-manifest.json'), read(directory / 'resources.json'),
                      read(directory / 'legacy-resources.json'), pack)
    return info


def verify_source(directory, info, upstream, config):
    manifest = read(directory / 'resource-manifest.json')
    for key in ('game_version', 'switch_version', 'nso_sha256'):
        if info.get(key) != config[key]:
            raise ValueError('Prepared package does not match the selected game: ' + key)
    if {f['name']: f['bytes'] for f in manifest['files']} != ci.resource_sizes():
        raise ValueError('Prepared package resources do not match the selected source')
    dm = upstream / 'dm'
    if (dm / 'PRODUCT').read_text().strip() != info['payload']['product']:
        raise ValueError('Selected source requires a different prepared game product')
    expected = compatibility(upstream, config, info['original_input_identity'],
                             info['payload']['shader_source_chain'])
    if expected != info['compatibility']:
        changed = ', '.join(k for k in expected if expected[k] != info['compatibility'].get(k))
        raise ValueError('Selected source changed generation dependencies (' + changed +
                         '); supply an updated prepared package for this source')
    shutil.copy2(directory / 'shader-chain.lock', dm / 'gfx/tools/dmsh_chain.lock')
    chain = subprocess.check_output([sys.executable, str(dm / 'gfx/tools/dmsh_chain.py'), '--header'], text=True).strip()
    if chain != info['payload']['shader_chain']:
        raise ValueError('Selected source shader chain differs; supply an updated prepared package')


def resolve():
    url, digest = settings('PREPARED_INPUT')
    with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
        f.write('input_revision=' + input_identity(url, digest) + '\n')


def download(root=ci.ROOT):
    url, digest = settings('PREPARED_INPUT')
    archive = root / '.prepared-downloads/prepared-input.archive'
    marker = archive.with_suffix('.json')
    if archive.is_file():
        try:
            saved = read(marker)
            if (saved['identity'] == input_identity(url, digest) and saved['bytes'] == archive.stat().st_size
                    and saved['sha256'] == ci.sha256(archive) and (not digest or saved['sha256'] == digest)):
                print('Reused verified prepared package; download skipped', flush=True)
                return
        except (OSError, ValueError, KeyError):
            pass
    download_file(url, archive, digest or None, max_bytes=MAX_PACKAGE_BYTES)
    if not archive.stat().st_size:
        raise ValueError('Prepared package download is empty')
    write(marker, {'identity': input_identity(url, digest), 'bytes': archive.stat().st_size,
                   'sha256': ci.sha256(archive)})
    print('Prepared package downloaded and verified; ready to cache before extraction', flush=True)


def prepare(root=ci.ROOT):
    archive = root / '.prepared-downloads/prepared-input.archive'
    target = root / '.prepared-input'
    shutil.rmtree(target, ignore_errors=True)
    extract(archive, target)
    candidates = list(target.rglob('prepared.json'))
    if len(candidates) != 1:
        raise ValueError('Archive must contain exactly one prepared.json')
    directory = candidates[0].parent
    info = verify_directory(directory)
    upstream = root / 'upstream'
    verify_source(directory, info, upstream, ci.CONFIG)
    dm = upstream / 'dm'
    for name in GENERATED:
        destination = dm / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(directory / 'generated' / name, destination)
    subprocess.run([sys.executable, str(dm / 'ios/tools/shell_stubs.py'), 'stubs', str(dm)], check=True)
    out = root / 'outputs'
    out.mkdir(exist_ok=True)
    for name in ('source-payload.zip', 'resource-manifest.json', 'resources.json', 'legacy-resources.json'):
        shutil.copy2(directory / name, out / name)
    # Never inherit the producer's source commit, tool commit, build number or test claims.
    allowed = ('product', 'shader_chain', 'shader_source_chain', 'payload_sha256', 'legacy_pack',
               'shader_source_sha16', 'metal_precompiled', 'metal_libraries', 'metal_unique_libraries',
               'metal_toolchain', 'phone_shader_compilation_required')
    report = {k: info['payload'][k] for k in allowed}
    report.update(source_repository=os.environ['SOURCE_REPOSITORY'], source_commit=ci.CONFIG['upstream_commit'],
                  tools_commit=os.environ.get('TOOLS_COMMIT'), patch_sha256=ci.CONFIG.get('source_patch_sha256'),
                  input_identity=os.environ['INPUT_REVISION'], payload_reused=True, prepared_input=True,
                  prepared_schema_version=1, prepared_archive_sha256=ci.sha256(archive),
                  prepared_from_source=info['producer']['source_commit'],
                  metal_compiled_count=0, metal_cache_hits=report['metal_unique_libraries'], metal_seconds=0,
                  resource_links_verified=False,
                  prepared_metadata_sha256={n: ci.sha256(out / n) for n in
                    ('resource-manifest.json', 'resources.json', 'legacy-resources.json')})
    write(out / 'source-input-report.json', report)
    with tarfile.open(out / 'native-inputs.tar.gz', 'w:gz') as tf:
        def include(item):
            return None if any(p in ('.git', 'Gen', 'TouchArt', '__pycache__', 'bin', 'obj')
                               for p in Path(item.name).parts) else item
        tf.add(dm, arcname='upstream/dm', filter=include)
    print('Prepared input verified; game rewriting, resource generation, texture conversion and Metal compilation skipped', flush=True)
    print('Native runtime source:', ci.CONFIG['upstream_commit'], flush=True)


def export(root, payload, report, metadata, destination):
    """Export a producer's verified outputs; no game acquisition or conversion is performed."""
    root, payload, metadata, destination = map(Path, (root, payload, metadata, destination))
    report = read(report)
    report = report.get('packages', [report])[0]
    with tempfile.TemporaryDirectory(prefix='prepared-export-') as temporary:
        stage = Path(temporary)
        shutil.copy2(payload, stage / 'source-payload.zip')
        shutil.copy2(root / 'upstream/dm/gfx/tools/dmsh_chain.lock', stage / 'shader-chain.lock')
        for name in GENERATED:
            target = stage / 'generated' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / 'upstream/dm' / name, target)
        for name in ('resource-manifest.json', 'resources.json', 'legacy-resources.json'):
            shutil.copy2(metadata / name, stage / name)
        info = {'format': FORMAT, 'schema_version': 1,
                'game_version': ci.CONFIG['game_version'], 'switch_version': ci.CONFIG['switch_version'],
                'nso_sha256': ci.CONFIG['nso_sha256'], 'original_input_identity': report['input_identity'],
                'producer': {'source_commit': report['source_commit'], 'tools_commit': report.get('tools_commit')},
                'payload': report,
                'compatibility': compatibility(root / 'upstream', ci.CONFIG, report['input_identity'],
                                                 report['shader_source_chain']),
                'files': {n: {'bytes': (stage / n).stat().st_size, 'sha256': ci.sha256(stage / n)} for n in sorted(FILES)}}
        write(stage / 'prepared.json', info)
        verify_directory(stage)
        verify_source(stage, info, root / 'upstream', ci.CONFIG)
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_suffix('.zip.part')
        try:
            with zipfile.ZipFile(partial, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
                for path in sorted(stage.rglob('*')):
                    if path.is_file():
                        z.write(path, path.relative_to(stage).as_posix())
            partial.replace(destination)
        finally:
            partial.unlink(missing_ok=True)
    destination.with_name('Prepared-SHA256SUMS.txt').write_text(ci.sha256(destination) + '  ' + destination.name + '\n')
    print('Exported prepared package:', destination.name, destination.stat().st_size, 'bytes', flush=True)


if __name__ == '__main__':
    require_private()
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('resolve', 'download', 'prepare'):
        commands.add_parser(name)
    p = commands.add_parser('export')
    p.add_argument('--payload', type=Path, default=ci.ROOT / 'outputs/source-payload.zip')
    p.add_argument('--report', type=Path, default=ci.ROOT / 'outputs/source-input-report.json')
    p.add_argument('--metadata', type=Path, default=ci.ROOT / 'outputs')
    p.add_argument('--output', type=Path, default=ci.ROOT / 'outputs/D2RMobile-Prepared.zip')
    args = parser.parse_args()
    try:
        if args.command == 'export':
            export(ci.ROOT, args.payload, args.report, args.metadata, args.output)
        else:
            globals()[args.command]()
    except Exception as exc:
        print('::error::' + (str(exc) if isinstance(exc, ValueError) else type(exc).__name__), file=sys.stderr)
        sys.exit(1)
