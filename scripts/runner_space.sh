#!/usr/bin/env bash
# Only for disposable GitHub-hosted Ubuntu runners.
set -euo pipefail
sudo rm -rf /usr/local/lib/android /usr/share/swift /usr/local/.ghcup /opt/ghc \
  /opt/hostedtoolcache/CodeQL /usr/lib/jvm /usr/share/dotnet
python3 - <<'PY'
import shutil
free=shutil.disk_usage('.').free/1024**3
print(f'Free disk space: {free:.1f} GiB')
if free < 32: raise SystemExit('Game extraction requires at least 32 GiB free')
PY
