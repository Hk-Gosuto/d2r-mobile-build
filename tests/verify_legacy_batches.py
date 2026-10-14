"""Exercise the frozen converter and real ASTC encoder with generated BC3 fixtures."""
import base64
import hashlib
import json
from pathlib import Path
import random
import struct
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import legacy_batches as batches


def verify():
    encoder=batches.encoder()
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);romfs=root/'RomFS';(romfs/'data').mkdir(parents=True)
        rng=random.Random(42);data={};lines=[];entries=[]
        for i in range(9):
            name=f'data/hd/generated/fixture_{i}.texture'
            block=rng.randbytes(16);head=bytearray(48);head[4]=61+i%2
            struct.pack_into('<II',head,8,8,8);struct.pack_into('<I',head,40,8)
            data[name]=bytes(head)+block*4
            row=['']*11;row[9]='data:'+name;lines.append('|'.join(row))
            thumbnail=struct.pack('<IIII',1,4,16,4)+block
            entries.append({'filename':name,'format':head[4],'thumbnailBase64':base64.b64encode(thumbnail).decode(),'label':'生成测试'})
        data[batches.DESCRIPTOR]=json.dumps(entries).encode()
        row=['']*11;row[9]='data:'+batches.DESCRIPTOR;lines.append('|'.join(row))
        (romfs/'data/build_manifest.psv').write_text('\n'.join(lines)+'\n')

        def converter():
            module=batches.load_converter();module.BATCH_BLOCKS=5;module.ROW_BLOCKS=4
            module.touch_layout._read_entry=lambda romfs,row:data[row[9].split(':',1)[-1].lower()]
            return module

        module=converter();baseline=root/'baseline'
        previous=sys.argv
        try:
            sys.argv=[str(module.__file__),str(romfs),str(baseline),'--astcenc',str(encoder),'--preset','thorough']
            module.main()
        finally:sys.argv=previous
        workers=[]
        for i in range(2):
            dest=root/f'worker-{i}';batches.convert(converter(),romfs,dest,encoder,i,2,'fixture-recipe');workers.append(dest)
        merged=root/'merged';batches.merge(workers,merged,'fixture-recipe')
        order=[line.split('\t')[0] for line in (baseline/'repl.tsv').read_text().splitlines()]
        assert order==[line.split('\t')[0] for line in (merged/'repl.tsv').read_text().splitlines()]
        for name in order:
            expected=(baseline/'files'/name).read_bytes();actual=(merged/'files'/name).read_bytes()
            assert expected==actual,name
        print('Real ASTC encoder: serial and two-worker outputs match byte-for-byte;',len(order),'files')
        target=next((workers[0]/'files').rglob('*.texture'));target.write_bytes(b'corrupt')
        try:batches.merge(workers,root/'corrupt','fixture-recipe')
        except ValueError as e:assert 'Corrupt' in str(e)
        else:raise AssertionError('Corrupt worker output was accepted')
        print('Corrupt conversion outputs rejected')


if __name__=='__main__':verify()
