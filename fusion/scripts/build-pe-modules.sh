#!/usr/bin/env bash
# Build the patched Windows DLL with Wine's Clang PE backend.
set -euo pipefail
FUSION_SOURCE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
[[ $# == 1 ]] || { echo "Usage: $0 BUILD_DIRECTORY" >&2; exit 2; }
FUSION_BUILD="$(realpath -m -- "$1")"
[[ "$FUSION_BUILD" != "$FUSION_SOURCE" && "$FUSION_BUILD" != "$FUSION_SOURCE/wine"* ]] || exit 2
python3 "$FUSION_SOURCE/fusion/scripts/prepare.py"
cd "$FUSION_SOURCE/wine"
./dlls/winevulkan/make_vulkan -x vk.xml -X video.xml
./tools/make_specfiles
./tools/make_requests
autoreconf -f
mkdir -p "$FUSION_BUILD"
cd "$FUSION_BUILD"
"$FUSION_SOURCE/wine/configure" --enable-win64 --enable-archs=x86_64 --with-mingw=clang \
    --with-xdamage --without-wayland --without-gstreamer --disable-tests
make -j"${FUSION_BUILD_JOBS:-$(nproc)}" dlls/bcp47langs/x86_64-windows/bcp47langs.dll
