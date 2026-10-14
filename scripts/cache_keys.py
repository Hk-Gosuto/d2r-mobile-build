#!/usr/bin/env python3
"""Cache compiled tools and shaders by their inputs, independently of the app release."""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import ci
import prebuilt_tools


def collect(upstream, directories):
    files = {}
    for directory in directories:
        path = upstream / directory
        for item in ([path] if path.is_file() else path.rglob('*')):
            if item.is_file() and not any(p in ('.git', '__pycache__', 'bin', 'obj') for p in item.parts):
                files[item.relative_to(upstream).as_posix()] = item
    return files


def python_dependencies(upstream, entrypoints):
    """Follow local imports and literal child-script calls, excluding unrelated build tools."""
    upstream = Path(upstream).resolve()
    files = {}; pending = [upstream / name for name in entrypoints]
    search = (upstream/'dm/ios/tools', upstream/'dm/tools')
    while pending:
        path = pending.pop()
        if not path.is_file() or path.relative_to(upstream).as_posix() in files:
            continue
        files[path.relative_to(upstream).as_posix()] = path
        try:
            nodes = list(ast.walk(ast.parse(path.read_text())))
        except SyntaxError:
            continue
        names = []
        for node in nodes:
            if isinstance(node, ast.Import): names += [n.name.replace('.', '/')+'.py' for n in node.names]
            if isinstance(node, ast.ImportFrom) and node.module: names.append(node.module.replace('.', '/')+'.py')
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.endswith('.py'):
                names.append(node.value)
        for name in names:
            for directory in (path.parent, *search):
                child = (directory / name).resolve()
                if child.is_relative_to(upstream.resolve()) and child.is_file():
                    pending.append(child)
    return files


def python_versions(names):
    return {line.split('==')[0]: line.split('==')[1] for line in
            (ci.ROOT/'requirements.txt').read_text().splitlines()
            if '==' in line and line.split('==')[0] in names}


def fingerprint(files, values):
    h = hashlib.sha256(json.dumps(values, sort_keys=True).encode())
    for name, path in sorted(files.items()):
        h.update(name.encode() + b'\0' + path.read_bytes() + b'\0')
    return h.hexdigest()


def generation_keys(upstream, config):
    """App-only changes must not redo NSO rewriting or native art generation."""
    upstream = Path(upstream)

    rewrite = python_dependencies(upstream, ('dm/tools/patch_nso.py',))
    rewrite.update(collect(upstream, ('dm/PRODUCT',)))
    rewrite.update({p.relative_to(upstream).as_posix(): p for p in (upstream/'dm/data').glob('bootlist*.tsv')})
    assets = python_dependencies(upstream, ('dm/ios/tools/gen_assets.py',))
    assets.update(collect(upstream, ('dm/ios/tools/native_art', 'dm/ios/docs', 'dm/ios/NativeHUD', 'dm/data',
                                     'dm/ios/Sources/TouchArt/native_art_manifest.json',
                                     'dm/gfx/tex', 'dm/gfx/nvn/nvn_tex.c', 'dm/gfx/nvn/nvn_tex.h', 'dm/gfx/nvn/include')))
    for name in ('scripts/png_backend.sh', 'scripts/build_tool.sh', 'scripts/source/stages.py'):
        assets[name] = ci.ROOT / name
    return {
        'rewrite': fingerprint(rewrite, {'nso': config['nso_sha256'], 'ruleset': 'touch-run-v4',
                                        'python': python_versions(('capstone', 'lz4'))}),
        'assets': fingerprint(assets, {'inputs': os.environ.get('INPUT_REVISION', ''),
                                      'python': python_versions(('pillow', 'numpy', 'lz4'))}),
    }


def payload_key(upstream, config, chain):
    files = python_dependencies(upstream, ('dm/tools/d2rm_pack.py', 'dm/ios/tools/gen_romfs_overlay.py',
                                          'dm/ios/tools/gen_bright_levels.py', 'dm/ios/tools/shell_stubs.py'))
    files.update(collect(upstream, ('dm/data', 'dm/ios/NativeHUD', 'LICENSE',
                                     'dm/gfx/nvn/include', 'dm/third_party')))
    # C# sources in third_party do not affect packaging; notices and texture decoder sources do.
    files = {n:p for n,p in files.items() if not n.endswith(('.cs', '.csproj', '.props'))}
    files['scripts/source/prepare.py'] = ci.ROOT/'scripts/source/prepare.py'
    return fingerprint(files, {'generation': generation_keys(upstream, config), 'chain': chain,
                                'legacy': config['legacy_converter'], 'encoder': config['astc_encoder_sha256'],
                                'input': os.environ.get('INPUT_REVISION', '')})


def keys(upstream, config, sdk, chain=None):
    upstream = Path(upstream)
    tools = fingerprint({name: ci.ROOT / name for name in
                         ('scripts/tools.sh', 'scripts/prebuilt_tools.py', 'scripts/build_tool.sh')},
                        {kind: prebuilt_tools.recipe(kind, config, upstream, sdk)
                         for kind in prebuilt_tools.KINDS})
    chain_source = upstream / 'dm/gfx/tools/dmsh_chain.py'
    tree = ast.parse(chain_source.read_text())
    assignments = [n for n in tree.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'FILES' for t in n.targets)]
    if len(assignments) != 1:
        raise ValueError('Cannot determine upstream shader dependencies')
    dependencies = ast.literal_eval(assignments[0].value)
    files = {}
    for name in dependencies:
        path = (upstream / 'dm/gfx' / name).resolve()
        files[str(path.relative_to(upstream.resolve()))] = path
    for name in ('dm/gfx/tools/nometal_run.py', 'dm/tools/dmx.py'):
        files[name] = upstream / name
    for path in (upstream / 'dm/third_party/ryujinx').rglob('*'):
        if path.is_file() and not any(p in ('bin', 'obj', '.git', '__pycache__') for p in path.parts):
            files[str(path.relative_to(upstream))] = path
    shaders = fingerprint(files, {'spirv': config['spirv_commit'], 'sdk': sdk,
                                  'game': config['game_version'], 'switch': config['switch_version'],
                                  'nso': config['nso_sha256'], 'mode': 'no-metal',
                                  'inputs': os.environ.get('INPUT_REVISION', ''), 'verified_chain': chain})
    return {'tools': tools, 'shaders': shaders}


if __name__ == '__main__':
    sdk = subprocess.check_output(['dotnet', '--version'], text=True).strip()
    upstream = ci.ROOT / 'upstream'
    chain = None
    if sys.argv[1:] == ['shaders']:
        chain = subprocess.check_output([sys.executable, str(upstream / 'dm/gfx/tools/nometal_run.py'),
                                         str(upstream / 'dm/gfx/tools/dmsh_chain.py')], text=True).strip().splitlines()[-1]
    result = keys(upstream, ci.CONFIG, sdk, chain)
    result.update(generation_keys(upstream, ci.CONFIG))
    result['payload'] = payload_key(upstream, ci.CONFIG, chain)
    for key, value in result.items():
        print(key + '=' + value)
    with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
        stream.write(''.join(f'{key}={value}\n' for key, value in result.items()))
