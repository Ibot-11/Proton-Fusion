#!/usr/bin/env bash
set -euo pipefail
FUSION_TESTS="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ $# != 1 ]]; then
    echo "Usage: $0 /absolute/path/to/child-present.exe" >&2
    exit 2
fi
if command -v x86_64-w64-mingw32-gcc >/dev/null; then
    x86_64-w64-mingw32-gcc -O2 -nostdlib -Wl,--entry=WinMainCRTStartup -Wl,--subsystem=windows \
        "$FUSION_TESTS/child-present.c" -ld3d11 -ldxgi -lkernel32 -luser32 -o "$1"
else
    # Wine development headers/import libraries, as packaged on CachyOS/Arch.
    clang --target=x86_64-w64-windows-gnu -fuse-ld=lld -O2 \
        -I/usr/include/wine/windows -I/usr/include/wine/msvcrt -nostdlib \
        -Wl,--entry=WinMainCRTStartup -Wl,--subsystem=windows \
        "$FUSION_TESTS/child-present.c" -L/usr/lib/wine/x86_64-windows \
        -ld3d11 -ldxgi -lkernel32 -luser32 -o "$1"
fi
