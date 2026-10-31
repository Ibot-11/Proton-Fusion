#!/usr/bin/env python3
"""Run serial, isolated display regressions against stock and patched Proton."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--stock", type=Path, required=True)
parser.add_argument("--patched", type=Path, required=True)
parser.add_argument("--steam", type=Path, required=True)
parser.add_argument("--exe", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
tests = Path(__file__).resolve().parent
args.output = args.output.resolve()
args.output.mkdir(parents=True, exist_ok=True)
cases = [
    ("stock-discard", False, ["--bursts", "30"], {}),
    ("stock-flip", False, ["--bursts", "30", "--effect", "1"], {}),
    ("patched-discard", True, ["--bursts", "100"], {}),
    ("patched-flip", True, ["--bursts", "100", "--effect", "1"], {}),
    ("patched-small", True, ["--bursts", "40", "--size", "384"], {}),
    ("patched-resize-minimize", True, ["--bursts", "60", "--resize", "--minimize"], {}),
    ("patched-gpu-load", True, ["--bursts", "40", "--gpu", "2", "--cpu", "2"], {}),
    ("patched-fifo", True, ["--bursts", "30", "--config", str(tests / "dxvk-fifo.conf")], {}),
    ("patched-disabled", True, ["--bursts", "20"], {"WINE_FUSION_CHILD_DAMAGE": "0"}),
    ("stock-throughput", False, ["--bursts", "1", "--stress", "1000"], {}),
    ("patched-throughput", True, ["--bursts", "1", "--stress", "1000"], {}),
]
results = []
for name, patched, extra, overrides in cases:
    env = os.environ.copy()
    env.pop("WINE_FUSION_CHILD_DAMAGE", None)
    env["WINEDEBUG"] = "+fusion" if patched else "-all"
    env.update(overrides)
    cmd = [sys.executable, str(tests / "run-child-present.py"),
           "--proton", str((args.patched if patched else args.stock).resolve()),
           "--steam", str(args.steam.resolve()), "--exe", str(args.exe.resolve()),
           "--prefix", str(args.output / ("prefix-patched" if patched else "prefix-stock")),
           "--config", str(tests / "dxvk.conf"), "--output", str(args.output / name),
           *extra]
    subprocess.run(cmd, env=env, check=True)
    result = json.loads((args.output / name / "result.json").read_text())
    result["case"] = name
    if patched and "disabled" not in name and (result["stale_30ms"] or result["stale_200ms"]):
        raise SystemExit(f"Visible frame regression in {name}")
    if "throughput" not in name and (not patched or "disabled" in name) and not result["stale_200ms"]:
        raise SystemExit(f"Baseline no longer reproduces in {name}; investigate before drawing a conclusion")
    results.append(result)
    (args.output / "suite.json").write_text(json.dumps(results, indent=2) + "\n")
print(f"Completed {len(results)} cases")
