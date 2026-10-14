#!/usr/bin/env python3
"""Shared input validation and native executable inspection."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / 'config/build-pins.json').read_text())
DM = Path(os.environ.get('DM_ROOT', str(ROOT / '.dm-work')))
GAME = DM / 'data/switch' / CONFIG['game_version'] / 'Update'
TOOLS = ROOT / '.tools'
WORK = ROOT / '.downloads'
RAW = ROOT / '.game-downloads'


def build_label(config=None):
    config = CONFIG if config is None else config
    label = config.get('build_label', '')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', label):
        raise ValueError('Resolve the selected source before naming build outputs')
    return label


def ipa_names(config=None):
    config = CONFIG if config is None else config
    label = build_label(config)
    return (f'D2RMobile-{label}.ipa', f'D2RMobile-{label}-ios18.ipa')


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def download(url, dest, expected=None):
    """Keep signed URLs out of logs; reject web landing pages."""
    if not url.startswith('https://'):
        raise ValueError('Input downloads must use HTTPS')
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + '.part')
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'd2r-mobile-build/1.0'})
        with urllib.request.urlopen(req, timeout=120) as r:
            if 'text/html' in r.headers.get('Content-Type', '').lower():
                raise ValueError('Download returned an HTML page; supply a direct file URL')
            with partial.open('wb') as f:
                shutil.copyfileobj(r, f, length=8 * 1024 * 1024)
            length = r.headers.get('Content-Length')
            if length is not None and partial.stat().st_size != int(length):
                raise ValueError('Download incomplete: ' + dest.name)
        if expected and sha256(partial) != expected.lower():
            raise ValueError('Download SHA256 mismatch: ' + dest.name)
        partial.replace(dest)
    except Exception as exc:
        partial.unlink(missing_ok=True)
        # urllib exceptions can contain signed URL credentials.
        if isinstance(exc, ValueError):
            raise
        raise RuntimeError(f'Download failed for {dest.name}: {type(exc).__name__}') from None


def resource_sizes():
    src = (ROOT / 'upstream/dm/host/romfs_validate.c').read_text()
    names = re.search(r'static const char \*need\[\] = \{(.*?)\};', src, re.S)
    sizes = re.search(r'static const long long size\[\] = \{(.*?)\};', src, re.S)
    files = re.findall(r'"([^"]+\.data)"', names.group(1))
    lengths = [int(n) for n in re.findall(r'\d+', sizes.group(1))]
    if len(files) != 18 or len(lengths) != 18:
        raise ValueError('Unexpected upstream resource manifest')
    return dict(zip(files, lengths))


def validate_game(game=GAME):
    game = Path(game)
    for name, expected in CONFIG['nso_sha256'].items():
        path = game / 'ExeFS' / name
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f'ExeFS/{name} is not the original 3.3.94012 program')
    for name, length in resource_sizes().items():
        path = game / 'RomFS/data' / name
        if not path.is_file() or path.stat().st_size != length:
            raise ValueError(f'Resource missing or incomplete: {name}')
    if not (game / 'RomFS/data/build_manifest.psv').is_file():
        raise ValueError('RomFS/data/build_manifest.psv missing')
    print('Game verified: 3 original NSO hashes and 18 archive sizes match 3.3.94012')


def run(args, logfile, env=None):
    logfile = Path(logfile)
    with logfile.open('wb') as f:
        p = subprocess.run([str(a) for a in args], stdout=f, stderr=subprocess.STDOUT, env=env)
    if p.returncode:
        raise RuntimeError(f'{Path(str(args[0])).name} failed; inspect private runner log {logfile.name}')
    return logfile.read_text(errors='replace')


def macho_minimum_os(data):
    """Read the iOS minimum from a thin ARM64 executable's load commands."""
    if len(data) < 32 or struct.unpack_from('<II', data) != (0xfeedfacf, 0x0100000c):
        raise ValueError('Native executable is not Mach-O arm64')
    count, size = struct.unpack_from('<II', data, 16)
    end = 32 + size
    if end > len(data) or count > size // 8:
        raise ValueError('Truncated Mach-O load commands')
    offset, versions = 32, []
    for _ in range(count):
        if offset + 8 > end:
            raise ValueError('Truncated Mach-O load command')
        command, length = struct.unpack_from('<II', data, offset)
        if length < 8 or length % 8 or offset + length > end:
            raise ValueError('Invalid Mach-O load command size')
        if command == 0x32:  # LC_BUILD_VERSION
            if length < 24:
                raise ValueError('Truncated Mach-O build version')
            platform, minimum = struct.unpack_from('<II', data, offset + 8)
            if platform != 2:
                raise ValueError('Native executable does not target iOS')
            versions.append((minimum >> 16, (minimum >> 8) & 255, minimum & 255))
        offset += length
    if offset != end or len(versions) != 1:
        raise ValueError('Missing or ambiguous Mach-O build version')
    return versions[0]


def diagnostics():
    target = ROOT / 'outputs/diagnostics'
    target.mkdir(parents=True, exist_ok=True)
    sources = list(WORK.glob('*.log')) + list((DM / 'build/pack/stage').glob('*.log'))
    sources += list((DM / 'build/cache/dm/out').glob('*/*.patch.log'))
    for i, path in enumerate(sources):
        content = path.read_text(errors='replace')
        # Never publish 128-bit (or longer) key values from tool diagnostics.
        content = re.sub(r'(?i)(?<![0-9a-f])[0-9a-f]{32,}(?![0-9a-f])', '[hex redacted]', content)
        (target / f'{i:02}-{path.name}').write_text(content)
    print('Sanitized diagnostic logs:', len(sources))
