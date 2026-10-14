"""Reuse verified input metadata only when bound to the exact archive SHA-256."""
import json
import hashlib
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import ci
import export_resources
from input_config import settings, input_identity

CACHE=ci.ROOT/'.input-metadata/verified-input.json'


def checksum(value):
    return hashlib.sha256(json.dumps({k:v for k,v in value.items() if k!='record_sha256'},sort_keys=True).encode()).hexdigest()


def restore():
    url,digest=settings();reused=False
    try:
        saved=json.loads(CACHE.read_text())
        manifest=saved['resources']
        reused=(saved['record_sha256']==checksum(saved) and bool(digest) and saved['archive_sha256']==digest and saved['input_id']==input_identity(url,digest)
                and saved['nso_sha256']==ci.CONFIG['nso_sha256']
                and manifest['game_version']==ci.CONFIG['game_version']
                and manifest['switch_version']==ci.CONFIG['switch_version']
                and {f['name']:f['bytes'] for f in manifest['files']}==ci.resource_sizes())
        export_resources.resource_identity(manifest)
        import re
        reused=reused and re.fullmatch('[a-f0-9]{64}',saved['build_manifest_sha256']) is not None
        if reused:
            out=ci.ROOT/'outputs';out.mkdir(exist_ok=True)
            (out/'verified-input.json').write_text(json.dumps(saved,indent=2)+'\n')
            (out/'resource-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
            print('Reused SHA-256-bound input metadata; archive restore and extraction can be skipped',flush=True)
    except (OSError,ValueError,KeyError,TypeError):
        reused=False
    with open(os.environ['GITHUB_OUTPUT'],'a') as out:out.write('reused='+str(reused).lower()+'\n')
    return reused


def save():
    url,digest=settings()
    manifest=export_resources.scan_resources(ci.GAME)
    value={'archive_sha256':digest,'input_id':input_identity(url,digest),'nso_sha256':ci.CONFIG['nso_sha256'],
           'build_manifest_sha256':ci.sha256(ci.GAME/'RomFS/data/build_manifest.psv'),'resources':manifest}
    value['record_sha256']=checksum(value)
    out=ci.ROOT/'outputs';out.mkdir(exist_ok=True)
    (out/'verified-input.json').write_text(json.dumps(value,indent=2)+'\n')
    (out/'resource-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    CACHE.parent.mkdir(exist_ok=True);CACHE.write_text(json.dumps(value,indent=2)+'\n')


if __name__=='__main__':
    save() if sys.argv[1:] == ['save'] else restore()
