#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
TASK_ROOT="$PWD"
python scripts/prebuilt_tools.py ensure spirv
python scripts/prebuilt_tools.py ensure xlate
export PATH="$TASK_ROOT/.tools/bin:$PATH"
rm -rf "$DM_ROOT/build/gfx/dmsh_xlate"
mkdir -p "$DM_ROOT/build/gfx"
cp -R .tools/dmsh_xlate "$DM_ROOT/build/gfx/dmsh_xlate"
"$DM_ROOT/build/gfx/dmsh_xlate/dmsh_xlate" --source-sha
python upstream/dm/gfx/tools/nometal_run.py upstream/dm/gfx/tools/dmsh_chain.py --update-lock
python upstream/dm/gfx/tools/nometal_run.py upstream/dm/gfx/tools/dmsh_chain.py --check-tools
