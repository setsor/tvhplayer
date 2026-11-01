#!/usr/bin/env python3
"""Bounded native libmpv playback test with an artificial local MPEG-TS file.

The Python parent enforces a hard process timeout. No GUI, server access,
credentials or network connectivity are used.
"""
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import time


class MpvEvent(ctypes.Structure):
    _fields_ = [
        ("event_id", ctypes.c_int),
        ("error", ctypes.c_int),
        ("reply_userdata", ctypes.c_uint64),
        ("data", ctypes.c_void_p),
    ]


def child(lib_path, sample_path):
    lib = ctypes.CDLL(lib_path)
    ptr = ctypes.c_void_p
    lib.mpv_create.restype = ptr
    lib.mpv_set_option_string.argtypes = [ptr, ctypes.c_char_p, ctypes.c_char_p]
    lib.mpv_set_option_string.restype = ctypes.c_int
    lib.mpv_initialize.argtypes = [ptr]
    lib.mpv_initialize.restype = ctypes.c_int
    lib.mpv_command.argtypes = [ptr, ctypes.POINTER(ctypes.c_char_p)]
    lib.mpv_command.restype = ctypes.c_int
    lib.mpv_wait_event.argtypes = [ptr, ctypes.c_double]
    lib.mpv_wait_event.restype = ctypes.POINTER(MpvEvent)
    lib.mpv_terminate_destroy.argtypes = [ptr]
    lib.mpv_terminate_destroy.restype = None
    handle = lib.mpv_create()
    if not handle:
        raise RuntimeError("mpv_create returned NULL")
    for key, value in [
        ("vo", "null"), ("ao", "null"), ("hwdec", "no"),
        ("config", "no"), ("load-scripts", "no"), ("idle", "yes"),
    ]:
        rc = lib.mpv_set_option_string(handle, key.encode(), value.encode())
        print(f"native option {key}: rc={rc}", flush=True)
        if rc < 0:
            return 2
    rc = lib.mpv_initialize(handle)
    print(f"native initialize: rc={rc}", flush=True)
    if rc < 0:
        return 3
    # Pass exactly the same loadfile command recognized by MPV, with a local
    # file. This isolates native command dispatch and demux from network and GL.
    args = (ctypes.c_char_p * 4)(b"loadfile", os.fsencode(sample_path), b"replace", None)
    rc = lib.mpv_command(handle, args)
    print(f"native loadfile: rc={rc}", flush=True)
    if rc < 0:
        return 4
    events = []
    deadline = time.monotonic() + 9.0
    while time.monotonic() < deadline:
        ev = lib.mpv_wait_event(handle, 0.4).contents
        if ev.event_id:
            events.append((ev.event_id, ev.error))
            print(f"native event: id={ev.event_id} error={ev.error}", flush=True)
        if ev.event_id == 21:
            break
        if ev.event_id == 7 and ev.error < 0:
            break
    started = any(k == 6 for k, _ in events)
    loaded = any(k == 8 for k, _ in events)
    print(f"native summary: started={started} loaded={loaded} events={events}", flush=True)
    if not (started and loaded):
        # If the core is deadlocked, never synchronously destroy in this child;
        # the process supervisor will take care of shutdown safely.
        return 5
    print("native terminate begin", flush=True)
    lib.mpv_terminate_destroy(handle)
    print("native terminate success", flush=True)
    return 0


def main():
    if len(sys.argv) != 3 and len(sys.argv) != 4:
        raise SystemExit("usage: smoke_libmpv.py libmpv.2.dylib sample.ts")
    lib_path, sample_path = sys.argv[1:3]
    assert Path(lib_path).is_file()
    assert Path(sample_path).is_file()
    if len(sys.argv) == 4:
        raise SystemExit(child(lib_path, sample_path))
    try:
        p = subprocess.run(
            [sys.executable, __file__, lib_path, sample_path, "--child"],
            capture_output=True, text=True, timeout=25, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        print("NATIVE PLAYBACK SMOKE: TIMEOUT after 25 seconds")
        if exc.stdout:
            print(exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout)
        if exc.stderr:
            print(exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr)
        raise SystemExit(124)
    print(p.stdout, end="")
    if p.stderr:
        print("native stderr tail:\n" + p.stderr[-3000:])
    print(f"NATIVE PLAYBACK SMOKE EXIT={p.returncode}")
    raise SystemExit(p.returncode)


if __name__ == "__main__":
    main()
