#!/usr/bin/env bash
# Pin the PNG compressor used by the upstream frozen byte hashes.
set -euo pipefail
cd "$(dirname "$0")/.."
PNG_PREFIX="$PWD/.tools/png-zlib-ng-2.3.2"
python scripts/prebuilt_tools.py ensure png
test -f "$PNG_PREFIX/lib/libz.so.1"
