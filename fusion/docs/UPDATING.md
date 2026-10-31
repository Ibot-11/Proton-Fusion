# Updating the upstream base

The initial base is official `experimental_11.0`, commit
`871b0bf1402dd9632a16495a2def7036161e771c`, selected on 2026-10-31.
The latest stable release at that date was `proton-11.0-2`; Experimental was
chosen to follow the newest official code already used by the Fusion installation.
The `bleeding-edge` development branch is not the selected channel.

```bash
python3 fusion/scripts/check-upstream.py
```

This reports a newer upstream commit without changing source, prefixes, or
installed runtimes. Updates are reviewed explicitly:

1. Keep the current working build and results. Create a fresh Git worktree and an
   `update/...` branch from `main`; use clean submodules in that worktree.
2. Fetch and merge the selected upstream commit. Preserve the absolute official
   Wine submodule URL and the fork's `--with-xdamage` configure requirement.
3. Update `fusion/upstream.json`: Proton commit, selected date, Wine and DXVK
   commits must match `git ls-tree <upstream-commit> wine dxvk`.
4. Initialize the new submodules. Run `prepare.py --check`. If a patch no longer
   applies, examine the upstream change and rework or remove the patch. Do not
   force an old binary module into the new runtime.
5. Build in the selected Proton SDK. Run the GPU regression suite against both
   the new unpatched base and the patched build, with the external Vulkan sync
   layer disabled. If upstream alone passes, inspect whether the downstream
   patch is still necessary.
6. Check Fusion itself: snapping, sketch preview, dimensions/HUDs, file dialogs,
   multiple documents, minimized/hidden windows, DPI changes, and SpaceMouse.
   Include AMD/Mesa, Intel/Mesa and NVIDIA validation before claiming broad
   driver support.
7. Record module and patch hashes and publish a new build only after review.
   Keep rollback available. Never change the runtime beneath a running Fusion
   process or automatically migrate a user's working prefix.

The desired long-term outcome is an accepted Wine fix and a shrinking downstream
patch series. An upstream merge should be checked for equivalent behavior before
the downstream copy is removed.
