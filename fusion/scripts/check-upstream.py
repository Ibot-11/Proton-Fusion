#!/usr/bin/env python3
"""Report the next upstream candidate. Never merge or switch an installation."""
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[2]
manifest = json.loads((root / "fusion/upstream.json").read_text())
upstream = manifest["proton"]
ref = "refs/heads/" + upstream["branch"]
result = subprocess.run(["git", "ls-remote", upstream["repository"], ref],
                        check=True, capture_output=True, text=True)
lines = result.stdout.splitlines()
if len(lines) != 1 or len(lines[0].split()) != 2:
    raise SystemExit("Upstream branch could not be resolved")
latest = lines[0].split()[0]
print(json.dumps(dict(branch=upstream["branch"], pinned=upstream["commit"],
                      latest=latest, update_available=latest != upstream["commit"]), indent=2))
