"""Report TVHplayer worker threads that survive each UI test."""
import sys
import threading
import traceback


def pytest_runtest_teardown(item, nextitem):
    names = {"tasks-fetch", "start-watch"}
    threads = [
        thread for thread in threading.enumerate()
        if thread.is_alive() and (
            thread.name in names
            or thread.name.startswith("tasks-fetch")
            or thread.name.startswith("start-watch")
        )
    ]
    if not threads:
        return
    frames = sys._current_frames()
    print(
        f"THREAD-AUDIT after={item.nodeid} "
        f"active={[(thread.name, thread.ident, thread.daemon) for thread in threads]}",
        flush=True,
    )
    for thread in threads:
        frame = frames.get(thread.ident)
        if frame is not None:
            print(
                f"THREAD-AUDIT stack {thread.name}:\n"
                + "".join(traceback.format_stack(frame)),
                flush=True,
            )
