"""Publish only the three explicitly allowlisted, game-independent tool packages."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

import prebuilt_tools as tools


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True)


def publish(directory):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    spec = manifest['recipe']
    if spec['kind'] not in tools.KINDS or spec['platform'] != tools.PLATFORM:
        raise ValueError('Not a supported public tool')
    release_tag = tools.tag(spec)
    if (directory / 'tag.txt').read_text().strip() != release_tag:
        raise ValueError('Tools tag mismatch')
    archive = directory / 'tool.tar.gz'
    checksum = f'{tools.sha(archive)}  tool.tar.gz\n'
    if (directory / 'SHA256SUMS.txt').read_text() != checksum:
        raise ValueError('Tool archive checksum mismatch')
    # Reuse the consumer's archive validation before granting public distribution.
    with tempfile.TemporaryDirectory() as temp:
        tools.unpack(archive, temp)
        checked = tools.validate(temp, spec)
        if checked != manifest:
            raise ValueError('Tool metadata mismatch')
    result = subprocess.run(['gh', 'api', f'repos/{tools.REPOSITORY}/releases/tags/{release_tag}'],
                            text=True, capture_output=True)
    if result.returncode == 0:
        release = json.loads(result.stdout)
        if not release['draft']:
            assets = {a['name'] for a in release['assets']}
            if assets != {'tool.tar.gz', 'manifest.json', 'SHA256SUMS.txt'}:
                raise ValueError('Existing public tool Release is incomplete')
            # Do not replace a published recipe with a different build of the same inputs.
            with tools.request(f'https://github.com/{tools.REPOSITORY}/releases/download/{release_tag}/manifest.json') as response:
                existing = json.load(response)
            if existing['recipe'] != spec or existing['identity'] != tools.identity(spec):
                raise ValueError('Existing tool Release identity mismatch')
            print('Tool already published:', release_tag); return
    elif '404' not in result.stderr:
        raise RuntimeError('Cannot check existing tools Release')
    else:
        notes = directory / 'notes.md'
        notes.write_text(f'Prebuilt **{spec["kind"]}** for Ubuntu 24.04 x64.\n\n'
                         'Source revisions and dependency fingerprints are recorded in `manifest.json`. '
                         'License notices are included in `tool.tar.gz`; archive checksums are in `SHA256SUMS.txt`.\n\n'
                         'Ubuntu 24.04 x64 预构建工具。来源与依赖指纹见 `manifest.json`，许可证随工具包提供，'
                         '校验值见 `SHA256SUMS.txt`。\n')
        gh('release', 'create', release_tag, '--repo', tools.REPOSITORY, '--draft', '--prerelease',
           '--target', manifest['tools_commit'], '--title', f'Build tool: {spec["kind"]} ({tools.identity(spec)[:12]})',
           '--notes-file', str(notes))
    gh('release', 'upload', release_tag, '--repo', tools.REPOSITORY, '--clobber',
       str(archive), str(directory / 'manifest.json'), str(directory / 'SHA256SUMS.txt'))
    gh('release', 'edit', release_tag, '--repo', tools.REPOSITORY, '--draft=false', '--latest=false')
    print('Published tool:', release_tag)


if __name__ == '__main__':
    if os.environ.get('GITHUB_REPOSITORY') != tools.REPOSITORY:
        raise SystemExit('Publish public tools only from the maintained tools repository')
    for kind in tools.KINDS:
        publish(tools.ROOT / 'outputs/tools' / kind)
