#!/usr/bin/env python3
"""Measure the last visible child-window frame after a burst, through X11.

The optional damage-copy mode is a causality experiment, not a product fix:
it copies a known test surface to a known test window after XDamageNotify.
It never searches for or writes to Fusion windows.
"""
import argparse
import ctypes as C
import hashlib
import json
import os
import signal
from pathlib import Path
import subprocess
import time


class DamageEvent(C.Structure):
    _fields_ = [("type", C.c_int), ("serial", C.c_ulong),
                ("send_event", C.c_int), ("display", C.c_void_p),
                ("drawable", C.c_ulong), ("damage", C.c_ulong)]


class X11:
    def __init__(self):
        self.lib = C.CDLL("libX11.so.6")
        signatures = {
            "XOpenDisplay": ([C.c_char_p], C.c_void_p),
            "XDefaultRootWindow": ([C.c_void_p], C.c_ulong),
            "XQueryTree": ([C.c_void_p, C.c_ulong, C.POINTER(C.c_ulong), C.POINTER(C.c_ulong), C.POINTER(C.POINTER(C.c_ulong)), C.POINTER(C.c_uint)], C.c_int),
            "XGetGeometry": ([C.c_void_p, C.c_ulong, C.POINTER(C.c_ulong), C.POINTER(C.c_int), C.POINTER(C.c_int), C.POINTER(C.c_uint), C.POINTER(C.c_uint), C.POINTER(C.c_uint), C.POINTER(C.c_uint)], C.c_int),
            "XFetchName": ([C.c_void_p, C.c_ulong, C.POINTER(C.c_void_p)], C.c_int),
            "XFree": ([C.c_void_p], C.c_int),
            "XGetImage": ([C.c_void_p, C.c_ulong, C.c_int, C.c_int, C.c_uint, C.c_uint, C.c_ulong, C.c_int], C.c_void_p),
            "XGetPixel": ([C.c_void_p, C.c_int, C.c_int], C.c_ulong),
            "XDestroyImage": ([C.c_void_p], C.c_int),
            "XCreateGC": ([C.c_void_p, C.c_ulong, C.c_ulong, C.c_void_p], C.c_void_p),
            "XCopyArea": ([C.c_void_p, C.c_ulong, C.c_ulong, C.c_void_p, C.c_int, C.c_int, C.c_uint, C.c_uint, C.c_int, C.c_int], C.c_int),
            "XFlush": ([C.c_void_p], C.c_int),
            "XPending": ([C.c_void_p], C.c_int),
            "XNextEvent": ([C.c_void_p, C.c_void_p], C.c_int),
            "XCloseDisplay": ([C.c_void_p], C.c_int),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(self.lib, name)
            fn.argtypes, fn.restype = args, result
        self.display = self.lib.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError("An X11/Xwayland display is required")
        self.error_callback = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_void_p)(lambda *_: 0)
        self.lib.XSetErrorHandler(self.error_callback)
        self.root = self.lib.XDefaultRootWindow(self.display)

    def children(self, window):
        root, parent, count = C.c_ulong(), C.c_ulong(), C.c_uint()
        children = C.POINTER(C.c_ulong)()
        if not self.lib.XQueryTree(self.display, window, C.byref(root), C.byref(parent), C.byref(children), C.byref(count)):
            return []
        result = list(children[:count.value])
        if children:
            self.lib.XFree(children)
        return result

    def geometry(self, window):
        root, x, y = C.c_ulong(), C.c_int(), C.c_int()
        width, height, border, depth = [C.c_uint() for _ in range(4)]
        if not self.lib.XGetGeometry(self.display, window, C.byref(root), C.byref(x), C.byref(y), C.byref(width), C.byref(height), C.byref(border), C.byref(depth)):
            return None
        return width.value, height.value, depth.value

    def windows(self, parent=None, depth=0):
        if depth > 8:
            return
        parent = self.root if parent is None else parent
        for child in self.children(parent):
            yield child, parent
            yield from self.windows(child, depth + 1)

    def name(self, window):
        name = C.c_void_p()
        if not self.lib.XFetchName(self.display, window, C.byref(name)) or not name:
            return None
        result = C.string_at(name).decode("utf-8", "replace")
        self.lib.XFree(name)
        return result

    def pixel(self, window):
        image = self.lib.XGetImage(self.display, window, 310, 310, 1, 1, C.c_ulong(-1), 2)
        if not image:
            return None
        try:
            return self.lib.XGetPixel(image, 0, 0) & 0xffffff
        finally:
            self.lib.XDestroyImage(image)


def run(args):
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    log = out / "frames.log"
    log.write_text("")
    test_prefix = args.prefix.resolve()
    marker = test_prefix / ".proton-fusion-test-prefix"
    if (test_prefix / "pfx").exists() and not marker.exists():
        raise RuntimeError("Refusing an existing prefix without a .proton-fusion-test-prefix marker")
    test_prefix.mkdir(parents=True, exist_ok=True)
    marker.touch()
    env = os.environ.copy()
    module_hashes = {module: hashlib.sha256((args.proton / "files/lib/wine/x86_64-unix" / module).read_bytes()).hexdigest()
                     for module in ("win32u.so", "winex11.so")}
    for name in ("VK_INSTANCE_LAYERS", "VK_LAYER_PATH", "QT_QPA_PLATFORM", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "WINEDLLOVERRIDES"):
        env.pop(name, None)
    env.update(STEAM_COMPAT_DATA_PATH=str(args.prefix.resolve()),
               STEAM_COMPAT_CLIENT_INSTALL_PATH=str(args.steam.resolve()),
               PROTON_USE_WINED3D="0", PROTON_USE_XALIA="0", NO_AT_BRIDGE="1",
               WINEDEBUG=env.get("WINEDEBUG", "-all"),
               DXVK_CONFIG_FILE=str(args.config.resolve()),
               DXVK_LOG_PATH=str(out), DXVK_LOG_LEVEL="info")
    if args.layer:
        env.update(VK_LAYER_PATH=str(args.layer.resolve()), VK_INSTANCE_LAYERS="VK_LAYER_FUSION_present_sync")
    x = X11()
    top = source = gc = damage = damage_lib = None
    damage_base = C.c_int()
    samples, pending = [], []
    palette = (0xff0000, 0x00ff00, 0x0000ff, 0xffff00, 0x00ffff, 0xff00ff, 0xffffff, 0xff8000)
    read_position = 0
    damage_events = copies = 0
    stress_result = None
    started = time.monotonic()
    with (out / "runtime.log").open("w") as runtime_log:
        process = subprocess.Popen([str(args.proton.resolve() / "proton"), "run", str(args.exe.resolve()), "Z:" + str(log).replace("/", "\\"), str(args.bursts), str(args.effect), str(args.stress), str(args.gpu), str(args.cpu), str(args.size), str(int(args.resize)), str(int(args.minimize))], env=env, stdout=runtime_log, stderr=subprocess.STDOUT, start_new_session=True, stdin=subprocess.DEVNULL)
        try:
            done = False
            while time.monotonic() - started < args.timeout:
                if damage:
                    while x.lib.XPending(x.display):
                        event = (C.c_long * 24)()
                        x.lib.XNextEvent(x.display, event)
                        notification = C.cast(event, C.POINTER(DamageEvent)).contents
                        if notification.type == damage_base.value and notification.damage == damage:
                            damage_events += 1
                            damage_lib.XDamageSubtract(x.display, damage, 0, 0)
                            if args.damage_copy:
                                x.lib.XCopyArea(x.display, source, top, gc, 0, 0, 580, 580, 20, 50)
                                copies += 1
                            x.lib.XFlush(x.display)
                with log.open() as frames:
                    frames.seek(read_position)
                    chunk = frames.read()
                if "\n" in chunk:
                    complete, _ = chunk.rsplit("\n", 1)
                    read_position += len(complete) + 1
                    for line in complete.splitlines():
                        fields = line.split()
                        if fields[0] == "ERR":
                            raise RuntimeError("D3D11 reproducer failed: " + line)
                        if fields[0] == "READY":
                            candidates = [(w, p) for w, p in x.windows()]
                            named = [w for w, _ in candidates if x.name(w) == "SnapTest"]
                            if len(named) != 1:
                                raise RuntimeError(f"Expected exactly one SnapTest window, found {named}")
                            top = named[0]
                            if args.damage_observe or args.damage_copy:
                                sources = [w for w, p in candidates if x.geometry(w) == (580, 580, 24) and x.geometry(p) == (1, 1, 24)]
                                if len(sources) != 1:
                                    raise RuntimeError(f"Expected one isolated 580x580 child test surface, found {sources}")
                                source = sources[0]
                                damage_lib = C.CDLL("libXdamage.so.1")
                                damage_lib.XDamageQueryExtension.argtypes = [C.c_void_p, C.POINTER(C.c_int), C.POINTER(C.c_int)]
                                error_base = C.c_int()
                                if not damage_lib.XDamageQueryExtension(x.display, C.byref(damage_base), C.byref(error_base)):
                                    raise RuntimeError("XDamage extension unavailable")
                                damage_lib.XDamageCreate.argtypes = [C.c_void_p, C.c_ulong, C.c_int]
                                damage_lib.XDamageCreate.restype = C.c_ulong
                                damage_lib.XDamageSubtract.argtypes = [C.c_void_p, C.c_ulong, C.c_ulong, C.c_ulong]
                                damage = damage_lib.XDamageCreate(x.display, source, 3)
                                gc = x.lib.XCreateGC(x.display, top, 0, None)
                                x.lib.XFlush(x.display)
                        elif fields[0] == "F":
                            expected = int(fields[2])
                            now = time.monotonic()
                            pending.extend((now + delay / 1000, int(fields[1]), expected, delay) for delay in (30, 200))
                        elif fields[0] == "DONE":
                            done = True
                        elif fields[0] == "STRESS":
                            stress_result = dict(frames=int(fields[1]), mean_present_us=int(fields[2]))
                now = time.monotonic()
                for sample in list(pending):
                    deadline, burst, expected, delay = sample
                    if now >= deadline:
                        pixel = x.pixel(top)
                        # Allow a one-unit rounding difference for orange.
                        correct = pixel is not None and all(abs(((pixel >> shift) & 255) - ((palette[expected] >> shift) & 255)) <= 1 for shift in (0, 8, 16))
                        samples.append(dict(burst=burst, delay_ms=delay, expected=expected, pixel=pixel, correct=correct))
                        pending.remove(sample)
                if done and not pending:
                    break
                if process.poll() is not None and not pending:
                    if not done:
                        raise RuntimeError(f"Reproducer exited without DONE (code {process.returncode})")
                    break
                time.sleep(0.002)
            else:
                raise TimeoutError("Reproducer deadline exceeded")
            process.wait(timeout=15)
            result = dict(effect=args.effect, requested_bursts=args.bursts, samples=len(samples),
                          size=args.size, resize=args.resize, minimize=args.minimize,
                          gpu_copies=args.gpu, cpu_ms=args.cpu, stress_frames=args.stress,
                          module_hashes=module_hashes,
                          damage_disabled=env.get("WINE_FUSION_CHILD_DAMAGE") == "0",
                          continuous_present=stress_result,
                          damage_events=damage_events, damage_copies=copies,
                          elapsed_s=round(time.monotonic() - started, 3),
                          stale_30ms=sum(not s["correct"] for s in samples if s["delay_ms"] == 30),
                          stale_200ms=sum(not s["correct"] for s in samples if s["delay_ms"] == 200),
                          detail=samples, proton=str(args.proton.resolve()),
                          proton_version=(args.proton / "version").read_text().strip())
            if len(samples) != args.bursts * 2 or process.returncode:
                raise RuntimeError("Incomplete run: " + json.dumps(result))
            (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps({k: v for k, v in result.items() if k != "detail"}))
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            x.lib.XCloseDisplay(x.display)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proton", type=Path, required=True)
    parser.add_argument("--steam", type=Path, required=True)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--prefix", type=Path, required=True, help="A dedicated test prefix; never use the Fusion prefix")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--effect", type=int, choices=(0, 1), default=0)
    parser.add_argument("--bursts", type=int, default=30)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--layer", type=Path)
    parser.add_argument("--damage-observe", action="store_true")
    parser.add_argument("--damage-copy", action="store_true")
    parser.add_argument("--size", type=int, choices=(320, 384, 580), default=580)
    parser.add_argument("--resize", action="store_true")
    parser.add_argument("--minimize", action="store_true")
    parser.add_argument("--stress", type=int, default=0, help="Additional continuous presents after burst tests")
    parser.add_argument("--gpu", type=int, default=0, help="8192x8192 texture copies before each present")
    parser.add_argument("--cpu", type=int, default=0, help="CPU work in milliseconds before each present")
    run(parser.parse_args())
