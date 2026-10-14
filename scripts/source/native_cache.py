"""Bounded compiler caches, isolated by Apple toolchain and iOS deployment target."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess


def configure(root, minimum):
    def run(*args):
        return subprocess.check_output(args, text=True).strip()
    ccache = shutil.which('ccache')
    if not ccache:
        raise ValueError('ccache is not installed')
    clang = run('xcrun', '--find', 'clang')
    clangxx = run('xcrun', '--find', 'clang++')
    compiler = {'xcode': run('xcodebuild', '-version'), 'sdk': run('xcrun', '--sdk', 'iphoneos', '--show-sdk-build-version'),
                'clang_sha256': hashlib.sha256(Path(clang).read_bytes()).hexdigest(),
                'clangxx_sha256': hashlib.sha256(Path(clangxx).read_bytes()).hexdigest(),
                'ccache': run(ccache, '--version').splitlines()[0],
                'minimum': minimum, 'architecture': platform.machine()}
    print('Compiler cache toolchain:', json.dumps(compiler, sort_keys=True), flush=True)
    family = hashlib.sha256(json.dumps(compiler, sort_keys=True).encode()).hexdigest()
    source = hashlib.sha256()
    for p in sorted((root/'upstream/dm').rglob('*')):
        if p.is_file() and not any(n in ('.git', 'bin', 'obj', '__pycache__') for n in p.parts):
            source.update(p.relative_to(root).as_posix().encode()+b'\0'+p.read_bytes())
    tools = root/'.tools'; tools.mkdir(exist_ok=True)
    for name, executable in (('clang', clang), ('clang++', clangxx)):
        wrapper=tools/('ccache-'+name)
        wrapper.write_text('#!/bin/sh\nexec '+shlex.quote(ccache)+' '+shlex.quote(executable)+' "$@"\n')
        wrapper.chmod(0o755)
    cache=root/'.native-ccache'; cache.mkdir(exist_ok=True)
    # Keep room for the original archive and the much more valuable game-generation caches.
    (cache/'ccache.conf').write_text('max_size = 128M\ncompiler_check = content\ndirect_mode = true\ndepend_mode = true\n')
    with open(os.environ['GITHUB_OUTPUT'],'a') as out:
        out.write(f'prefix=native-ccache-v1-{family}-\nkey=native-ccache-v1-{family}-{source.hexdigest()}\n')
    with open(os.environ['GITHUB_ENV'],'a') as out:
        out.write(f'CCACHE_DIR={cache}\nCCACHE_BASEDIR={root}\n')


if __name__ == '__main__':
    configure(Path(__file__).resolve().parents[2], os.environ['MINIMUM_IOS'])
