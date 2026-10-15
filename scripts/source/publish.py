"""Publish only the two verified IPAs and their build checksums/report."""
import json
import os

import ci
import publish_release as releases
from repository_access import require_private
from release_notes import bilingual, INSTALLER_LINKS, CHINESE_INSTALLER_LINKS


def notes():
    standard, compatibility = ci.ipa_names()
    base = 'https://github.com/jiayx/d2r-mobile-build/blob/feat/build-template/'
    return bilingual(
        f'Source: `{ci.CONFIG["upstream_commit"]}`.\n\n'
        f'- iOS 26 and later: `{standard}`.\n'
        f'- iOS 18–25: `{compatibility}`.\n\n'
        f'Sign and install with {INSTALLER_LINKS}.\n\n'
        'Download matching Data and, for A14–A16 devices, the Legacy Device Pack '
        'from your resource provider’s storage. Previously imported matching resources remain reusable. '
        'Metal shaders are included precompiled. This build has not been tested on a physical device.\n\n'
        f'For installation and resource import, see the [README]({base}README.md).',
        f'源码：`{ci.CONFIG["upstream_commit"]}`。\n\n'
        f'- iOS 26 及以上：`{standard}`。\n'
        f'- iOS 18–25：`{compatibility}`。\n\n'
        f'使用 {CHINESE_INSTALLER_LINKS} 签名安装。\n\n'
        '从资源提供者的网盘下载配套 Data；A14–A16 设备另需 Legacy Device Pack。'
        '已导入的相同资源可以继续复用。包内已包含预编译 Metal 着色器。此构建未进行真机测试。\n\n'
        f'安装和资源导入方式见[中文 README]({base}README.zh-CN.md)。')


def publish():
    repo = require_private()
    out = ci.ROOT / 'outputs'
    report = json.loads((out / 'build-report.json').read_text())
    releases.validate_report(report)
    paths = releases.validate_packages(report)
    releases.STAGE.mkdir(exist_ok=True)
    body = releases.STAGE / 'RELEASE.md'
    body.write_text(notes())
    tag, title = ci.release_tag(), releases.release_title()
    releases.ensure_release(repo, tag, title, body)
    releases.upload_verified(repo, tag, [*paths, out / 'SHA256SUMS.txt', out / 'build-report.json'])
    release = releases.publish_complete(repo, tag, body, title)
    print('Published verified IPAs:', release['html_url'], flush=True)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
            summary.write(f"\n[Download IPAs]({release['html_url']})\n")
    return release
