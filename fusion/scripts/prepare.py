#!/usr/bin/env python3
"""Validate pinned submodules and apply/check the Fusion Wine patch series."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def git(*args, cwd=ROOT, check=True):
    return subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=check)


def prepare(check_only=False):
    manifest = json.loads((ROOT / "fusion/upstream.json").read_text())
    for module in ("wine", "dxvk"):
        expected = manifest[module]["commit"]
        recorded = git("rev-parse", f"HEAD:{module}").stdout.strip()
        if recorded != expected:
            raise RuntimeError(f"{module} gitlink differs from fusion/upstream.json; review the base update first")
        actual = git("rev-parse", "HEAD", cwd=ROOT / module).stdout.strip()
        if actual != expected:
            raise RuntimeError(f"{module} checkout is {actual}, expected {expected}; initialize the pinned submodules")
    patches_dir = ROOT / "fusion/patches/wine"
    names = [line.strip() for line in (patches_dir / "series").read_text().splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    if not names or any(Path(name).name != name for name in names):
        raise RuntimeError("Invalid or empty Wine patch series")
    patches = [str(patches_dir / name) for name in names]
    if git("apply", "--reverse", "--check", *reversed(patches), cwd=ROOT / "wine", check=False).returncode == 0:
        print("Fusion Wine patches are already applied")
        return
    if git("diff", "--quiet", cwd=ROOT / "wine", check=False).returncode:
        raise RuntimeError("Wine has local changes that are not the complete Fusion patch series; leaving them untouched")
    git("apply", "--check", *patches, cwd=ROOT / "wine")
    if not check_only:
        git("apply", *patches, cwd=ROOT / "wine")
    print("Fusion Wine patch series " + ("applies cleanly" if check_only else "applied"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate without applying unapplied patches")
    args = parser.parse_args()
    try:
        prepare(args.check)
    except (RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")
