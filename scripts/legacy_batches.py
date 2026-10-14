"""Distribute intact upstream ASTC batches without changing their pixels or ordering."""
import argparse
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile

import ci
import legacy_pack as legacy
import publish_release as publish

DESCRIPTOR = 'data/hd/texture_desc_cache.json'


def safe_path(name):
    p=PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or str(p)!=name:
        raise ValueError('Unsafe conversion path')
    return name


def load_converter():
    legacy.ensure_converter()
    path=legacy.CONVERTER/'dm/tools/astc_pack.py'
    sys.path.insert(0,str(legacy.CONVERTER/'dm/ios/tools'))
    spec=importlib.util.spec_from_file_location('frozen_astc_converter',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def convert(module, romfs, output, encoder, index, count, recipe_id):
    if not 0 <= index < count or count != 2:
        raise ValueError('Expected one of two conversion workers')
    original=module.encode_batch; batches=[]; owned=set()

    def encode(enc,preset,srgb,px,tmp):
        caller=inspect.currentframe().f_back
        kind=caller.f_code.co_name
        if kind=='flush': paths=[safe_path(item[0]) for item in caller.f_locals['items']]
        elif kind=='desc_cache': paths=[safe_path(item[0]['filename'].lower()) for item in caller.f_locals['items']]
        else: raise ValueError('Frozen converter batch interface changed')
        number=len(batches)
        batches.append({'number':number,'kind':kind,'srgb':srgb,'paths':paths,
                        'shape':list(px.shape),'pixels_sha256':hashlib.sha256(px.tobytes()).hexdigest()})
        if number % count == index:
            if kind=='flush': owned.update(paths)
            return original(enc,preset,srgb,px,tmp)
        # Non-owned placeholders are never packaged. Walking all inputs preserves
        # upstream batching, thumbnail grouping and replacement-table ordering.
        return bytes(len(px)*16),px

    module.encode_batch=encode
    previous=sys.argv
    try:
        sys.argv=[str(module.__file__),str(romfs),str(output),'--astcenc',str(encoder),'--preset','thorough']
        module.main()
    finally:
        sys.argv=previous;module.encode_batch=original
    order=[line.split('\t')[0] for line in (output/'repl.tsv').read_text().splitlines()]
    if len(order)!=len(set(order)) or order[-1]!=DESCRIPTOR:
        raise ValueError('Unexpected converter replacement order')
    for path in order:
        if path not in owned and path!=DESCRIPTOR:
            (output/'files'/path).unlink()
    selected=owned|{DESCRIPTOR}
    record={'schema':1,'index':index,'count':count,'recipe_id':recipe_id,'batches':batches,'order':order,
            'files':{p:ci.sha256(output/'files'/p) for p in sorted(selected)}}
    (output/'batch-plan.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


def merge(directories, output, recipe_id):
    records=[json.loads((p/'batch-plan.json').read_text()) for p in directories]
    if sorted(r['index'] for r in records)!=[0,1]:
        raise ValueError('Missing or duplicated conversion worker')
    by_index={r['index']:(p,r) for p,r in zip(directories,records)}
    first=by_index[0][1]; owners={}; thumbnail_owners={}
    for p,r in by_index.values():
        if r['schema']!=1 or r['count']!=2 or r['recipe_id']!=recipe_id or r['order']!=first['order'] or r['batches']!=first['batches']:
            raise ValueError('Conversion workers disagree on original batches')
        expected={DESCRIPTOR}
        for batch in r['batches']:
            if batch['number']%2==r['index'] and batch['kind']=='flush': expected.update(batch['paths'])
        if set(r['files'])!=expected:
            raise ValueError('Incomplete owned conversion outputs')
        for name,digest in r['files'].items():
            path=p/'files'/safe_path(name)
            if ci.sha256(path)!=digest: raise ValueError('Corrupt conversion output: '+name)
    for batch in first['batches']:
        mapping=owners if batch['kind']=='flush' else thumbnail_owners
        for name in batch['paths']: mapping[safe_path(name)]=batch['number']%2
    if set(owners)|{DESCRIPTOR}!=set(first['order']):
        raise ValueError('Conversion coverage mismatch')
    output.mkdir(parents=True,exist_ok=True)
    descriptors={i:json.loads((p/'files'/DESCRIPTOR).read_text()) for i,(p,_) in by_index.items()}
    if len(descriptors[0])!=len(descriptors[1]): raise ValueError('Thumbnail descriptor count mismatch')
    combined=descriptors[0]
    for n,entry in enumerate(combined):
        other=descriptors[1][n]
        if {k:v for k,v in entry.items() if k!='thumbnailBase64'}!={k:v for k,v in other.items() if k!='thumbnailBase64'}:
            raise ValueError('Thumbnail descriptor mismatch')
        owner=thumbnail_owners.get(entry['filename'].lower())
        if owner is not None: entry['thumbnailBase64']=descriptors[owner][n]['thumbnailBase64']
    for name in first['order']:
        dest=output/'files'/safe_path(name);dest.parent.mkdir(parents=True,exist_ok=True)
        if name==DESCRIPTOR: dest.write_text(json.dumps(combined,ensure_ascii=False,separators=(',',':')))
        else: shutil.copy2(by_index[owners[name]][0]/'files'/name,dest)
    (output/'repl.tsv').write_text(''.join(f'{p}\t{output/"files"/p}\n' for p in first['order']))


def encoder():
    archive=ci.TOOLS/'astcenc-5.2.0-linux-x64.zip'
    if not archive.exists() or ci.sha256(archive)!=ci.CONFIG['astc_encoder_sha256']:
        ci.download(ci.CONFIG['astc_encoder_url'],archive,ci.CONFIG['astc_encoder_sha256'])
    import zipfile
    out=ci.TOOLS/'bin/astcenc-avx2';out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:out.write_bytes(z.read('bin/astcenc-avx2'))
    out.chmod(0o755);return out


def unpack(archive, directory):
    with tarfile.open(archive) as tf:
        seen=set(); total=0
        for member in tf:
            name=safe_path(member.name)
            if not member.isfile() or name in seen:raise ValueError('Unsafe conversion archive')
            seen.add(name); total+=member.size
            if total>3*1024**3:raise ValueError('Conversion archive too large')
            path=directory/name;path.parent.mkdir(parents=True,exist_ok=True)
            with tf.extractfile(member) as src,path.open('wb') as dst:shutil.copyfileobj(src,dst,8*1024**2)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('convert','merge'));parser.add_argument('--index',type=int,default=0)
    args=parser.parse_args();repo=legacy.require_private()
    plan=json.loads((publish.OUT/'legacy-plan.json').read_text());recipe_id=plan['recipe_id']
    if args.mode=='convert':
        module=load_converter();out=ci.DM/'build/legacy-worker'
        record=convert(module,ci.GAME/'RomFS',out,encoder(),args.index,2,recipe_id)
        publish.OUT.mkdir(exist_ok=True)
        with tarfile.open(publish.OUT/f'legacy-worker-{args.index}.tar','w') as tf:
            tf.add(out/'batch-plan.json',arcname='batch-plan.json')
            for name in record['files']:tf.add(out/'files'/name,arcname='files/'+name)
    else:
        legacy.ensure_converter();roots=[]
        for i in range(2):
            dest=ci.DM/f'build/legacy-worker-{i}';unpack(publish.OUT/f'legacy-worker-{i}.tar',dest);roots.append(dest)
        work=ci.DM/'build/legacy/work';merge(roots,work,recipe_id)
        tools=legacy.CONVERTER/'dm/tools'
        for command in ([sys.executable,str(tools/'casc_overlay.py'),'pack',str(ci.GAME/'RomFS'),str(legacy.PACK),str(work/'repl.tsv'),'0-8'],
                        [sys.executable,str(tools/'astc_pack.py'),'finalize',str(legacy.PACK)]):
            subprocess.run(command,check=True)
        publish.STAGE.mkdir(exist_ok=True)
        ref=legacy.reference(repo,publish.release_info(repo,plan['tag']),recipe_id)
        if ref:
            info=legacy.validate_pack(legacy.PACK)
            index=next(a for a in ref['assets'] if a['name']=='pack_index.tsv')
            if info!=ref['pack'] or ci.sha256(legacy.PACK/'pack_index.tsv')!=index['sha256']:
                raise ValueError('Parallel conversion differs from the existing single-worker pack')
            (publish.OUT/'legacy-validation.json').write_text(json.dumps({'recipe_id':recipe_id,'parallel_shards':2,
                'pack_sha256':info['sha256'],'index_sha256':index['sha256'],'matches_existing':True},indent=2)+'\n')
            print('Parallel conversion exactly matches existing pack and index:',info['sha256'],flush=True)
        else:
            ref=legacy.publish_pack(repo,recipe_id,plan['tag'],prepared=True)
        (publish.OUT/'legacy-resources.json').write_text(json.dumps(ref,indent=2)+'\n')


if __name__=='__main__':main()
