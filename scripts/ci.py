#!/usr/bin/env python3
"""Remote input preparation, version verification and IPA verification."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / 'build-config.json').read_text())
DM = Path(os.environ.get('DM_ROOT', str(ROOT / '.dm-work')))
GAME = DM / 'data/switch/3.3.94012/Update'
TOOLS = ROOT / '.tools'
WORK = ROOT / '.downloads'
SHELL = TOOLS / 'D2RMobile-shell.ipa'


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
        req = urllib.request.Request(url, headers={'User-Agent': 'd2r-private-build/1.0'})
        with urllib.request.urlopen(req, timeout=120) as r:
            if 'text/html' in r.headers.get('Content-Type', '').lower():
                raise ValueError('Download returned an HTML page; supply a direct file URL')
            with partial.open('wb') as f:
                shutil.copyfileobj(r, f, length=8 * 1024 * 1024)
        if expected and sha256(partial) != expected.lower():
            raise ValueError('Download SHA256 mismatch: ' + dest.name)
        partial.replace(dest)
    except Exception as exc:
        partial.unlink(missing_ok=True)
        # urllib exceptions can contain signed URL credentials.
        if isinstance(exc, ValueError):
            raise
        raise RuntimeError(f'Download failed for {dest.name}: {type(exc).__name__}') from None


def shell_info(path):
    with zipfile.ZipFile(path) as z:
        infos = [n for n in z.namelist() if n.endswith('/dm/shell_info.txt')]
        if len(infos) != 1:
            raise ValueError('Shell version manifest missing or ambiguous')
        return dict(line.split('=', 1) for line in z.read(infos[0]).decode().splitlines() if '=' in line)


def ensure_shell():
    if not SHELL.exists() or sha256(SHELL) != CONFIG['shell_sha256']:
        download(CONFIG['shell_url'], SHELL, CONFIG['shell_sha256'])
    info = shell_info(SHELL)
    product = (ROOT / 'upstream/dm/PRODUCT').read_text().strip()
    if info['PRODUCT'] != product:
        raise ValueError('Pinned source and shell PRODUCT differ')
    print('Shell verified:', info['PRODUCT'], 'shader digest', info['SHADER_SRC'])


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


def run(args, logfile):
    logfile = Path(logfile)
    with logfile.open('wb') as f:
        p = subprocess.run([str(a) for a in args], stdout=f, stderr=subprocess.STDOUT)
    if p.returncode:
        raise RuntimeError(f'{Path(str(args[0])).name} failed; inspect private runner log {logfile.name}')
    return logfile.read_text(errors='replace')


def unpack_archives():
    for path in sorted(WORK.glob('*')):
        if not path.is_file():
            continue
        name = path.name.lower()
        if re.search(r'\.part\d+\.rar$', name) and not re.search(r'\.part0*1\.rar$', name):
            continue
        if re.search(r'\.(zip|rar|7z)(\.001)?$', name):
            target = WORK / (path.name + '.unpacked')
            target.mkdir(exist_ok=True)
            # Reject absolute/traversing paths before letting 7z extract.
            listing = subprocess.check_output(['7z', 'l', '-slt', str(path)], text=True)
            for member in re.findall(r'^Path = (.*)$', listing, re.M)[1:]:
                clean = member.replace('\\', '/')
                if clean.startswith('/') or '..' in clean.split('/') or re.match(r'^[A-Za-z]:', clean):
                    raise ValueError('Unsafe archive member path')
            run(['7z', 'x', '-y', f'-o{target}', path], WORK / 'archive.log')


def prepare_game():
    if GAME.is_dir():
        validate_game()
        print('Using validated game cache; no game download required')
        return
    raw = os.environ.get('GAME_INPUT_MANIFEST', '').strip()
    if not raw:
        raise ValueError('GAME_INPUT_MANIFEST secret missing and game cache not found. Supply direct download URLs for prepared ExeFS/RomFS or base+update packages.')
    manifest = json.loads(raw)
    kind = manifest.get('kind')
    if kind not in ('prepared', 'packages'):
        raise ValueError('Input manifest kind must be prepared or packages')
    if kind == 'packages' and not os.environ.get('PROD_KEYS', '').strip():
        raise ValueError('PROD_KEYS secret required to decrypt NSP/XCI; alternatively provide prepared ExeFS/RomFS')
    files = manifest.get('files', [])
    if not files:
        raise ValueError('Input manifest files cannot be empty')
    WORK.mkdir(parents=True, exist_ok=True)
    for item in files:
        name = item['name']
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', name) or name.startswith('.'):
            raise ValueError('Unsafe input filename')
        digest = item.get('sha256')
        if digest and not re.fullmatch(r'[a-fA-F0-9]{64}', digest):
            raise ValueError('Invalid input SHA256')
        print('Downloading remote input:', name, flush=True)
        download(item['url'], WORK / name, digest)
    unpack_archives()
    GAME.parent.mkdir(parents=True, exist_ok=True)
    if kind == 'prepared':
        candidates = [p.parent for p in WORK.rglob('ExeFS') if p.is_dir() and (p.parent / 'RomFS').is_dir()]
        if len(candidates) != 1:
            raise ValueError('Prepared archive must contain exactly one ExeFS/RomFS pair')
        validate_game(candidates[0])
        shutil.move(str(candidates[0]), str(GAME))
    else:
        extract_packages()
        validate_game()
    (GAME / '.ci-verified.json').write_text(json.dumps({'game': CONFIG['game_version'], 'nso_sha256': CONFIG['nso_sha256']}))
    shutil.rmtree(WORK)
    print('Game input ready and eligible for private Actions cache')


def extract_packages():
    keys = WORK / 'prod.keys'
    fd = os.open(keys, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(os.environ['PROD_KEYS'])
    ht = TOOLS / 'bin/hactool'
    prefix = [ht, '-k', keys, '--disablekeywarns', '--suppresskeys']
    ncas = WORK / 'ncas'
    ncas.mkdir()
    try:
        packages = sorted(p for p in WORK.rglob('*') if p.suffix.lower() in ('.nsp', '.xci'))
        if not packages:
            raise ValueError('No NSP/XCI packages in downloads')
        for i, path in enumerate(packages):
            if path.suffix.lower() == '.xci':
                args = ['-t', 'xci', f'--securedir={ncas}', path]
            else:
                args = ['-t', 'pfs0', f'--outdir={ncas}', path]
            run(prefix + args, WORK / f'unpack-{i}.log')
            path.unlink()  # Reclaim space before materializing full RomFS.
        base, update = [], []
        for i, path in enumerate(sorted(ncas.glob('*.nca'))):
            if path.name.endswith('.cnmt.nca'):
                continue
            info = run(prefix + ['-t', 'nca', path], WORK / f'nca-{i}.log')
            if re.search(r'Content Type:\s*Program', info) and re.search(r'Title ID:\s*0100726014352000', info):
                (update if 'BKTR' in info else base).append(path)
        if len(base) != 1 or len(update) != 1:
            raise ValueError('Need exactly one base Program NCA and one update Program NCA')
        temporary = GAME.with_name('Update.partial')
        temporary.mkdir()
        run(prefix + ['-t', 'nca', f'--basenca={base[0]}', f'--exefsdir={temporary / "ExeFS"}', f'--romfsdir={temporary / "RomFS"}', update[0]], WORK / 'extract.log')
        validate_game(temporary)
        temporary.rename(GAME)
    finally:
        keys.unlink(missing_ok=True)


def verify_ipa():
    output = ROOT / 'outputs/D2RMobile-unsigned.ipa'
    info = shell_info(SHELL)
    with zipfile.ZipFile(SHELL) as shell, zipfile.ZipFile(output) as z:
        corrupt = z.testzip()
        if corrupt:
            raise ValueError('Corrupt IPA member: ' + corrupt)
        bases = [n.removesuffix('dm/shell_manifest.txt') for n in shell.namelist() if n.endswith('/dm/shell_manifest.txt')]
        if len(bases) != 1:
            raise ValueError('Shell app path ambiguous')
        base = bases[0]
        members = set(z.namelist())
        required = shell.read(base + 'dm/shell_manifest.txt').decode().splitlines()
        for item in required:
            item = item.strip()
            if not item:
                continue
            target = base + item
            if not (any(n.startswith(target) for n in members) if item.endswith('/') else target in members):
                raise ValueError('Missing IPA content: ' + item)
        guest = z.read(base + 'Frameworks/Guest.framework/Guest')
        if guest[:4] != bytes.fromhex('cffaedfe'):
            raise ValueError('Guest dynamic library is not Mach-O arm64')
        # The packer itself checks the complete shader-source digest against the shell.
        shader_files = [n for n in members if '/msl/b-' + info['CHAIN'] + '/' in n and n.endswith('_b.metallib')]
        if not shader_files:
            raise ValueError('IPA shader library missing')
    digest = sha256(output)
    (output.parent / 'SHA256SUMS.txt').write_text(f'{digest}  {output.name}\n')
    report = {'upstream_commit': CONFIG['upstream_commit'], 'game_version': CONFIG['game_version'], 'switch_version': CONFIG['switch_version'], 'shell_sha256': CONFIG['shell_sha256'], 'shader_source_sha16': info['SHADER_SRC'], 'ipa_sha256': digest, 'ipa_bytes': output.stat().st_size, 'shader_libraries': len(shader_files), 'signed': False}
    (output.parent / 'build-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('IPA verified:', output.stat().st_size, 'bytes;', len(shader_files), 'shader libraries')


if __name__ == '__main__':
    try:
        {'shell': ensure_shell, 'inputs': prepare_game, 'validate-game': validate_game, 'verify-ipa': verify_ipa}[sys.argv[1]]()
    except Exception as error:
        print(f'::error::{error}', file=sys.stderr)
        sys.exit(1)
