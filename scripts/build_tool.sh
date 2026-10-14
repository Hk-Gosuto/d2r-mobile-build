#!/usr/bin/env bash
# Build only open-source tools; never read game inputs.
set -euo pipefail
cd "$(dirname "$0")/.."
KIND="$1"
DEST="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve())' "$2")"
BUILD=$(mktemp -d)
trap 'rm -rf "$BUILD"' EXIT
mkdir -p "$DEST" "$DEST/licenses"
case "$KIND" in
  spirv)
    COMMIT=$(python3 -c 'import json; print(json.load(open("build-config.json"))["spirv_commit"])')
    git clone --quiet https://github.com/KhronosGroup/SPIRV-Cross.git "$BUILD/source"
    git -C "$BUILD/source" checkout --quiet "$COMMIT"
    cmake -S "$BUILD/source" -B "$BUILD/build" -G Ninja \
      -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=clang++ -DSPIRV_CROSS_ENABLE_TESTS=OFF
    cmake --build "$BUILD/build" --target spirv-cross -j 2
    mkdir -p "$DEST/bin"
    cp "$BUILD/build/spirv-cross" "$DEST/bin/"
    cp "$BUILD/source/LICENSE" "$DEST/licenses/SPIRV-Cross.txt"
    if [[ -f "$BUILD/source/NOTICE" ]]; then cp "$BUILD/source/NOTICE" "$DEST/licenses/SPIRV-Cross-NOTICE.txt"; fi
    ;;
  png)
    curl -fL --retry 3 https://github.com/zlib-ng/zlib-ng/archive/6d9f3dc072369dc719a5fbe71d4e086a96a680bd.tar.gz -o "$BUILD/source.tar.gz"
    printf '%s  %s\n' 8f24a48f6a9325044941908cdbd6eb4852fce279ad3e4969a82d620fcf184e3a "$BUILD/source.tar.gz" | sha256sum -c -
    tar -xzf "$BUILD/source.tar.gz" -C "$BUILD"
    SRC="$BUILD/zlib-ng-6d9f3dc072369dc719a5fbe71d4e086a96a680bd"
    cmake -S "$SRC" -B "$BUILD/build" -DZLIB_COMPAT=ON -DBUILD_SHARED_LIBS=ON \
      -DZLIB_ENABLE_TESTS=OFF -DWITH_GTEST=OFF -DCMAKE_BUILD_TYPE=Release
    cmake --build "$BUILD/build" -j 2
    mkdir -p "$DEST/png-zlib-ng-2.3.2/lib"
    # Copy the actual library, not an absolute link into the build directory.
    cp -L "$BUILD/build/libz.so.1" "$DEST/png-zlib-ng-2.3.2/lib/libz.so.1"
    cp "$SRC/LICENSE.md" "$DEST/licenses/zlib-ng.txt"
    ;;
  xlate)
    dotnet publish upstream/dm/gfx/tools/dmsh_xlate -c Release -o "$DEST/dmsh_xlate" -v quiet
    "$DEST/dmsh_xlate/dmsh_xlate" --source-sha
    python3 scripts/prebuilt_tools.py licenses "$DEST/licenses"
    ;;
  *) echo "Unknown tool: $KIND" >&2; exit 1 ;;
esac
