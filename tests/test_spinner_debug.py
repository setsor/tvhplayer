import os
import threading
import time
from types import SimpleNamespace

import pytest

from tvhplayer import spinner_debug


@pytest.fixture
def make_watch(monkeypatch):
    # The diagnostic owns a daemon and a process-wide faulthandler timer.
    # Dispose of each watcher before the next test (and before monkeypatch
    # restores the real clock or the platform's file APIs).
    watches = []

    def create(*args, **kwargs):
        watch = spinner_debug.SpinnerWatch(*args, **kwargs)
        watches.append(watch)
        return watch

    yield create
    for watch in reversed(watches):
        watch.close()
        assert watch._thread is None or not watch._thread.is_alive()
        assert watch._dump is None or watch._dump.closed
        assert watch._dump_reader is None or watch._dump_reader.closed


def test_off_unless_asked(monkeypatch):
    monkeypatch.delenv(spinner_debug.DEBUG_ENV, raising=False)
    assert not spinner_debug.enabled()
    monkeypatch.setenv(spinner_debug.DEBUG_ENV, '0')
    assert not spinner_debug.enabled()
    monkeypatch.setenv(spinner_debug.DEBUG_ENV, '1')
    assert spinner_debug.enabled()


def test_module_hooks_do_nothing_when_off(monkeypatch):
    monkeypatch.setattr(spinner_debug, '_watch', None)
    spinner_debug.started()
    spinner_debug.tick()
    spinner_debug.painted(1.0)
    spinner_debug.stopped()


def test_faulthandler_dump_comes_with_the_late_tick(make_watch):
    out = []
    watch = make_watch(out=out.append)
    watch.started()
    watch.tick()
    time.sleep(spinner_debug.FAULT_SECONDS + 0.05)
    watch.tick()
    watch.stopped()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and not any('stopped after' in line for line in out):
        time.sleep(0.01)
    report = next(line for line in out if line.startswith('tick late'))
    assert 'faulthandler, all threads' in report
    assert 'test_faulthandler_dump_comes_with_the_late_tick' in report


def test_on_time_ticks_are_not_reported(monkeypatch, make_watch):
    # Exercise the classification of known on-time ticks, not the CI
    # scheduler's ability to wake a sleeping thread within 50 ms.
    # Keep the actual watchdog/report delivery; the other tests exercise
    # real faulthandler timeouts and stalls.
    clock = [100.0]
    monkeypatch.setattr(spinner_debug, 'time', SimpleNamespace(
        monotonic=lambda: clock[0], sleep=time.sleep))
    out = []
    reported = threading.Event()

    def collect(message):
        out.append(message)
        if message.startswith('spinner stopped after'):
            reported.set()

    watch = make_watch(out=collect, dump=False)
    watch.started()
    try:
        for gap in (0.016, 0.016, 0.049, 0.016, 0.016):
            clock[0] += gap
            watch.tick()
    finally:
        watch.stopped()
    assert reported.wait(2), out
    assert not any(line.startswith('tick late') for line in out), out
    assert '5 ticks, 0 late' in out[-1]


def test_threads_in_blocking_calls_are_marked_waiting():
    event = threading.Event()
    waiter = threading.Thread(target=event.wait, name='sleeper')
    waiter.start()
    try:
        time.sleep(0.02)
        text = spinner_debug.format_late(0.2, [spinner_debug.snapshot()])
    finally:
        event.set()
        waiter.join()
    assert 'sleeper: waiting at' in text


def test_a_stall_that_ends_with_the_stop_is_reported(make_watch):
    # The window is often busy right as the picture comes: the spinner stops
    # without another tick, and that stall must still be reported.
    out = []
    watch = make_watch(out=out.append)
    watch.started()
    watch.tick()
    time.sleep(spinner_debug.FAULT_SECONDS + 0.05)
    watch.stopped()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and not any('stopped after' in line for line in out):
        time.sleep(0.01)
    report = next((line for line in out if line.startswith('tick late')), None)
    assert report is not None, out
    assert 'test_a_stall_that_ends_with_the_stop_is_reported' in report
    assert '1 late' in out[-1]



def test_dump_reader_without_pread_preserves_writer_offset(monkeypatch, make_watch):
    # Exercise the Windows path on all platforms, using direct fd writes
    # just as faulthandler does. Reading must not change the writer's offset.
    monkeypatch.delattr(os, 'pread', raising=False)
    watch = make_watch()
    fd = watch._dump.fileno()
    try:
        first, second = b'first dump\n', b'second dump\n'
        assert os.write(fd, first) == len(first)
        assert watch._new_dump() == first.decode()
        assert os.lseek(fd, 0, os.SEEK_CUR) == len(first)
        assert watch._new_dump() == ''
        assert os.write(fd, second) == len(second)
        assert watch._new_dump() == second.decode()
        assert os.lseek(fd, 0, os.SEEK_CUR) == len(first) + len(second)
        assert watch._new_dump() == ''
    finally:
        watch.close()


def test_close_stops_the_watchdog_and_releases_its_files(make_watch):
    out = []
    watch = make_watch(out=out.append)
    watch.started()
    thread = watch._thread
    watch.close()
    assert thread is not None and not thread.is_alive()
    assert watch._dump.closed
    assert watch._dump_reader is None or watch._dump_reader.closed
    assert any(line.startswith('spinner stopped after') for line in out), out
    # Closing twice must be safe, but a disposed watch must not restart.
    watch.close()
    with pytest.raises(RuntimeError, match='closed'):
        watch.started()
