"""Download and safely prepare one user-supplied ExeFS/RomFS archive."""
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tarfile
from urllib.parse import urlsplit
import zipfile

import ci

ARCHIVE = ci.RAW / 'game-input.archive'
MAX_EXPANDED_BYTES = 24 * 1024**3


def settings():
    url = os.environ.get('GAME_ARCHIVE_URL', '').strip()
    digest = os.environ.get('GAME_ARCHIVE_SHA256', '').strip().lower()
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('GAME_ARCHIVE_URL must be an HTTPS direct download URL')
    if not re.fullmatch(r'[a-f0-9]{64}', digest):
        raise ValueError('GAME_ARCHIVE_SHA256 must contain the archive SHA-256')
    return url, digest


def download():
    url, digest = settings()
    if ARCHIVE.is_file() and ci.sha256(ARCHIVE) == digest:
        print('Reusing verified original archive; download skipped', flush=True)
        return
    ci.download(url, ARCHIVE, digest)
    print('Original archive downloaded and verified; ready to cache before extraction', flush=True)


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
    _, digest = settings()
    marker = ci.GAME / '.input-archive-sha256'
    if ci.GAME.exists():
        if not marker.is_file() or marker.read_text().strip() != digest:
            raise ValueError('Prepared game cache belongs to different input')
        ci.validate_game()
        print('Reusing verified ExeFS/RomFS; extraction skipped', flush=True)
        return
    if not ARCHIVE.is_file() or ci.sha256(ARCHIVE) != digest:
        raise ValueError('Verified original archive missing; download it first')
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
        marker.write_text(digest + '\n')
        print('ExeFS/RomFS extracted and validated; original archive retained', flush=True)
    except Exception:
        shutil.rmtree(ci.GAME, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


if __name__ == '__main__':
    try:
        {'download': download, 'prepare': prepare}[sys.argv[1]]()
    except Exception as exc:
        # Archive member names and downloader exception strings can contain user data.
        message = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        print('::error::' + message, file=sys.stderr)
        sys.exit(1)
