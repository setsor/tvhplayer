"""Isolate test-order contamination before the built-in shutdown lookup.

Diagnostic only. Selects collected node ids in original order and reruns
contiguous suffixes before the target in fresh subprocesses. A failing prefix
does not establish a culprit; we record whether the target itself failed.
"""
import os
from pathlib import Path
import re
import subprocess
import sys

TEST_FILE = "tests/test_pyqt6_ui.py"
TARGET = "test_quit_asks_the_builtin_server_even_when_another_is_selected"
OUT = Path("diagnostics/quit-interference")
OUT.mkdir(parents=True, exist_ok=True)
BASE = [sys.executable, "-X", "faulthandler", "-m", "pytest", "-q", "-x",
        "--tb=short", "--timeout=120", "-p", "no:cacheprovider"]
ENV = dict(os.environ, PYTHONUNBUFFERED="1", TVHPLAYER_DIAG_NO_MODULE_RELOAD="0")


def run(label, arguments):
    try:
        proc = subprocess.run(BASE + arguments, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, env=ENV, timeout=180)
        output, status = proc.stdout, proc.returncode
    except subprocess.TimeoutExpired as exc:
        output, status = str(exc.stdout or "") + "\nTIMEOUT", 124
    (OUT / (label + ".log")).write_text(output, encoding="utf-8", errors="replace")
    failed_target = bool(re.search(r"FAILED\s+[^\n]*" + re.escape(TARGET), output))
    line = f"{label}: exit={status}; target_failed={failed_target}; selected={len(arguments)}"
    print(line, flush=True)
    for part in output.splitlines():
        if "FAILED " in part or "Fatal Python error" in part or "ERROR " in part:
            print("  " + part[:220], flush=True)
    with (OUT / "summary.txt").open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return failed_target, status


collection = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q",
                             "-p", "no:cacheprovider", TEST_FILE],
                            text=True, capture_output=True, env=ENV, timeout=90)
(OUT / "collection.log").write_text(collection.stdout + collection.stderr, encoding="utf-8")
if collection.returncode:
    raise SystemExit("pytest collection failed")
nodes = [line.strip() for line in collection.stdout.splitlines()
         if line.strip().startswith(TEST_FILE + "::")]
matches = [i for i, item in enumerate(nodes) if item.split("::")[-1].split("[")[0] == TARGET]
if len(matches) != 1:
    raise SystemExit(f"Expected exactly one {TARGET}, got {len(matches)}")
prior = nodes[:matches[0]]
target = nodes[matches[0]]
print(f"Collected {len(nodes)} cases; {len(prior)} precede target", flush=True)
(OUT / "prior-nodeids.txt").write_text("\n".join(f"{i}: {node}" for i, node in enumerate(prior)),
                                       encoding="utf-8")
alone, _ = run("target-alone", [target])
whole, _ = run("all-prior-and-target", prior + [target])
if alone:
    print("Target fails alone; not an order-dependent reproduction.")
elif not whole:
    print("Prefix does not reproduce; failure may require later tests or environment.")
else:
    # Determine the shortest contiguous suffix of earlier tests that reproduces
    # the target failure. Each probe is a brand new interpreter.
    low, high = 0, len(prior)
    rounds = 0
    while high - low > 1 and rounds < 8:
        middle = (low + high) // 2
        suffix = prior[middle:] + [target]
        failed, status = run(f"suffix-from-{middle:03d}", suffix)
        if failed:
            low = middle
        else:
            high = middle
        rounds += 1
    print(f"Boundary: suffix starting at index {low} reproduces; "
          f"next index {high} does not (subject to repeatability).", flush=True)
    run("boundary-repeat", prior[low:] + [target])
print(f"Diagnostic files: {OUT}", flush=True)
