#!/usr/bin/env bash
# Host-local x86_64 experiment only. This is not a portable Proton release.
set -euo pipefail
FUSION_SOURCE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ $# != 1 ]]; then
    echo "Usage: $0 /absolute/path/to/native-build-directory" >&2
    exit 2
fi
FUSION_BUILD="$(realpath -m -- "$1")"
if [[ "$FUSION_BUILD" == "$FUSION_SOURCE" || ( "$FUSION_BUILD" == "$FUSION_SOURCE/"* && "$FUSION_BUILD" != "$FUSION_SOURCE/.build/"* ) ]]; then
    echo 'Use a separate build directory outside the source checkout.' >&2
    exit 2
fi
python3 "$FUSION_SOURCE/fusion/scripts/prepare.py"
cd -- "$FUSION_SOURCE/wine"
./dlls/winevulkan/make_vulkan -x vk.xml -X video.xml
./tools/make_specfiles
./tools/make_requests
autoreconf -f
mkdir -p -- "$FUSION_BUILD"
cd -- "$FUSION_BUILD"
"$FUSION_SOURCE/wine/configure" --enable-win64 --with-xdamage --without-mingw --without-wayland --without-gstreamer --disable-tests
make -j"${FUSION_BUILD_JOBS:-$(nproc)}" dlls/win32u/win32u.so dlls/winex11.drv/winex11.so
echo "Host-local modules: $FUSION_BUILD/dlls/{win32u/win32u.so,winex11.drv/winex11.so}"
