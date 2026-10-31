#!/usr/bin/env bash
set -euo pipefail
FUSION_TESTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ $# == 1 ]] || exit 2
mkdir -p "$1"
for probe in panel bcp47; do
  clang --target=x86_64-w64-windows-gnu -fuse-ld=lld -O2 -fno-builtin \
    -I/usr/include/wine/windows -I/usr/include/wine/msvcrt -nostdlib \
    -Wl,--entry=WinMainCRTStartup -Wl,--subsystem=windows \
    "$FUSION_TESTS/$probe-probe.c" -L/usr/lib/wine/x86_64-windows \
    -lkernel32 -luser32 -lcombase -o "$1/$probe-probe.exe"
done
