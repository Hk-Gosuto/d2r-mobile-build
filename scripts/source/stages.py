"""Generate and validate independent stages before saving their private caches."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ci


def run(*args, env=None):
    subprocess.run([str(a) for a in args], check=True, env=dict(os.environ, **(env or {})))


def receipt(path, key, files, save=False):
    """Only a matching, complete, byte-verified stage may bypass generation."""
    path = Path(path)
    values = {str(p.resolve()): ci.sha256(p) for p in files if p.is_file()}
    if not values:
        return False
    # Paths are stable within this repository's GitHub workspace. Never share this cache publicly.
    value = {'key': key, 'files': values}
    if save:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, sort_keys=True) + '\n')
        return True
    try:
        return json.loads(path.read_text()) == value
    except (OSError, ValueError):
        return False


def rewrite():
    out = ci.DM / 'build/cache/dm/out' / ((ci.ROOT/'upstream/dm/PRODUCT').read_text().strip() + '-touch')
    key = os.environ['REWRITE_KEY']
    files = list(out.glob('*'))
    required = [out / (m + s) for m in ('main', 'sdk') for s in ('.patched.bin', '.gates.tsv', '.fixups.tsv', '.cuts.tsv')]
    marker = out / '.verified.json'
    files = [p for p in files if p != marker and p.suffix != '.log']
    if all(p.is_file() for p in required) and receipt(marker, key, files):
        print('Reused verified rewritten game code', flush=True); return
    shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
    for module in ('main', 'sdk'):
        run(sys.executable, ci.ROOT/'upstream/dm/tools/patch_nso.py', ci.GAME/'ExeFS'/module, out, module,
            env={'DM_RULESET': 'touch-run-v4'})
    if not all(p.is_file() for p in required):
        raise ValueError('Incomplete rewritten game code')
    receipt(marker, key, [p for p in out.iterdir() if p != marker and p.suffix != '.log'], save=True)


def asset_files():
    ios = ci.ROOT/'upstream/dm/ios'
    return [p for base in (ios/'Gen/assets', ios/'Sources/TouchArt') for p in base.rglob('*')
            if p.is_file() and p.name not in ('.stamp', '.verified.json') and '.gen_lock' not in p.parts] + [ios/'Sources/dm_touch_native_art.c']


def assets():
    ios = ci.ROOT/'upstream/dm/ios'; target = ios/'Gen/assets'; marker = target/'.verified.json'
    key = os.environ['ASSETS_KEY']
    # Upstream's stamp includes unrelated iOS build scripts. Our dependency key and
    # byte receipt prove these assets; refresh its stamp without changing upstream code.
    if receipt(marker, key, asset_files()):
        sys.path.insert(0, str(ios/'tools'))
        spec = importlib.util.spec_from_file_location('asset_stamp', ios/'tools/gen_assets.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        (target/'.stamp').write_text(module.stamp(str(ci.GAME/'RomFS')))
        print('Reused verified interface assets', flush=True)
    else:
        (target/'.stamp').unlink(missing_ok=True)
    run(sys.executable, ios/'tools/gen_assets.py', ci.GAME/'RomFS')
    if not (ios/'Sources/dm_touch_native_art.c').is_file():
        raise ValueError('Interface asset generation incomplete')
    receipt(marker, key, asset_files(), save=True)


def shaders():
    up = ci.ROOT/'upstream/dm'; tools = up/'gfx/tools'
    packs = ci.DM/'build/cache/dm/dmsh'; packs.mkdir(parents=True, exist_ok=True)
    if len(list(packs.glob('*.bin'))) != 162:
        env = dict(os.environ, DMX_ROOT=str(ci.GAME/'RomFS/data'))
        paths = subprocess.check_output([sys.executable, str(up/'tools/dmx.py'), 'list', 'data:data/hd/shaders/*.bin'], env=env, text=True)
        for line in paths.splitlines():
            name = line.split('\t')[0]
            if name:
                run(sys.executable, up/'tools/dmx.py', 'get', name, packs/Path(name).name, env={'DMX_ROOT': str(ci.GAME/'RomFS/data')})
    run(sys.executable, tools/'nometal_run.py', tools/'dmsh_build.py', packs, ci.DM/'build/cache/metal_shader_cache',
        env={'IOSOUT': str(ci.DM/'build/ios/dmsh_b'), 'MAIN': str(ci.GAME/'ExeFS/main')})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=('rewrite', 'assets', 'shaders'))
    args = parser.parse_args()
    globals()[args.stage]()
