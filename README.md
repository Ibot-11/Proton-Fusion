# Proton-Fusion

Autodesk Fusion runtime based on **official Proton Experimental**. The maintained
branch is `main`. The fork fixes stale last-frame rendering of offscreen Win32
child windows, Qt panel handling and preferred UI language support through Wine.

**[Deutsche Untersuchung und Ergebnisse](fusion/docs/UNTERSUCHUNG.de.md)** ·
[Fusion launcher integration](fusion/docs/INTEGRATION.de.md) ·
[Build and test](fusion/docs/BUILDING.md) ·
[Upstream updates](fusion/docs/UPDATING.md) ·
[Original Proton README](README.upstream.md)

## Current approach

The runtime also manages Fusion's persistent Qt tool panels directly in Wine,
implements `bcp47langs.GetUserLanguages`, and owns the Fusion DLL/graphics defaults.
The Fusion launcher pins a manifest-verified build instead of selecting stock
Proton or injecting the former Vulkan/panel helpers. Versioned local installation
and complete SDK packaging share the same runtime manifest contract.

New large Qt tool panels with buffered GDI content remain transparent until
their first drawing operation has been flushed. This prevents an empty black
panel flashing at Qt's temporary center position before its layout is ready.
The reveal follows the owning window's message loop; no fixed delay is used.

Wine's normal child-surface copy can run before Mesa/Xwayland has updated the
offscreen source drawable. The Fusion patch subscribes to **XDamage** on actual
offscreen Vulkan surfaces and repaints after source damage through the window
owner's event loop. It does not wait for an entire GPU queue, intercept Vulkan
presentation, depend on a DXVK-owned fence, or select windows by pixel size.

The native-event identity is checked against Wine's live surface list under its
existing lock. Subscriptions are removed on detachment, destruction, and a
transition back to onscreen rendering. Missing runtime XDamage support falls
back to upstream behavior. `WINE_FUSION_CHILD_DAMAGE=0` disables the fix;
`WINEDEBUG=+fusion` shows diagnostics.

## Evidence and scope

On RX 7900 XTX / Mesa RADV 26.2.5 / Xwayland, the initial integrated prototype
passed **370/370 burst-and-idle series** with no stale last frame at 30 or 200 ms.
Cases include discard and flip swapchains, a 384x384 viewport, resize/minimize,
GPU load, and FIFO. Stock controls reproduced the bug; disabling the patch
restored it. Results are recorded in `fusion/validation/2026-10-31.json`.

The local runtime
uses host-built x86_64 Unix modules on the matching official runtime. Native
module CI and a manual complete SDK build workflow are included. Real Fusion
interaction has been checked on the local AMD/Mesa setup, including the corrected
Extrusion panel opening. The panel, language and 40-series resize/minimize
regressions passed. Results are in `fusion/validation/2026-10-31-first-paint.json`.
Other GPU vendors, cross-process surfaces, and a complete portable/32-bit build
still require validation. See the investigation for the retained immediate
copy, event-loop dependency, and alternatives.

## Pinned upstream

| Component | Commit |
|---|---|
| Proton Experimental (`experimental_11.0`) | `871b0bf1402dd9632a16495a2def7036161e771c` |
| Wine | `7b3ceaf8644bb5d57140903e12897efac69be16a` |
| DXVK | `a78a467cadb22bee928904290cf8e7921b121851` |

The Wine submodule remains upstream-pinned; the downstream changes live in
`fusion/patches/wine/`. Apply them with `python3 fusion/scripts/prepare.py`.
Check for a new base with `python3 fusion/scripts/check-upstream.py`.
Updates do not happen automatically.

Proton and its components retain their upstream licenses. Fusion-specific
scripts/tests/docs are MIT; Wine patches are LGPL-2.1-or-later. Autodesk Fusion
is proprietary and is not included.
