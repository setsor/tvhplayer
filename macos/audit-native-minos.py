#!/usr/bin/env python3
"""List the macOS minimum OS declared by every Mach-O binary in a .app.

Not a substitute for testing on the actual macOS version: SDK features,
weak-linked symbols, CPU features and runtime dependencies still matter.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys


def required_versions(load_commands):
    result = []
    lines = load_commands.splitlines()
    for i, line in enumerate(lines):
        cmd = line.strip()
        if cmd == "cmd LC_BUILD_VERSION":
            chunk = "\n".join(lines[i + 1:i + 9])
            match = re.search(r"\bminos\s+(\d+(?:\.\d+){1,2})", chunk)
            if match:
                result.append(tuple(int(x) for x in match.group(1).split(".")))
        elif cmd == "cmd LC_VERSION_MIN_MACOSX":
            chunk = "\n".join(lines[i + 1:i + 9])
            match = re.search(r"\bversion\s+(\d+(?:\.\d+){1,2})", chunk)
            if match:
                result.append(tuple(int(x) for x in match.group(1).split(".")))
    return result


def main():
    if len(sys.argv) != 3:
        print("usage: audit-native-minos.py APP_PATH OUTPUT_TSV", file=sys.stderr)
        return 2
    app = pathlib.Path(sys.argv[1])
    report = pathlib.Path(sys.argv[2])
    found, unknown, unsuitable = [], [], []
    conda_prefix = (app / "conda-meta").exists()
    for path in sorted(p for p in app.rglob("*") if p.is_file() and not p.is_symlink()):
        # A conda installation includes thousands of Python scripts, caches,
        # package metadata and other files never bundled into the app.
        # Only native libraries and media executables matter in this preflight.
        if conda_prefix and not (path.name.endswith((".dylib", ".so"))
                                 or path.name in ("ffmpeg", "ffprobe", "mpv")):
            continue
        description = subprocess.run(
            ["file", "-b", str(path)], capture_output=True, text=True, errors='replace', check=False
        ).stdout
        if "Mach-O" not in description:
            continue
        otool = subprocess.run(
            ["otool", "-l", str(path)], capture_output=True, text=True, errors='replace', check=False
        )
        relative = str(path.relative_to(app))
        versions = required_versions(otool.stdout) if otool.returncode == 0 else []
        if not versions:
            unknown.append(relative)
            found.append((relative, "UNKNOWN", description.strip()))
            continue
        version = max(versions)
        version_str = ".".join(map(str, version))
        found.append((relative, version_str, description.strip()))
        if version > (13, 0):
            unsuitable.append((relative, version_str))
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "Mach-O path\tmaximum minOS across architectures\tfile description\n"
        + "\n".join("\t".join(row) for row in found) + "\n",
        encoding="utf-8"
    )
    print(f"Audited {len(found)} Mach-O files; {len(unsuitable)} declare minimum macOS above 13; {len(unknown)} unknown.")
    if unsuitable:
        print("NOT A VENTURA-COMPATIBLE BUILD (native minimum OS is too high):")
        for path, version in unsuitable[:30]:
            print(f"  {version}: {path}")
        if len(unsuitable) > 30:
            print(f"  ... {len(unsuitable) - 30} more in {report}")
    elif unknown:
        print("Ventura binary compatibility not established (unknown Mach-O minima).")
    else:
        print("All declared Mach-O minima allow macOS 13; runtime compatibility still untested.")
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main())
