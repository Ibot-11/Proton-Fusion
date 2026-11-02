# Building Proton-Fusion

This is an experimental Fusion-focused downstream of official Proton
Experimental, not GE-Proton. Exact component commits are in `fusion/upstream.json`.
Upstream's original documentation is in `README.upstream.md`.

## Source preparation

```bash
git clone --branch main https://github.com/Ibot-11/Proton-Fusion.git
cd Proton-Fusion
git submodule update --init --depth=1 wine dxvk
python3 fusion/scripts/prepare.py --check
python3 fusion/scripts/prepare.py
```

The submodules stay at upstream commits. The Wine changes are committed as a
reviewable patch series in `fusion/patches/wine/`. `prepare.py` is idempotent,
checks the pinned gitlinks and checked-out commits, and refuses to replace
unrelated tracked Wine changes. Applying the patches makes the Wine submodule
appear modified; that is expected. Generated Wine headers may also appear modified
after a native build; they are not part of the Fusion patch series.

## Complete SDK build

Use a working Docker or rootless Podman setup, the dependencies listed in
`README.upstream.md`, and a builder with ample RAM and at least 100 GB of free
build space. The upstream makefiles select a versioned Proton SDK image.

```bash
bash fusion/scripts/build-sdk.sh /absolute/path/to/proton-fusion-build
```

The result is `proton-fusion-build/redist/`. The fork requires XDamage development
files at configure time, rather than silently producing a runtime without the fix.
The complete SDK workflow is manual and expects a self-hosted runner labelled
`proton-builder`; it does not automatically publish releases or change an installed
Fusion runtime. Initial development was validated with native modules, not a full
SDK redistributable.

## Native module experiment

The native step builds `win32u.so` and `winex11.so` for the local x86_64 host. A
second Clang PE step builds the patched `bcp47langs.dll`. These steps require
GCC, Make, Autoconf/Autoheader, Bison, Flex, Perl, Python, X11/XComposite/XDamage
development files, and the optional development libraries detected by Wine.
It is useful for investigating the exact installed Proton source version;
it is not a portable or 32-bit release build.

```bash
bash fusion/scripts/build-native-modules.sh /absolute/path/to/fusion-native
bash fusion/scripts/build-pe-modules.sh /absolute/path/to/fusion-pe
```

Use `fusion/scripts/install-local.py` to assemble a versioned runtime from the
matching official base, both module builds and the Fusion profile. See
`INTEGRATION.de.md`. It leaves Steam's managed runtime intact and verifies the
base version before creating `fusion-runtime.json`.

## Test program

Build the Win64 D3D11 reproducer with MinGW GCC, or Clang/LLD and Wine development
headers/import libraries as provided on Arch/CachyOS:

```bash
bash fusion/tests/build-child-present.sh /absolute/path/to/child-present.exe
python3 fusion/tests/run-suite.py \
  --stock '/path/to/Proton - Experimental' \
  --patched /path/to/Proton-Fusion \
  --steam /path/to/Steam \
  --exe /absolute/path/to/child-present.exe \
  --output /absolute/path/to/test-results
```

Run on an X11/Xwayland desktop with a Vulkan-capable GPU. Tests are serial and
use dedicated marked prefixes, never the Fusion prefix. They draw a palette in
a Win32 `WS_CHILD` D3D11 swapchain, present short bursts, stop rendering, and read
the visible parent-window pixel after 30 and 200 ms. The stock controls must
reproduce a stale frame; each patched correctness case must have no mismatches.
Do not run a second `SnapTest` instance at the same time.

`--damage-copy` in the individual test runner is a deliberately restricted
causality probe for a known 580x580 test window. It is not used by the Wine fix
or by the regression suite. No Python helper or Vulkan interception layer is
required by the patched runtime.

## X11 resource lifetime regressions

The fault suite issues real X server requests with invalid resource IDs from
private library interposers. Use a previous Proton-Fusion build that still
exhibits the errors as the baseline. The suite requires the native X11/XDamage/
XRandR/XCB-RandR development libraries, GCC, `ldconfig`, and the D3D11 reproducer
above. The unchecked XCB case requires a Vulkan driver using that path, such as
the tested Mesa RADV 26.2.5; the test fails if injection is not exercised.

```sh
python3 fusion/tests/build-x11-fault-shims.py .build/x11-fault-shims
python3 fusion/tests/run-x11-faults.py \
  --baseline /path/to/previous/Proton-Fusion --runtime /path/to/fixed/Proton-Fusion \
  --steam /path/to/Steam --shims .build/x11-fault-shims --output .local/x11-fault-results
```

It compares failed Damage creation, repeated Damage destruction, a stale Damage
notification, Wine's invalid RandR CRTC query, and Mesa's unchecked XCB query.
An unrelated `BadAtom` and a different RandR request (`RRGetCrtcGammaSize`) with
the same `BadRRCrtc` error must still terminate the test process, ensuring the fix
matches both the error and the precise request.
All cases are serial, use marked test prefixes and stop only those test Wine
servers. The library shims are never packaged or installed in a runtime. No
physical monitor configuration is changed by these tests.

The Damage subscription orders drawable creation on the GDI connection before
creation on the owner's connection, then validates the asynchronous request.
Retired Damage cleanup and subtraction errors are scoped to those two protocol
requests. A stale live subscription is marked under its display lock and rebuilt
on the next ordinary surface update. There is no extra server round trip per
frame. RandR CRTC queries use Wine's expected-error mechanism; the query already
waits for its reply, and existing callers handle a missing CRTC. Mesa can also
submit an unchecked XCB `RRGetCrtcInfo` on an Xlib-owned connection. Its missing
reply already invalidates the cached monitor data, but Xlib subsequently
delivers the error outside Wine's scoped trap. Wine's normal error handler now
recognizes exactly that RandR opcode, request and error. Initialization publishes
the extension codes atomically; no X query or blocking work runs in the handler.

## Diagnostics and fallback

* `WINEDEBUG=+fusion` reports subscriptions and damage-triggered repaints.
* `WINE_FUSION_CHILD_DAMAGE=0` restores the original presentation behavior.
* XDamage is enabled by default for actual offscreen Vulkan client surfaces.
  Surface dimensions and present mode are not used to select them.
* The updated Fusion launcher pins the verified runtime, removes the legacy
  Fusion Vulkan layer, and no longer runs `panel-fix.exe`. It retains browser,
  SpaceMouse and the separately identified phantom-dialog integration.
* `WINE_FUSION_MANAGED_PANELS=0` disables the additional Qt-panel policy.
* `WINE_FUSION_PANEL_FIRST_PAINT=0` disables the initial-paint guard. Large owned
  Qt tool windows with buffered GDI surfaces start with X11 opacity zero. Expose
  of the initialized backing store does not reveal them: GDI drawing must have
  started. Preserving pixels when replacing a surface also counts as GDI drawing.
  After the first such flush, a one-time X server round trip
  orders the pixels before an owner-thread notification restores the current
  opacity. This does not inspect pixel colors or add a timer. Layered windows
  are excluded initially; subsequent opacity changes are preserved. Switching
  to direct/GPU drawing releases the guard. This mechanism requires a compositor
  honoring `_NET_WM_WINDOW_OPACITY`, as verified locally with KWin/Xwayland.

The initial-paint regression probe, including a disabled control, geometry changes,
subsequent alpha changes, and deliberately black application content, runs with:

```sh
bash fusion/tests/build-probes.sh .build/tests
python3 fusion/tests/run-first-paint.py --runtime /path/to/Proton-Fusion \
  --steam /path/to/Steam --output .local/first-paint-probe
```

The patch initially retains Wine's original immediate copy and adds a corrective
copy after source damage. This preserves exposure/geometry behavior. Coalescing
or eliminating redundant copies is a follow-up optimization, not an assumed
property of this prototype.
