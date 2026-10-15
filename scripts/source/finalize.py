"""Join the two verified native build reports and publish in the caller repository."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ci
import publish_release
from repository_access import require_private


def main():
    require_private()
    out = ci.ROOT / 'outputs'
    reports = [json.loads((out / name).read_text())
               for name in ('source-report.json', 'source-ios18-report.json')]
    for key in ('source_commit', 'patch_sha256', 'product', 'payload_sha256', 'legacy_pack',
                'app_version', 'build_number', 'release_tag', 'shader_chain', 'metal_toolchain', 'metal_precompiled'):
        if reports[0].get(key) != reports[1].get(key):
            raise ValueError('The two IPA variants use different source inputs: ' + key)
    report = dict(reports[0], packages=reports)
    (out / 'build-report.json').write_text(json.dumps(report, indent=2) + '\n')
    (out / 'SHA256SUMS.txt').write_text(''.join(
        f"{item['ipa_sha256']}  {item['ipa_name']}\n" for item in reports))
    publish_release.main('ipa')


if __name__ == '__main__':
    main()
