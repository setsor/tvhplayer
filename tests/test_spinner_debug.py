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


def _wait_for_native_dump(watch):
    # The 60 ms native timeout is unchanged. A loaded runner may not
    # schedule its watchdog immediately; wait for actual output instead of
    # cancelling it after an assumed additional 50 ms scheduling margin.
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if os.fstat(watch._dump.fileno()).st_size > watch._dump_boundary:
            return
        time.sleep(0.005)
    pytest.fail('Native faulthandler did not write a dump')


def test_faulthandler_dump_comes_with_the_late_tick(make_watch):
    out = []
    watch = make_watch(out=out.append)
    watch.started()
    watch.tick()
    _wait_for_native_dump(watch)
    watch.tick()
    watch.stopped()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and not any('stopped after' in line for line in out):
        time.sleep(0.01)
    report = next(line for line in out if line.startswith('tick late'))
    assert 'faulthandler, all threads' in report
    # Check the native dump itself, not the independently sampled stacks.
    assert 'test_faulthandler_dump_comes_with_the_late_tick' in report.split(
        'faulthandler, all threads', 1)[1]


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
    _wait_for_native_dump(watch)
    watch.stopped()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and not any('stopped after' in line for line in out):
        time.sleep(0.01)
    report = next((line for line in out if line.startswith('tick late')), None)
    assert report is not None, out
    assert 'faulthandler, all threads' in report
    assert 'test_a_stall_that_ends_with_the_stop_is_reported' in report.split(
        'faulthandler, all threads', 1)[1]
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


def test_delayed_reporter_keeps_each_dump_with_its_own_interval(monkeypatch, make_watch):
    # Deterministically reproduce a delayed reporter: two completed native
    # dumps and a status/paint message are queued before it gets to read.
    # Direct fd writes model native output here; the preceding tests still
    # require the real native timer to produce a stack.
    clock = [100.0]
    monkeypatch.setattr(spinner_debug, 'time', SimpleNamespace(
        monotonic=lambda: clock[0], sleep=time.sleep))
    out = []
    watch = make_watch(out=out.append)
    gate = threading.Event()
    original_watchdog = watch._watchdog

    def delayed_watchdog():
        gate.wait()
        original_watchdog()

    monkeypatch.setattr(watch, '_watchdog', delayed_watchdog)
    monkeypatch.setattr(watch, '_arm', lambda: None)
    monkeypatch.setattr(watch, '_disarm', lambda: None)
    try:
        watch.started()
        fd = watch._dump.fileno()
        clock[0] += 0.1
        os.write(fd, b'first interval dump\n')
        watch.painted(0.02)
        watch.tick()
        clock[0] += 0.1
        os.write(fd, b'second interval dump\n')
        watch.tick()
        watch.stopped()
    finally:
        gate.set()
        watch.close()
    reports = [line for line in out if line.startswith('tick late')]
    assert len(reports) == 2, out
    assert 'first interval dump' in reports[0]
    assert 'second interval dump' not in reports[0]
    assert 'second interval dump' in reports[1]
    assert 'first interval dump' not in reports[1]
    assert any(line.startswith('slow spinner paint') for line in out)
