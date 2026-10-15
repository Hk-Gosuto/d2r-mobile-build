"""Generate interface resources from the selected source and small original inputs."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

from source.romfs_input import restore

BASE = 'Payload/DmIOS.app/'
HEAVY_DM = {'c1_full.tsv', 'bootlist.tsv', 'main.cuts.tsv',
            'main.fixups.tsv', 'main.gates.tsv', 'sdk.fixups.tsv', 'sdk.gates.tsv'}


def heavy_member(name):
    relative = name.removeprefix(BASE)
    return relative.startswith(('msl/', 'Frameworks/Guest.framework/')) or relative in {'dm/' + n for n in HEAVY_DM}


def generate(dm, inputs, workspace, *, macos=False, legacy=None):
    started = time.monotonic()
    romfs = restore(inputs, workspace / 'RomFS')
    environment = dict(os.environ, DM_ROOT=str(workspace), DM_ROMFS_SRC=str(romfs))
    environment.pop('DM_PC_DATA', None)
    environment.pop('DM_REQUIRE_PC_ART', None)
    if macos:
        environment['DM_OVERLAY_MAC'] = '1'
    if legacy:
        environment['DM_ASTC_PACK'] = str(legacy)
    def run(script, *args, **kwargs):
        subprocess.run([sys.executable, str(dm / script), *map(str, args)],
                       env=environment, check=True, **kwargs)
    run('ios/tools/gen_assets.py', romfs)
    for output, script in (('dm_vault_tab.h', 'ios/tools/gen_vault_table.py'),
                           ('dm_hud_exp.h', 'ios/tools/gen_hud_exp.py'),
                           ('dm_bright_levels.inc', 'tools/gen_bright_levels.py')):
        with (dm / 'host' / output).open('w') as stream:
            run(script, romfs, stdout=stream)
    overlay = workspace / 'romfs_overlay'
    for name in ('romfs_overlay', 'romfs_overlay_variants', 'romfs_overlay_astc', 'romfs_overlay_astc_variants'):
        shutil.rmtree(workspace / name, ignore_errors=True)
    run('ios/tools/gen_romfs_overlay.py', romfs, overlay)
    return round(time.monotonic() - started, 2)


def ios_payload(directory, info, dm, destination, workspace):
    seconds = generate(dm, directory / 'romfs-inputs.zip', workspace, legacy=directory / 'legacy')
    stage = workspace / 'payload'
    shutil.rmtree(stage, ignore_errors=True)
    (stage / 'dm').mkdir(parents=True)
    with zipfile.ZipFile(directory / 'source-payload.zip') as source:
        for item in source.infolist():
            if not item.is_dir() and heavy_member(item.filename):
                path = stage / item.filename.removeprefix(BASE)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(source.read(item))
                path.chmod(0o755 if path.name == 'Guest' else 0o644)
    for name in ('romfs_overlay', 'romfs_overlay_variants', 'romfs_overlay_astc', 'romfs_overlay_astc_variants'):
        shutil.copytree(workspace / name, stage / name)
    for name, source in (('hud_v4_ui', 'v4/hud_v4_ui'), ('mapgoal', 'mapgoal'), ('mercslots', 'mercslots')):
        shutil.copytree(dm / 'ios/Gen/assets/NativeHUD' / source, stage / name)
    for path in (dm / 'ios/Sources/TouchArt').iterdir():
        if path.is_file():
            shutil.copy2(path, stage / path.name)
    subprocess.run([sys.executable, str(dm / 'ios/tools/shell_stubs.py'), 'data', str(dm),
                    str(stage / 'dm/derived.tsv')], check=True)
    chain = info['payload']['shader_chain']
    product = (dm / 'PRODUCT').read_text().strip()
    (stage / 'dm/shell_info.txt').write_text(f'PRODUCT={product}\nCHAIN={chain}\nKIND=ios\n')
    (stage / 'dm/pack_info.txt').write_text(f'PRODUCT={product}\n')
    manifest = [p.name + '/' for p in stage.iterdir() if p.is_dir() and p.name != 'dm']
    manifest += [p.relative_to(stage).as_posix() for p in (stage / 'dm').iterdir() if p.is_file()]
    manifest += [p.name for p in stage.iterdir() if p.is_file()]
    (stage / 'dm/shell_manifest.txt').write_text('\n'.join(sorted(manifest)) + '\n')
    licenses = [(dm.parent / 'LICENSE', 'd2r-mobile-MIT.txt')]
    licenses += [(p, p.relative_to(dm).as_posix()) for folder in ('third_party', 'gfx/nvn/include')
                 for p in (dm / folder).rglob('*') if p.is_file()
                 and (p.name.upper().startswith(('LICENSE', 'COPYING', 'NOTICE')) or p.name == 'nvn.h')]
    for source, name in licenses:
        path = stage / 'Licenses' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, path)
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as output:
        for path in sorted(stage.rglob('*')):
            if path.is_file():
                output.write(path, BASE + path.relative_to(stage).as_posix())
    return seconds
