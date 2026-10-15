"""Compile translated iOS shaders once, preserving upstream chain and reflection contracts."""
import concurrent.futures
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ci
from repository_access import require_private

BASE = 'Payload/DmIOS.app/'
CACHE = ci.ROOT / '.metal-cache'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def toolchain(dm):
    command = ['xcrun', '-sdk', 'iphoneos', 'metal', '--version']
    check = subprocess.run(command, capture_output=True, text=True)
    if check.returncode:
        subprocess.run(['xcodebuild', '-downloadComponent', 'MetalToolchain'], check=True, timeout=1200)
        check = subprocess.run(command, capture_output=True, text=True, check=True)
    run = lambda *args: subprocess.check_output(args, text=True).strip()
    ios = module(dm / 'ios/tools/ios_metal.py', 'ios_metal_compile')
    # Honor the upstream iOS compile implementation, including its deployment target.
    identity = {'metal': check.stdout.strip(), 'xcode': run('xcodebuild', '-version'),
                'sdk': run('xcrun', '--sdk', 'iphoneos', '--show-sdk-build-version'),
                'compiler_sha256': ci.sha256(Path(run('xcrun', '-sdk', 'iphoneos', '--find', 'metal'))),
                'ios_compile_sha256': ci.sha256(dm / 'ios/tools/ios_metal.py'),
                'compile_record': ios.RECORD}
    return identity, ios


def inputs(payload, report):
    if ci.sha256(payload) != report['payload_sha256']:
        raise ValueError('Translated payload checksum mismatch')
    chain = report['shader_chain']
    prefix = BASE + 'msl/b-' + chain + '/'
    with zipfile.ZipFile(payload) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate payload member')
        if any(not n.startswith(BASE) or '..' in n.split('/') for n in names):
            raise ValueError('Unsafe payload path')
        libraries = {n: z.read(n) for n in names if n.startswith(prefix) and n.endswith('.metallib')}
        if not libraries or not any(n.endswith('_b.metallib') for n in libraries):
            raise ValueError('Translated shader libraries missing')
        if any(n.endswith('.metallib') and n not in libraries for n in names):
            raise ValueError('Mixed shader directories')
        for name, data in libraries.items():
            if data.startswith(b'MTLB'):
                raise ValueError('Expected translated shader source before Metal compilation')
            data.decode('utf-8')
            if name.endswith('_b.metallib'):
                reflection = json.loads(z.read(name.removesuffix('.metallib') + '.json'))
                if reflection['chain'] != chain:
                    raise ValueError('Translated reflection chain mismatch')
    return libraries


def object_key(source, family):
    return digest(family.encode() + b'\0' + source)


def compile_object(source, family, cache, compile_fn):
    key = object_key(source, family)
    target = cache / 'objects' / key
    library = target / 'library.metallib'
    expected = {'family': family, 'source_sha256': digest(source)}
    try:
        record = json.loads((target / 'receipt.json').read_text())
        binary = library.read_bytes()
        if (all(record.get(k) == v for k, v in expected.items()) and binary.startswith(b'MTLB')
                and digest(binary) == record['library_sha256']):
            return binary, True
    except (OSError, ValueError, KeyError):
        pass
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache, prefix='compile-') as temporary:
        work = Path(temporary)
        src, air, lib = work / 'shader.metal', work / 'shader.air', work / 'shader.metallib'
        src.write_bytes(source)
        compile_fn(str(src), str(air), str(lib))
        binary = lib.read_bytes()
        if not binary.startswith(b'MTLB'):
            raise ValueError('Metal compiler did not produce a binary library')
        target.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(lib, library)
        (target / 'receipt.json').write_text(json.dumps(dict(expected, library_sha256=digest(binary))) + '\n')
    return binary, False


def set_chain(dm, identity):
    lock = dm / 'gfx/tools/dmsh_chain.lock'
    rows = lock.read_text().splitlines()
    if sum(line.startswith('metal_iphoneos\t') for line in rows) != 1:
        raise ValueError('Upstream Metal tool fingerprint missing')
    lock.write_text('\n'.join('metal_iphoneos\t' + identity['metal'].splitlines()[0]
                              if line.startswith('metal_iphoneos\t') else line for line in rows) + '\n')
    # Other tool fingerprints describe the Linux translation that produced this source.
    return subprocess.check_output([sys.executable, str(dm / 'gfx/tools/dmsh_chain.py'), '--header'], text=True).strip()


def configure(root):
    out = root / 'outputs'
    report = json.loads((out / 'source-input-report.json').read_text())
    inputs(out / 'source-payload.zip', report)
    identity, _ = toolchain(root / 'upstream/dm')
    family = digest(json.dumps(identity, sort_keys=True).encode())
    recipe = digest(Path(__file__).read_bytes())
    key = digest((family + report['payload_sha256'] + recipe).encode())
    (out / 'metal-plan.json').write_text(json.dumps({'family': family, 'toolchain': identity,
                                                   'input_sha256': report['payload_sha256']}, indent=2) + '\n')
    with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
        f.write(f'prefix=metal-ios-v1-{family}-\nkey=metal-ios-v1-{family}-{key}\n')
    print('Metal toolchain:', json.dumps(identity, sort_keys=True), flush=True)


def rewrite_payload(source, destination, report, compiled, new_chain, compile_record):
    old = report['shader_chain']
    old_prefix, new_prefix = 'msl/b-' + old + '/', 'msl/b-' + new_chain + '/'
    with zipfile.ZipFile(source) as z, zipfile.ZipFile(destination, 'w') as result:
        for item in z.infolist():
            data = z.read(item)
            relative = item.filename.removeprefix(BASE)
            renamed = copy.copy(item)
            if relative.startswith(old_prefix):
                renamed.filename = BASE + new_prefix + relative.removeprefix(old_prefix)
                if item.filename in compiled:
                    data = compiled[item.filename]
                elif relative.endswith('.json'):
                    reflection = json.loads(data)
                    if reflection['chain'] != old:
                        raise ValueError('Mixed reflection chain')
                    reflection.update(chain=new_chain, chain_metal=compile_record)
                    data = (json.dumps(reflection, separators=(',', ':')) + '\n').encode()
            elif relative == 'dm/shell_manifest.txt':
                data = data.replace(old_prefix.encode(), new_prefix.encode())
            elif relative == 'dm/shell_info.txt':
                if ('CHAIN=' + old + '\n').encode() not in data:
                    raise ValueError('Shell shader chain missing')
                data = data.replace(('CHAIN=' + old + '\n').encode(), ('CHAIN=' + new_chain + '\n').encode())
            elif relative == 'dm/c1_full.tsv':
                if not data.startswith(('# chain b-' + old + ' ').encode()):
                    raise ValueError('Shader index chain mismatch')
                data = data.replace(('# chain b-' + old + ' ').encode(), ('# chain b-' + new_chain + ' ').encode(), 1)
            result.writestr(renamed, data)


def verify_payload(payload, report):
    if not report.get('metal_precompiled'):
        raise ValueError('Precompiled Metal shader report missing')
    chain = report['shader_chain']
    prefix = BASE + 'msl/b-' + chain + '/'
    with zipfile.ZipFile(payload) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate compiled payload member')
        libraries = [n for n in names if n.endswith('.metallib')]
        if len(libraries) != report['metal_libraries'] or not libraries:
            raise ValueError('Incomplete precompiled Metal libraries')
        for name in libraries:
            if not name.startswith(prefix) or not z.read(name).startswith(b'MTLB'):
                raise ValueError('Uncompiled or mixed Metal shader: ' + name)
            if name.endswith('_b.metallib'):
                reflection = json.loads(z.read(name.removesuffix('.metallib') + '.json'))
                if reflection['chain'] != chain or reflection['chain_metal'] != report['metal_toolchain']['compile_record']:
                    raise ValueError('Compiled reflection metadata mismatch')
        info = dict(line.split('=', 1) for line in z.read(BASE + 'dm/shell_info.txt').decode().splitlines())
        if info['CHAIN'] != chain or info['PRODUCT'] != report['product']:
            raise ValueError('Compiled shell metadata mismatch')
        if not z.read(BASE + 'dm/c1_full.tsv').startswith(('# chain b-' + chain + ' ').encode()):
            raise ValueError('Compiled shader index mismatch')
        for item in z.read(BASE + 'dm/shell_manifest.txt').decode().splitlines():
            target = BASE + item
            if not item or not (any(n.startswith(target) for n in names) if item.endswith('/') else target in names):
                raise ValueError('Incomplete compiled payload manifest: ' + item)


def compile_payload(root, cache=CACHE):
    started = time.monotonic()
    out, dm = root / 'outputs', root / 'upstream/dm'
    report = json.loads((out / 'source-input-report.json').read_text())
    plan = json.loads((out / 'metal-plan.json').read_text())
    identity, ios = toolchain(dm)
    if identity != plan['toolchain'] or report['payload_sha256'] != plan['input_sha256']:
        raise ValueError('Metal inputs or toolchain changed after cache resolution')
    payload = out / 'source-payload.zip'
    sources = inputs(payload, report)
    unique = {object_key(source, plan['family']): source for source in sources.values()}
    binaries = {}; hits = 0
    workers = max(1, min(3, os.cpu_count() or 1))
    print(f'Compiling {len(sources)} Metal libraries ({len(unique)} unique) with {workers} workers', flush=True)
    def compile_one(item):
        key, source = item
        return key, *compile_object(source, plan['family'], cache, ios.compile)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for key, binary, cached in pool.map(compile_one, unique.items()):
            binaries[key] = binary; hits += int(cached)
            if len(binaries) % 100 == 0 or len(binaries) == len(unique):
                print(f'Metal progress: {len(binaries)}/{len(unique)}, cache hits {hits}, elapsed {time.monotonic()-started:.0f}s', flush=True)
    old_chain = report['shader_chain']
    new_chain = set_chain(dm, identity)
    compiled = {name: binaries[object_key(source, plan['family'])] for name, source in sources.items()}
    temporary = out / 'compiled-payload.zip'
    rewrite_payload(payload, temporary, report, compiled, new_chain, ios.RECORD)
    report.update(shader_source_chain=old_chain, shader_chain=new_chain, metal_precompiled=True,
                  metal_libraries=len(sources), metal_unique_libraries=len(unique), metal_cache_hits=hits,
                  metal_compiled_count=len(unique)-hits, metal_toolchain=identity,
                  phone_shader_compilation_required=False, metal_seconds=round(time.monotonic()-started, 2))
    verify_payload(temporary, report)
    temporary.replace(payload)
    report['payload_sha256'] = ci.sha256(payload)
    (out / 'source-input-report.json').write_text(json.dumps(report, indent=2) + '\n')
    with tarfile.open(out / 'native-inputs.tar.gz', 'w:gz') as tf:
        tf.add(dm, arcname='upstream/dm')
    for directory in (cache / 'objects').iterdir():
        if directory.name not in unique:
            shutil.rmtree(directory)
    print(f'Metal precompilation verified: {len(sources)} libraries, {len(unique)-hits} compiled, {hits} reused; {report["metal_seconds"]}s', flush=True)


if __name__ == '__main__':
    require_private()
    configure(ci.ROOT) if sys.argv[1:] == ['keys'] else compile_payload(ci.ROOT)
