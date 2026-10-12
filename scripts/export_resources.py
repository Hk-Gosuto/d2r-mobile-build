#!/usr/bin/env python3
"""Export only the 18 archives used by the matching iOS app."""
import hashlib
import json
import os
from pathlib import Path
import zipfile

import ci


def export_resources(game=ci.GAME, output=None):
    game = Path(game)
    ci.validate_game(game)
    output = Path(output or ci.ROOT / 'outputs/D2R-Mobile-Resources.zip')
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix('.zip.part')
    folder = 'D2R Mobile Resources'
    files = []
    try:
        with zipfile.ZipFile(partial, 'w', compression=zipfile.ZIP_DEFLATED,
                             compresslevel=6, allowZip64=True) as archive:
            for name, size in ci.resource_sizes().items():
                source = game / 'RomFS/data' / name
                if source.stat().st_size != size:
                    raise ValueError('Resource missing or incomplete: ' + name)
                digest = ci.sha256(source)
                files.append({'name': name, 'bytes': size, 'sha256': digest})
                archive.write(source, f'{folder}/data/{name}')
                print('Packed and hashed:', name, size, flush=True)
            sums = ''.join(f"{f['sha256']}  data/{f['name']}\n" for f in files)
            archive.writestr(f'{folder}/SHA256SUMS.txt', sums)
            archive.writestr(f'{folder}/README.txt',
                'D2R Mobile 游戏资源（游戏版本 3.3.94012 / Switch 更新 1.0.34.0）\n\n'
                '1. 在电脑上解压本 ZIP，得到 D2R Mobile Resources 文件夹。\n'
                '2. 用数据线连接 iPhone，打开 Finder → iPhone → 文件。\n'
                '3. 将整个 D2R Mobile Resources 文件夹拖入 D2R Mobile 应用。\n'
                '   也可放入手机 文件 → 我的 iPhone → D2R Mobile。\n'
                '4. 打开应用，点击重试。首次启动等待着色器编译完成。\n\n'
                'data 文件夹包含完整的 18 个 .data 文件，合计约 5.56GB。\n'
                '无需向手机复制游戏包、ExeFS 或任何密钥。\n'
                '正常覆盖安装时请保持应用标识一致；卸载应用会删除资源和存档。\n')
        # Read every compressed member back and compare with the source digest.
        with zipfile.ZipFile(partial) as archive:
            expected = {f"{folder}/data/{f['name']}" for f in files}
            expected.update({f'{folder}/SHA256SUMS.txt', f'{folder}/README.txt'})
            if set(archive.namelist()) != expected:
                raise ValueError('Unexpected resource ZIP contents')
            for item in files:
                name = f"{folder}/data/{item['name']}"
                digest = hashlib.sha256()
                with archive.open(name) as stream:
                    for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
                        digest.update(chunk)
                if archive.getinfo(name).file_size != item['bytes'] or digest.hexdigest() != item['sha256']:
                    raise ValueError('Resource ZIP verification failed: ' + name)
                print('Verified ZIP entry:', item['name'], flush=True)
            for name in (f'{folder}/SHA256SUMS.txt', f'{folder}/README.txt'):
                archive.read(name)  # Also check metadata CRCs.
        partial.replace(output)
    finally:
        partial.unlink(missing_ok=True)
    report = {'game_version': ci.CONFIG['game_version'],
              'input_revision': os.environ.get('INPUT_REVISION'),
              'switch_version': ci.CONFIG['switch_version'],
              'upstream_commit': ci.CONFIG['upstream_commit'],
              'archive_count': len(files), 'resource_bytes': sum(f['bytes'] for f in files),
              'zip_bytes': output.stat().st_size, 'zip_sha256': ci.sha256(output), 'files': files}
    output.with_name('resources-report.json').write_text(json.dumps(report, indent=2) + '\n')
    output.with_name('Resources-SHA256SUMS.txt').write_text(f"{report['zip_sha256']}  {output.name}\n")
    print('Resource export verified:', report['archive_count'], 'archives;', report['zip_bytes'], 'ZIP bytes', flush=True)
    return report


if __name__ == '__main__':
    export_resources()
