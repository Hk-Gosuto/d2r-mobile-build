#!/usr/bin/env python3
"""Package both official shells with the same generated game and legacy pack."""
import json
import os
from pathlib import Path
import subprocess
import sys

import ci

VARIANTS = (
    ('D2RMobile-unsigned.ipa', 'D2RMobile-shell.ipa', '26.0'),
    ('D2RMobile-ios18-unsigned.ipa', 'D2RMobile-shell-ios18.ipa', '18.0'),
)


def main():
    output = ci.ROOT / 'outputs'
    output.mkdir(exist_ok=True)
    pack = Path(os.environ['D2RM_ASTC_PACK'])
    reports = []
    for name, shell, minimum in VARIANTS:
        shell_path = ci.TOOLS / shell
        if ci.sha256(shell_path) != ci.CONFIG['shell_sha256' if minimum == '26.0' else 'ios18_shell_sha256']:
            raise ValueError('Official shell SHA256 mismatch: ' + shell)
        subprocess.run([sys.executable, str(ci.ROOT / 'upstream/dm/tools/d2rm_pack.py'),
                        str(shell_path), str(ci.GAME), str(output / name)], check=True)
        reports.append(ci.verify_ipa(output / name, shell_path, minimum, pack))
    report = dict(reports[0], packages=reports,
                  legacy_pack=json.loads((pack / 'pack.json').read_text()))
    (output / 'build-report.json').write_text(json.dumps(report, indent=2) + '\n')
    (output / 'SHA256SUMS.txt').write_text(''.join(
        f"{r['ipa_sha256']}  {r['ipa_name']}\n" for r in reports))


if __name__ == '__main__':
    main()
