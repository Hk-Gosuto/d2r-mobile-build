"""Validate cold and cached generation without downloading original game inputs."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import ci
from source.prepared import prepare
from source.runtime_assets import generate


def contents(path):
    with zipfile.ZipFile(path) as archive:
        return {p.filename: hashlib.sha256(archive.read(p)).hexdigest() for p in archive.infolist() if not p.is_dir()}


def sources(path):
    with tarfile.open(path) as archive:
        return {p.name: hashlib.sha256(archive.extractfile(p).read()).hexdigest() for p in archive if p.isfile()}


def run(kind):
    archive = ROOT / 'outputs' / ('D2RMobile-MacPrepared.zip' if kind == 'macos' else 'D2RMobile-Prepared.zip')
    sums = ROOT / 'outputs' / ('MacPrepared-SHA256SUMS.txt' if kind == 'macos' else 'Prepared-SHA256SUMS.txt')
    if ci.sha256(archive) != sums.read_text().split()[0]:
        raise ValueError('Prepared archive checksum mismatch')
    target = ROOT / ('.macos-downloads' if kind == 'macos' else '.prepared-downloads') / 'prepared-input.archive'
    target.parent.mkdir(exist_ok=True); shutil.copy2(archive, target)
    if kind == 'ios':
        started = time.monotonic(); prepare(ROOT); cold = time.monotonic() - started
        cold_report = json.loads((ROOT / 'outputs/source-input-report.json').read_text())
        payload = contents(ROOT / 'outputs/source-payload.zip')
        native = sources(ROOT / 'outputs/native-inputs.tar.gz')
        assert payload == contents(ROOT / '.baseline/source-payload.zip'), 'Cold payload differs from verified build'
        assert native == sources(ROOT / '.baseline/native-inputs.tar.gz'), 'Cold native inputs differ from verified build'
        started = time.monotonic(); prepare(ROOT); warm = time.monotonic() - started
        warm_report = json.loads((ROOT / 'outputs/source-input-report.json').read_text())
        assert payload == contents(ROOT / 'outputs/source-payload.zip'), 'Cached payload differs'
        assert native == sources(ROOT / 'outputs/native-inputs.tar.gz'), 'Cached native inputs differ'
        report = {'platform': kind, 'cold_prepare_seconds': round(cold, 2), 'warm_prepare_seconds': round(warm, 2),
                  'cold_generation_seconds': cold_report['runtime_generation_seconds'],
                  'warm_generation_seconds': warm_report['runtime_generation_seconds'],
                  'payload_and_sources_match_verified_build': True, 'cached_outputs_identical': True}
    else:
        import macos
        macos.import_prepared()
        info = macos.load_prepared(); dm = ROOT / 'upstream/dm'; workspace = ROOT / '.macos-runtime'
        cold = generate(dm, ROOT / '.macos-prepared/romfs-inputs.zip', workspace, macos=True,
                        headers=ROOT / '.macos-prepared/generated', baseline=info['source_commit'])
        cache = ci.sha256(ROOT / '.interface-cache/interface.zip')
        warm = generate(dm, ROOT / '.macos-prepared/romfs-inputs.zip', workspace, macos=True,
                        headers=ROOT / '.macos-prepared/generated', baseline=info['source_commit'])
        assert ci.sha256(ROOT / '.interface-cache/interface.zip') == cache
        macos.build()
        report = {'platform': kind, 'cold_generation_seconds': cold, 'warm_generation_seconds': warm,
                  'cached_outputs_identical': True, 'both_macos_variants_built': True}
    (ROOT / 'outputs/interface-cache-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    run(sys.argv[1])
