"""Resolve public Drive share links or HTTPS files without logging input URLs."""
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import parse_qs, urlsplit

import ci


def https_url(value):
    if not isinstance(value, str):
        raise ValueError('url must be an HTTPS URL')
    value = value.strip()
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or
            parsed.password or any(c in value for c in '\r\n\x00')):
        raise ValueError('url must be an HTTPS URL without embedded credentials')
    return value


def drive_file_id(url):
    parsed = urlsplit(url)
    if parsed.hostname not in ('drive.google.com', 'docs.google.com'):
        return None
    match = re.fullmatch(r'/file/d/([A-Za-z0-9_-]+)(?:/[^/]*)?/?', parsed.path)
    file_id = match[1] if match else parse_qs(parsed.query).get('id', [''])[0]
    if not re.fullmatch(r'[A-Za-z0-9_-]+', file_id):
        raise ValueError('Use a Google Drive file share link, not a folder link')
    return file_id


def download_file(url, destination, expected=None, max_bytes=None):
    url = https_url(url)
    destination = Path(destination)
    if drive_file_id(url) is None:
        ci.download(url, destination, expected, max_bytes=max_bytes)
        return
    import gdown
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + '.part')
    hasher = hashlib.sha256()
    last = time.monotonic()

    def progress(done, total):
        nonlocal last
        if max_bytes and done > max_bytes:
            raise ValueError('Download exceeds the supported size')
        if time.monotonic() - last >= 30:
            print(f'Archive download: {done / 1e9:.2f} GB' +
                  (f' / {total / 1e9:.2f} GB' if total else ''), flush=True)
            last = time.monotonic()

    try:
        result = gdown.download(url=url, output=str(partial), quiet=True,
                                use_cookies=False, resume=True, hasher=hasher,
                                timeout=(30, 120), retries=4, progress=progress)
        if result is None or not partial.is_file() or not partial.stat().st_size:
            raise RuntimeError('Google Drive download did not complete')
        if expected and hasher.hexdigest() != expected:
            partial.unlink()
            raise ValueError('Download SHA256 mismatch: ' + destination.name)
        partial.replace(destination)
    except ValueError:
        raise
    except Exception:
        # gdown exceptions may contain URLs; keep them out of Actions logs.
        raise RuntimeError('Google Drive download failed; check link sharing and download quota') from None


def parse_checksum(text):
    entries = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'([A-Fa-f0-9]{64})(?:\s+\*?(.+))?', line)
        if not match:
            raise ValueError('Expected SHA256SUMS text containing one archive checksum')
        entries.append(match[1].lower())
    if len(entries) != 1:
        raise ValueError('Checksum URL must contain exactly one archive checksum')
    return entries[0]


def settings():
    try:
        config = json.loads(os.environ.get('PREPARED_INPUT', ''))
    except ValueError:
        raise ValueError('PREPARED_INPUT must be a JSON object with url and sha256') from None
    if not isinstance(config, dict) or not isinstance(config.get('url'), str):
        raise ValueError('PREPARED_INPUT must contain a download url')
    if set(config) - {'url', 'sha256', 'sha256_url'}:
        raise ValueError('PREPARED_INPUT supports url, sha256 and sha256_url')
    url = https_url(config['url'])
    drive_file_id(url)
    digest = config.get('sha256')
    if digest is None:
        digest = ''
    if not isinstance(digest, str):
        raise ValueError('sha256 must be a string or null')
    digest = digest.strip().lower()
    if digest and not re.fullmatch(r'[a-f0-9]{64}', digest):
        raise ValueError('sha256 must be empty or contain 64 hexadecimal characters')
    checksum_url = config.get('sha256_url')
    if checksum_url is not None:
        if digest:
            raise ValueError('Set sha256 or sha256_url, not both')
        checksum_url = https_url(checksum_url)
        with tempfile.TemporaryDirectory(prefix='d2r-checksum-') as temporary:
            path = Path(temporary) / 'SHA256SUMS.txt'
            download_file(checksum_url, path, max_bytes=64 * 1024)
            digest = parse_checksum(path.read_text(encoding='utf-8-sig'))
    revision = input_identity(url, digest)
    if os.environ.get('INPUT_REVISION', revision) != revision:
        raise ValueError('Archive checksum changed since cache resolution; start a new run')
    return url, digest


def input_identity(url, digest):
    return hashlib.sha256((digest if digest else 'url:' + url).encode()).hexdigest()
