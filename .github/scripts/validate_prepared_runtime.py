"""One-time migration check using retained inputs; never publishes a Release."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import ci
from archive_input import extract
from input_config import download_file
from source.prepared import write
from source.upgrade_prepared import upgrade, upgrade_macos


def pack(directory, destination):
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for path in sorted(directory.rglob('*')):
            if path.is_file():
                output.write(path, path.relative_to(directory).as_posix())


def prepare():
    original = ROOT / 'legacy-source/.dm-work/data/switch/3.3.94012'
    ios = ROOT / '.ios-runtime-prepared'
    extract(ROOT / '.prepared-downloads/prepared-input.archive', ios)
    legacy = ROOT / 'legacy-index.tsv'
    download_file('https://github.com/jiayx/d2r-mobile-build/releases/download/legacy-3.3.94012-3e82ab6dec4dee197c05cfc558f60d794e62394f4d843c908c2b91837fa6f9ce/pack_index.tsv', legacy,
                  'ba0e16cd71fac430c6f7ee1cced2a2e8a28d17dce3cb75070a8f9965d9907056')
    info = upgrade(ios, original, legacy, ROOT / 'upstream')
    macos = ROOT / '.macos-prepared'
    extract(ROOT / '.macos-downloads/prepared-input.archive', macos, max_members=100000)
    upgrade_macos(macos, original, ROOT / 'upstream')
    outputs = ROOT / 'outputs'
    outputs.mkdir(exist_ok=True)
    ios_zip = outputs / 'D2RMobile-Prepared.zip'
    mac_zip = outputs / 'D2RMobile-MacPrepared.zip'
    pack(ios, ios_zip)
    pack(macos, mac_zip)
    (outputs / 'Prepared-SHA256SUMS.txt').write_text(ci.sha256(ios_zip) + '  ' + ios_zip.name + '\n')
    (outputs / 'MacPrepared-SHA256SUMS.txt').write_text(ci.sha256(mac_zip) + '  ' + mac_zip.name + '\n')
    shutil.copy2(ios_zip, ROOT / '.prepared-downloads/prepared-input.archive')
    os.environ['INPUT_REVISION'] = hashlib.sha256(ci.sha256(ios_zip).encode()).hexdigest()
    from source.prepared import prepare as prepare_build
    prepare_build(ROOT)
    write(outputs / 'prepared-migration-report.json', {'original_input_bytes': info['runtime_input_bytes'],
          'ios_bytes': ios_zip.stat().st_size, 'macos_bytes': mac_zip.stat().st_size,
          'source_commit': ci.CONFIG['upstream_commit'], 'heavy_outputs_recompiled': False,
          'game_archive_downloaded': False, 'device_tested': False})


if __name__ == '__main__':
    prepare()
