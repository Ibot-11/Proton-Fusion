#!/usr/bin/env bash
# Complete redistributable build using Valve's pinned Proton SDK.
set -euo pipefail
FUSION_SOURCE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ $# != 1 ]]; then
    echo "Usage: $0 /absolute/path/to/empty-build-directory" >&2
    exit 2
fi
FUSION_BUILD="$(realpath -m -- "$1")"
if [[ "$FUSION_BUILD" == "$FUSION_SOURCE" || "$FUSION_BUILD" == "$FUSION_SOURCE/"* ]]; then
    echo 'Use a separate build directory outside the source checkout.' >&2
    exit 2
fi
if ! command -v podman >/dev/null && ! command -v docker >/dev/null; then
    echo 'The full Proton SDK build requires a working Podman or Docker installation.' >&2
    exit 1
fi
git -C "$FUSION_SOURCE" submodule sync --recursive
git -C "$FUSION_SOURCE" submodule update --init --recursive
python3 "$FUSION_SOURCE/fusion/scripts/prepare.py"
mkdir -p -- "$FUSION_BUILD"
cd -- "$FUSION_BUILD"
"$FUSION_SOURCE/configure.sh" --build-name=Proton-Fusion
make -j"${FUSION_BUILD_JOBS:-$(nproc)}" redist
echo "Proton-Fusion redistributable: $FUSION_BUILD/redist"
