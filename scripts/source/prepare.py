"""Generate matching game payload and native compile inputs without a prebuilt IPA."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tarfile
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import ci

CACHE = ci.DM/'build/payload-cache'
GENERATED = ('host/dm_vault_tab.h', 'host/dm_hud_exp.h', 'host/dm_bright_levels.inc',
             'ios/Sources/dm_touch_native_art.c')


def cached_payload(key):
    try:
        info = json.loads((CACHE/'receipt.json').read_text())
        if info['key'] != key:
            return None
        expected = {'source-payload.zip', *('generated/'+n for n in GENERATED)}
        if set(info['files']) != expected:
            return None
        for name, digest in info['files'].items():
            if ci.sha256(CACHE/name) != digest:
                return None
        return info
    except (OSError, ValueError, KeyError):
        return None


def run(*args, **kwargs):
    return subprocess.check_output([str(a) for a in args], text=True, **kwargs)


def main():
    up=ci.ROOT/'upstream'; dm=up/'dm'; ios=dm/'ios'; out=ci.ROOT/'outputs'
    out.mkdir(exist_ok=True)
    romfs=ci.GAME/'RomFS'
    chain=run(sys.executable,dm/'gfx/tools/nometal_run.py',dm/'gfx/tools/dmsh_chain.py').strip().splitlines()[-1]
    product=(dm/'PRODUCT').read_text().strip()
    key=os.environ['PAYLOAD_KEY']
    cached=cached_payload(key)
    payload=out/'source-payload.zip'
    if cached:
        if cached['chain'] != chain or cached['product'] != product:
            raise ValueError('Cached payload does not match selected generation inputs')
        for name in GENERATED:
            target=dm/name; target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(CACHE/'generated'/name,target)
        shutil.copy2(CACHE/'source-payload.zip',payload)
        shader_digest=cached['shader_source_sha16']
        print('Reused verified common payload; skipped generation and compression',flush=True)
    else:
        generate_payload(dm, ios, romfs, chain, product, payload)
        (dm/'host/dm_bright_levels.inc').write_text(run(sys.executable,dm/'tools/gen_bright_levels.py',romfs))
        shader_digest=run(sys.executable,dm/'tools/d2rm_pack.py','--src-digest',ci.DM/'build/cache/metal_shader_cache'/('b-'+chain)).strip()
        CACHE.mkdir(parents=True,exist_ok=True)
        shutil.copy2(payload,CACHE/'source-payload.zip')
        for name in GENERATED:
            target=CACHE/'generated'/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(dm/name,target)
        files={'source-payload.zip':ci.sha256(CACHE/'source-payload.zip')}
        files.update({'generated/'+n:ci.sha256(CACHE/'generated'/n) for n in GENERATED})
        (CACHE/'receipt.json').write_text(json.dumps({'key':key,'files':files,'chain':chain,'product':product,
                                                   'shader_source_sha16':shader_digest},indent=2)+'\n')
    # Native sources and all per-run metadata are always taken from the selected source.
    native=ci.DM/'build/native-source/dm'
    shutil.rmtree(native.parent,ignore_errors=True)
    shutil.copytree(dm,native,ignore=shutil.ignore_patterns('.git','Gen','TouchArt','__pycache__','bin','obj'))
    run(sys.executable,ios/'tools/shell_stubs.py','stubs',native)
    source_commit=run('git','-C',up,'rev-parse','HEAD').strip()
    report={'tools_commit':os.environ.get('TOOLS_COMMIT'), 'input_identity':os.environ.get('INPUT_REVISION'),
            'source_repository':os.environ['SOURCE_REPOSITORY'],'source_commit':source_commit,
            'patch_sha256':ci.CONFIG.get('source_patch_sha256'), 'product':product,'shader_chain':chain,
            'payload_sha256':ci.sha256(payload),'legacy_pack':json.loads((Path(os.environ['D2RM_ASTC_PACK'])/'pack.json').read_text()),
            'shader_source_sha16':shader_digest,'payload_reused':cached is not None}
    validation=out/'legacy-validation.json'
    if validation.is_file():
        report['legacy_conversion_validation']=json.loads(validation.read_text())
    (out/'build-context.json').write_text(json.dumps(ci.CONFIG,indent=2)+'\n')
    (out/'source-input-report.json').write_text(json.dumps(report,indent=2)+'\n')
    with tarfile.open(out/'native-inputs.tar.gz','w:gz') as tf:
        def include(item):
            parts=Path(item.name).parts
            if any(p in ('.git','Gen','TouchArt','__pycache__','bin','obj') for p in parts):return None
            return item
        tf.add(native,arcname='upstream/dm',filter=include)
    print('Prepared source build inputs:',source_commit,product,chain,flush=True)


def generate_payload(dm, ios, romfs, chain, product, payload):
    run(sys.executable,ios/'tools/gen_assets.py',romfs)
    manifest=[f'msl/b-{chain}/', 'romfs_overlay/', 'romfs_overlay_variants/',
              'hud_v4_ui/', 'mapgoal/', 'mercslots/', 'Frameworks/Guest.framework/',
              'dm/derived.tsv', 'dm/main.cuts.tsv', 'dm/c1_full.tsv']
    manifest += [f'dm/{m}{suffix}' for m in ('main','sdk') for suffix in ('.fixups.tsv','.gates.tsv')]
    manifest += sorted(p.name for p in (ios/'Sources/TouchArt').iterdir() if p.is_file())
    # This file is only a generation contract: it contains no executable and is never delivered.
    contract=ci.DM/'build/source-contract.zip'; contract.parent.mkdir(parents=True,exist_ok=True)
    base='Payload/DmIOS.app/'
    with zipfile.ZipFile(contract,'w') as z:
        z.writestr(base+'Info.plist',plistlib.dumps({'CFBundleExecutable':'DmIOS','MinimumOSVersion':'26.0'}))
        z.writestr(base+'dm/shell_manifest.txt','\n'.join(manifest)+'\n')
        z.writestr(base+'dm/shell_info.txt',f'PRODUCT={product}\nCHAIN={chain}\nKIND=ios\n')
    subprocess.run([sys.executable,str(dm/'tools/d2rm_pack.py'),str(contract),str(ci.GAME),str(payload)],check=True)
    # Carry the upstream and bundled third-party license notices into the final app.
    with zipfile.ZipFile(payload, 'a', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(ci.ROOT/'upstream/LICENSE',base+'Licenses/d2r-mobile-MIT.txt')
        for directory in ('third_party','gfx/nvn/include'):
            for path in (dm/directory).rglob('*'):
                if path.is_file() and (path.name.upper().startswith(('LICENSE','COPYING','NOTICE')) or path.name=='nvn.h'):
                    archive.write(path,base+'Licenses/'+path.relative_to(dm).as_posix())


if __name__=='__main__':main()
