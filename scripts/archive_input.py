"""Download and safely prepare one user-supplied ExeFS/RomFS archive."""
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import tarfile
import zipfile

import ci
from input_config import download_file, input_identity, settings

ARCHIVE = ci.RAW / 'game-input.archive'
MAX_EXPANDED_BYTES = 24 * 1024**3


def cached(url, digest, verify=True):
    if not ARCHIVE.is_file():
        return False
    if digest and verify:
        return ci.sha256(ARCHIVE) == digest
    try:
        marker = json.loads(ARCHIVE.with_suffix('.json').read_text())
        return (isinstance(marker, dict) and
                marker.get('identity') == input_identity(url, digest) and
                marker.get('bytes') == ARCHIVE.stat().st_size and marker['bytes'] > 0)
    except (OSError, ValueError, TypeError):
        return False


def download():
    url, digest = settings()
    if cached(url, digest):
        print('Reusing completed original archive; download skipped', flush=True)
        return
    download_file(url, ARCHIVE, digest or None)
    if ARCHIVE.stat().st_size == 0:
        raise ValueError('Downloaded archive is empty')
    marker = ARCHIVE.with_suffix('.json')
    partial = marker.with_suffix('.json.part')
    partial.write_text(json.dumps({'identity': input_identity(url, digest),
                                   'bytes': ARCHIVE.stat().st_size}) + '\n')
    partial.replace(marker)
    print('Archive downloaded; SHA-256 ' + ('verified' if digest else 'not requested') +
          '; ready to cache before extraction', flush=True)


def safe_members(members):
    """Check every path and size before writing any member."""
    seen, total = set(), 0
    for name, size, is_directory, is_regular in members:
        if is_directory and name in ('.', './'):
            continue
        path = PurePosixPath(name)
        if ('\\' in name or '\x00' in name or path.is_absolute() or
                '..' in path.parts or not path.parts or ':' in path.parts[0]):
            raise ValueError('Unsafe archive path')
        normalized = str(path).casefold()
        if normalized in seen or (not is_directory and not is_regular):
            raise ValueError('Duplicate path, link or special file in archive')
        seen.add(normalized)
        total += size
        if size < 0 or total > MAX_EXPANDED_BYTES:
            raise ValueError('Archive exceeds the supported extracted size')
    return total


def extract(archive, target):
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as source:
            members = source.infolist()
            total = safe_members((m.filename, m.file_size, m.is_dir(),
                                  stat.S_IFMT(m.external_attr >> 16) in (0, stat.S_IFREG))
                                 for m in members)
            if shutil.disk_usage(target).free < total + 1024**3:
                raise ValueError('Not enough free disk space to extract the archive')
            for member in members:
                dest = target / member.filename
                if member.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with source.open(member) as src, dest.open('xb') as dst:
                        shutil.copyfileobj(src, dst, 8 * 1024**2)
    elif tarfile.is_tarfile(archive):
        with tarfile.open(archive) as source:
            members = source.getmembers()
            total = safe_members((m.name, m.size, m.isdir(), m.isfile()) for m in members)
            if shutil.disk_usage(target).free < total + 1024**3:
                raise ValueError('Not enough free disk space to extract the archive')
            for member in members:
                if member.isdir() and member.name in ('.', './'):
                    continue
                dest = target / member.name
                if member.isdir():
                    dest.mkdir(parents=True, exist_ok=True)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with source.extractfile(member) as src, dest.open('xb') as dst:
                        shutil.copyfileobj(src, dst, 8 * 1024**2)
    else:
        raise ValueError('Expected a ZIP or tar archive containing ExeFS and RomFS')


def prepare():
    url, digest = settings()
    identity = input_identity(url, digest)
    marker = ci.GAME / '.input-archive-id'
    if ci.GAME.exists():
        if not marker.is_file() or marker.read_text().strip() != identity:
            raise ValueError('Prepared game cache belongs to different input')
        ci.validate_game()
        print('Reusing verified ExeFS/RomFS; extraction skipped', flush=True)
        return
    if not cached(url, digest, verify=False):
        raise ValueError('Completed original archive missing; download it first')
    temporary = ci.GAME.with_name('input.partial')
    shutil.rmtree(temporary, ignore_errors=True)
    try:
        extract(ARCHIVE, temporary)
        candidates = [p.parent for p in temporary.rglob('ExeFS')
                      if p.is_dir() and (p.parent / 'RomFS').is_dir()]
        if len(candidates) != 1:
            raise ValueError('Archive must contain exactly one ExeFS/RomFS pair')
        game = candidates[0]
        ci.validate_game(game)
        ci.GAME.parent.mkdir(parents=True, exist_ok=True)
        # Only retain the actual game directories, not unrelated files or credentials.
        ci.GAME.mkdir()
        for name in ('ExeFS', 'RomFS'):
            shutil.move(str(game / name), str(ci.GAME / name))
        marker.write_text(identity + '\n')
        print('ExeFS/RomFS extracted and validated; original archive retained', flush=True)
    except Exception:
        shutil.rmtree(ci.GAME, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def resolve():
    url, digest = settings()
    with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
        stream.write('input_revision=' + input_identity(url, digest) + '\n')
    print('Input identity resolved; SHA-256 ' + ('enabled' if digest else 'not configured'))


if __name__ == '__main__':
    try:
        {'resolve': resolve, 'download': download, 'prepare': prepare}[sys.argv[1]]()
    except Exception as exc:
        # Archive member names and downloader exception strings can contain user data.
        message = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        print('::error::' + message, file=sys.stderr)
        sys.exit(1)
