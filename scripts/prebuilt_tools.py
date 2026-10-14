"""Publish and consume game-independent, content-addressed Linux build tools."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'jiayx/d2r-mobile-build'
SOURCE = 'jhaizhou-ops/d2r-mobile'
KINDS = ('spirv', 'png', 'xlate')
PLATFORM = 'ubuntu-24.04-x64'
MAX_BYTES = 256 * 1024 * 1024


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def translator_sources(upstream):
    files = {}
    if (Path(upstream) / 'LICENSE').is_file():
        files['LICENSE'] = sha(Path(upstream) / 'LICENSE')
    for name in ('dm/gfx/tools/dmsh_xlate', 'dm/third_party/ryujinx'):
        for path in (Path(upstream) / name).rglob('*'):
            if (path.is_file() and not any(p in ('.git', 'bin', 'obj', '__pycache__') for p in path.parts)
                    and (path.suffix in ('.cs', '.csproj', '.props', '.targets', '.glsl')
                         or path.name.upper().startswith(('LICENSE', 'COPYING', 'NOTICE')))):
                files[path.relative_to(upstream).as_posix()] = sha(path)
    return files


def recipe(kind, config, upstream, sdk):
    result = {'schema': 1, 'kind': kind, 'platform': PLATFORM,
              'builder_sha256': sha(ROOT / 'scripts/build_tool.sh')}
    if kind == 'spirv':
        result['source'] = {'repository': 'KhronosGroup/SPIRV-Cross', 'commit': config['spirv_commit']}
    elif kind == 'png':
        result['source'] = {'repository': 'zlib-ng/zlib-ng', 'commit': '6d9f3dc072369dc719a5fbe71d4e086a96a680bd'}
    elif kind == 'xlate':
        result.update(dotnet_sdk=sdk, source_files=translator_sources(upstream))
    else:
        raise ValueError('Unknown tool')
    return result


def identity(spec):
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()


def tag(spec):
    return f"tools-{spec['kind']}-{identity(spec)}"


def allowed_payload(kind, name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or str(p) != name:
        return False
    if kind == 'spirv':
        return name == 'bin/spirv-cross'
    if kind == 'png':
        return name == 'png-zlib-ng-2.3.2/lib/libz.so.1'
    return (kind == 'xlate' and len(p.parts) >= 2 and p.parts[0] == 'dmsh_xlate'
            and (name == 'dmsh_xlate/dmsh_xlate' or p.suffix in ('.dll', '.json')))


def validate(directory, spec):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest['recipe'] != spec or manifest['identity'] != identity(spec):
        raise ValueError('Tool recipe mismatch')
    files = manifest['files']
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
    if actual != set(files) | {'manifest.json'}:
        raise ValueError('Unexpected tool files')
    if not any(n.startswith('licenses/') for n in files):
        raise ValueError('Tool licenses missing')
    for name, digest in files.items():
        p = PurePosixPath(name)
        legal_notice = (len(p.parts) >= 2 and p.parts[0] == 'licenses' and not p.is_absolute()
                        and '..' not in p.parts and '\\' not in name and str(p) == name)
        if not legal_notice and not allowed_payload(spec['kind'], name):
            raise ValueError('File outside tool allowlist: ' + name)
        path = directory / name
        if path.is_symlink() or sha(path) != digest:
            raise ValueError('Tool checksum mismatch: ' + name)
    required = {'spirv': 'bin/spirv-cross', 'png': 'png-zlib-ng-2.3.2/lib/libz.so.1',
                'xlate': 'dmsh_xlate/dmsh_xlate'}[spec['kind']]
    if required not in files:
        raise ValueError('Tool executable missing')
    return manifest


def request(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'd2r-build-tools'}), timeout=45)


def unpack(archive, directory):
    with tarfile.open(archive) as tf:
        seen = set(); size = 0
        for member in tf:
            p = PurePosixPath(member.name)
            if (not member.isfile() or p.is_absolute() or '..' in p.parts or '\\' in member.name
                    or str(p) != member.name or member.name in seen):
                raise ValueError('Unsafe tool archive entry')
            size += member.size
            if size > MAX_BYTES or len(seen) > 10000:
                raise ValueError('Tool archive too large')
            seen.add(member.name)
            target = Path(directory) / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            with tf.extractfile(member) as src, target.open('wb') as dst:
                shutil.copyfileobj(src, dst)
            target.chmod(0o755 if member.mode & 0o111 else 0o644)


def restore(directory, spec):
    """Only trust assets published in the maintained tools repository over HTTPS."""
    with request(f'https://api.github.com/repos/{REPOSITORY}/releases/tags/{tag(spec)}') as stream:
        release = json.load(stream)
    if release.get('draft') or release.get('tag_name') != tag(spec):
        raise ValueError('Unexpected tools Release')
    assets = [a for a in release['assets'] if a['name'] == 'tool.tar.gz']
    if len(assets) != 1 or not re.fullmatch(r'sha256:[a-f0-9]{64}', assets[0].get('digest') or ''):
        raise ValueError('Published tool checksum unavailable')
    asset = assets[0]
    url = asset['browser_download_url']
    if not url.startswith(f'https://github.com/{REPOSITORY}/releases/download/{tag(spec)}/'):
        raise ValueError('Unexpected tool download host')
    with tempfile.TemporaryDirectory() as temp:
        archive = Path(temp) / 'tool.tar.gz'
        with request(url) as response, archive.open('wb') as out:
            while block := response.read(1024 * 1024):
                out.write(block)
                if out.tell() > MAX_BYTES:
                    raise ValueError('Tool archive too large')
        if sha(archive) != asset['digest'][7:]:
            raise ValueError('Published tool checksum mismatch')
        unpack(archive, directory)
    validate(directory, spec)


def licenses(destination):
    """Carry upstream notices and the licenses of the actual NuGet dependency closure."""
    destination = Path(destination); destination.mkdir(parents=True, exist_ok=True)
    upstream = ROOT / 'upstream'
    shutil.copy2(upstream / 'LICENSE', destination / 'd2r-mobile-MIT.txt')
    ryu = upstream / 'dm/third_party/ryujinx'
    for p in ryu.rglob('*'):
        if p.is_file() and p.name.upper().startswith(('LICENSE', 'COPYING', 'NOTICE')):
            target = destination / 'ryujinx' / p.relative_to(ryu)
            target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p, target)
    assets = json.loads((upstream / 'dm/gfx/tools/dmsh_xlate/obj/project.assets.json').read_text())
    roots = [Path(p) for p in assets['packageFolders']]
    standard_licenses = {}
    for package, metadata in assets['libraries'].items():
        if metadata['type'] != 'package':
            continue
        package_root = next(p / metadata['path'] for p in roots if (p / metadata['path']).is_dir())
        nuspec = next(package_root.glob('*.nuspec'))
        tree = ET.parse(nuspec)
        license_node = next((n for n in tree.iter() if n.tag.split('}')[-1] == 'license'), None)
        if license_node is None:
            raise ValueError('Missing NuGet license: ' + package)
        target = destination / 'nuget' / package
        target.mkdir(parents=True, exist_ok=True); shutil.copy2(nuspec, target / nuspec.name)
        value = license_node.text.strip()
        if license_node.get('type') == 'file':
            source = (package_root / value).resolve()
            if not source.is_relative_to(package_root.resolve()):
                raise ValueError('Invalid NuGet license path')
            shutil.copy2(source, target / 'LICENSE.txt')
        elif license_node.get('type') == 'expression' and value in ('MIT', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause', 'ISC', 'Zlib'):
            if value not in standard_licenses:
                with request(f'https://raw.githubusercontent.com/spdx/license-list-data/v3.27.0/text/{value}.txt') as response:
                    standard_licenses[value] = response.read()
            (target / 'LICENSE.txt').write_bytes(standard_licenses[value])
            # Keep package-specific notices as well as the standard license text.
            for source in package_root.rglob('*'):
                if source.is_file() and source.name.upper().startswith(('LICENSE', 'COPYING', 'NOTICE', 'AUTHORS')):
                    notice = target / source.relative_to(package_root)
                    notice.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, notice)
        else:
            raise ValueError('Review NuGet license before public distribution: ' + package)


def build(directory, spec):
    subprocess.run(['bash', str(ROOT / 'scripts/build_tool.sh'), spec['kind'], str(directory)], cwd=ROOT, check=True)
    files = {p.relative_to(directory).as_posix(): sha(p) for p in Path(directory).rglob('*') if p.is_file()}
    manifest = {'identity': identity(spec), 'recipe': spec, 'files': files,
                'tools_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()}
    if spec['kind'] == 'xlate':
        manifest['source_repository'] = SOURCE
        manifest['source_commit'] = subprocess.check_output(['git', '-C', str(ROOT/'upstream'), 'rev-parse', 'HEAD'], text=True).strip()
    (Path(directory) / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    validate(directory, spec)


def ensure(spec):
    cache = ROOT / '.tools/packages' / tag(spec)
    try:
        validate(cache, spec)
        print('Using cached tool:', spec['kind'], flush=True)
    except (OSError, ValueError, KeyError):
        cache.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache.parent) as temp:
            stage = Path(temp) / 'package'; stage.mkdir()
            try:
                restore(stage, spec)
                print('Using verified prebuilt tool:', spec['kind'], flush=True)
            except (OSError, ValueError, KeyError, tarfile.TarError) as error:
                print(f'Prebuilt {spec["kind"]} unavailable ({type(error).__name__}); compiling from source', flush=True)
                shutil.rmtree(stage); stage.mkdir(); build(stage, spec)
            shutil.rmtree(cache, ignore_errors=True); shutil.copytree(stage, cache)
    # Install only validated payloads. Keep notices and receipts in the tool cache.
    if spec['kind'] == 'xlate':
        shutil.rmtree(ROOT / '.tools/dmsh_xlate', ignore_errors=True)
    for name in validate(cache, spec)['files']:
        if name.startswith('licenses/'):
            continue
        target = ROOT / '.tools' / name
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(cache / name, target)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('ensure', 'build', 'licenses'))
    parser.add_argument('kind')
    args = parser.parse_args()
    if args.command == 'licenses':
        licenses(args.kind); return
    if args.kind not in KINDS:
        parser.error('Unknown tool')
    sdk = subprocess.check_output(['dotnet', '--version'], text=True).strip() if args.kind == 'xlate' else ''
    config = json.loads((ROOT / 'build-config.json').read_text())
    spec = recipe(args.kind, config, ROOT / 'upstream', sdk)
    if args.command == 'ensure':
        ensure(spec); return
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'AMD64'):
        raise ValueError('Publish tools on Ubuntu 24.04 x64')
    out = ROOT / 'outputs/tools' / args.kind
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        build(Path(temp), spec)
        with tarfile.open(out / 'tool.tar.gz', 'w:gz') as tf:
            for p in sorted(Path(temp).rglob('*')):
                if p.is_file():
                    tf.add(p, arcname=p.relative_to(temp).as_posix())
        shutil.copy2(Path(temp) / 'manifest.json', out / 'manifest.json')
    (out / 'SHA256SUMS.txt').write_text(f'{sha(out / "tool.tar.gz")}  tool.tar.gz\n')
    (out / 'tag.txt').write_text(tag(spec) + '\n')


if __name__ == '__main__':
    main()
