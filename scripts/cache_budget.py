"""Save the compiler module cache only when repository cache space permits."""
import json
import os
from pathlib import Path
import subprocess

LIMIT = 10 * 1024**3
RESERVE = 256 * 1024**2


def can_save(used, size, limit=LIMIT, reserve=RESERVE):
    return used is not None and size > 0 and used + size + reserve <= limit


def main():
    try:
        result = subprocess.check_output(['gh', 'api', 'repos/' + os.environ['GITHUB_REPOSITORY'] +
                                          '/actions/cache/usage'], text=True, stderr=subprocess.DEVNULL)
        used = json.loads(result)['active_caches_size_in_bytes']
    except (subprocess.CalledProcessError, ValueError, KeyError):
        used = None
    files = [p for p in Path('.native-module-cache').rglob('*') if p.is_file()]
    size = sum(p.stat().st_size + 4096 for p in files) + 16 * 1024**2 if files else 0
    enabled = can_save(used, size)
    with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
        out.write('native=' + str(enabled).lower() + '\n')
    print('Save compiler module cache:', enabled)


if __name__ == '__main__':
    main()
