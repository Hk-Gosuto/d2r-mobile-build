"""Exercise Apple's actual iOS compiler with generated shaders, without game inputs."""
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
import zipfile

from test_metal import fixture
from source import metal


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    entries, report, _, dm = fixture(root)
    tools = dm / 'ios/tools'; tools.mkdir(parents=True)
    (tools / 'ios_metal.py').write_text('''import subprocess
METAL=['xcrun','-sdk','iphoneos','metal','-c','-mios-version-min=18.0']
METALLIB=['xcrun','-sdk','iphoneos','metallib']
RECORD=' '.join(METAL)+'; '+' '.join(METALLIB)
def compile(msl,air,lib):
 subprocess.run([*METAL,msl,'-o',air],check=True)
 subprocess.run([*METALLIB,air,'-o',lib],check=True)
''')
    for name in entries:
        if name.endswith('.metallib'):
            constant = '2.0f' if name.endswith('two_b.metallib') else '1.0f'
            entries[name] = ('#include <metal_stdlib>\nusing namespace metal;\n'
                             'kernel void shader_entry(device float *values [[buffer(0)]], '
                             'uint i [[thread_position_in_grid]]) { values[i] = '+constant+'; }\n').encode()
    payload = root / 'outputs/source-payload.zip'
    with zipfile.ZipFile(payload, 'w') as z:
        for name, data in entries.items(): z.writestr(name, data)
    translated = payload.read_bytes()
    report['payload_sha256'] = metal.ci.sha256(payload)
    for iteration in range(2):
        payload.write_bytes(translated)
        (root / 'outputs/source-input-report.json').write_text(json.dumps(report))
        with patch.dict(os.environ, GITHUB_OUTPUT=str(root / 'step-output')):
            metal.configure(root)
        metal.compile_payload(root, root / 'cache')
        actual = json.loads((root / 'outputs/source-input-report.json').read_text())
        assert actual['metal_compiled_count'] == (2 if iteration == 0 else 0), actual
        assert actual['metal_cache_hits'] == (0 if iteration == 0 else 2), actual
        metal.verify_payload(payload, actual)
        print('Apple iOS 18 Metal fixture verified:', iteration, actual['metal_seconds'], flush=True)
