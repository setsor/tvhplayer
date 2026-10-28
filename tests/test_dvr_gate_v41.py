"""The v4.1 UI must serialize DVR mutations and resolve unknown Stop outcomes."""
import threading
import time

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtTest import QTest

from tvhplayer.dvr_gate import DvrGate


class Entry:
    def __init__(self, uuid, category='recording'):
        self.uuid = uuid
        self._category = category

    def category(self):
        return self._category


def _app():
    return QCoreApplication.instance() or QCoreApplication([])


def _until(condition):
    app = _app()
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        app.processEvents()
        if condition():
            return True
        QTest.qWait(10)
    return False


def test_gate_serializes_stop_and_verifies_only_selected_uuid():
    _app()
    started = threading.Event()
    release = threading.Event()
    calls = []
    callbacks = []

    class Backend:
        def stop_dvr_entry(self, entry):
            calls.append(('stop', entry.uuid))
            started.set()
            assert release.wait(2)
            return {'accepted': True}

        def close(self):
            pass

    gate = DvrGate(lambda _server: Backend())
    server = {'url': 'http://nas:9981'}
    entry = Entry('uuid-1')
    assert gate.submit(server, 'stop', entry, lambda result, err: callbacks.append((result, err)))
    assert started.wait(2)
    assert not gate.submit(server, 'stop', entry)
    release.set()
    assert _until(lambda: not gate.busy)
    assert callbacks == [({'accepted': True}, None)]
    assert calls == [('stop', 'uuid-1')]
    assert gate.awaiting_verification
    assert not gate.submit(server, 'stop', entry)
    assert not gate.reconcile(server, [Entry('uuid-1', 'recording')])
    assert not gate.reconcile({'url': 'http://other:9981'}, [])
    assert gate.reconcile(server, [Entry('uuid-2', 'recording')])
    assert not gate.awaiting_verification
    assert not gate.uncertain


def test_gate_marks_timeout_uncertain_and_never_retries():
    _app()
    calls = []
    done = []

    class Backend:
        def stop_dvr_entry(self, entry):
            calls.append(entry.uuid)
            raise TimeoutError('simulated delayed response')

        def close(self):
            pass

    gate = DvrGate(lambda _server: Backend())
    server = {'url': 'http://nas:9981'}
    entry = Entry('uuid-1')
    assert gate.submit(server, 'stop', entry, lambda _result, error: done.append(error))
    assert _until(lambda: not gate.busy)
    assert done == ['TimeoutError']
    assert calls == ['uuid-1']
    assert gate.uncertain and gate.awaiting_verification
    assert not gate.submit(server, 'stop', entry)
    assert not gate.reconcile(server, [entry])
    assert not gate.submit(server, 'stop', entry)
    # A fresh authoritative server state that no longer shows recording
    # is the only way to clear the unknown result.
    assert gate.reconcile(server, [Entry('uuid-1', 'finished')])
    assert not gate.uncertain
    assert calls == ['uuid-1']


def test_gate_cancel_is_serialized_and_reconciled_separately():
    _app()
    calls = []

    class Backend:
        def cancel_dvr_entry(self, entry):
            calls.append(('cancel', entry.uuid))

        def close(self):
            pass

    gate = DvrGate(lambda _server: Backend())
    server = {'url': 'http://nas:9981'}
    assert gate.submit(server, 'cancel', Entry('timer-1', 'upcoming'))
    assert _until(lambda: not gate.busy)
    assert gate.awaiting_verification
    assert not gate.reconcile(server, [Entry('timer-1', 'upcoming')])
    assert gate.reconcile(server, [Entry('timer-1', 'finished')])
    assert calls == [('cancel', 'timer-1')]
