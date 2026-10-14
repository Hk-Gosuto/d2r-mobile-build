"""Record the selected source checkout and apply optional build patches."""
import hashlib
import json
from pathlib import Path
import re
import subprocess


def source_identity(upstream):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(upstream), *args],
                                       text=True, stderr=subprocess.DEVNULL).strip()

    commit = git('rev-parse', 'HEAD')
    label = 'src-' + commit[:12]
    try:
        description = git('describe', '--tags', '--match', 'v[0-9]*', '--long',
                          '--abbrev=12', 'HEAD')
    except subprocess.CalledProcessError:
        description = ''
    match = re.fullmatch(r'(v\d+\.\d+(?:\.\d+)?)-(\d+)-g[0-9a-f]+', description)
    if match:
        label = match[1]
        if int(match[2]):
            label += '-src-' + commit[:12]
    return commit, label


def configure(root):
    upstream = root / 'upstream'
    commit, label = source_identity(upstream)
    digest = hashlib.sha256()
    patches = sorted((root / 'source-patches').glob('*.patch'))
    for patch in patches:
        subprocess.run(['git', '-C', str(upstream), 'apply', '--check', str(patch)], check=True)
        subprocess.run(['git', '-C', str(upstream), 'apply', str(patch)], check=True)
        digest.update(patch.name.encode() + b'\0' + patch.read_bytes())
    path = root / 'config/build-pins.json'
    config = json.loads(path.read_text())
    config.pop('upstream_version', None)
    config.pop('source_patch_sha256', None)
    config['upstream_commit'] = commit
    if patches:
        config['source_patch_sha256'] = digest.hexdigest()
        label += '-patch-' + digest.hexdigest()[:12]
    config['build_label'] = label
    path.write_text(json.dumps(config, indent=2) + '\n')
    print('Selected source:', commit, 'build:', label)
    return config


if __name__ == '__main__':
    configure(Path(__file__).resolve().parents[2])
