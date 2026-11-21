"""Pytest diagnostic: report app worker threads left alive after each UI test."""
import threading
import traceback

def pytest_runtest_teardown(item, nextitem):
    app_threads = [
        thread for thread in threading.enumerate()
        if thread.is_alive() and (
            thread.name in {"tasks-fetch", "start-watch"}
            or "tasks-fetch" in thread.name
            or "start-watch" in thread.name
        )
    ]
    if app_threads:
        print(
            f"THREAD-AUDIT after={item.nodeid} "
            f"active={[(t.name, t.ident, t.daemon) for t in app_threads]}",
            flush=True,
        )
        frames = sys._current_frames()
        for thread in app_threads:
            frame = frames.get(thread.ident)
            if frame is not None:
                print(f"THREAD-AUDIT stack {thread.name}:\n" +
                      "".join(traceback.format_stack(frame)), flush=True)

import sys
