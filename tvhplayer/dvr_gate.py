"""Serialize server DVR Stop/Cancel writes and reconcile uncertain outcomes.

Every write goes through one Qt worker. An error or timeout never triggers an
automatic retry: only a fresh server DVR snapshot can resolve the unknown
outcome for the exact recording UUID.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot

from .core.playlist_sync import server_key


class _DvrWrite(QRunnable):
    def __init__(self, gate, factory, sequence, server, action, entry):
        super().__init__()
        self.gate = gate
        self.factory = factory
        self.sequence = sequence
        self.server = dict(server)
        self.action = action
        self.entry = entry

    def run(self):
        backend = None
        error = None
        result = None
        try:
            backend = self.factory(self.server)
            if self.action == 'stop':
                result = backend.stop_dvr_entry(self.entry)
            elif self.action == 'cancel':
                result = backend.cancel_dvr_entry(self.entry)
            else:
                raise ValueError('Unsupported DVR action')
        except Exception as exc:
            # Do not expose credential-bearing URLs in UI or logs.
            error = type(exc).__name__
        finally:
            if backend is not None:
                try:
                    backend.close()
                except Exception:
                    pass
        self.gate.finished.emit(self.sequence, result, error)


class DvrGate(QObject):
    """Single in-flight mutation; uncertain actions are never sent twice."""

    finished = pyqtSignal(int, object, object)

    def __init__(self, backend_factory, parent=None):
        super().__init__(parent)
        self.backend_factory = backend_factory
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.finished.connect(self._completed)
        self.busy = False
        self.uncertain = False
        self.awaiting_verification = False
        self.pending_uuid = None
        self.pending_server = None
        self.pending_action = None
        self.callback = None
        self._sequence = 0

    def submit(self, server, action, entry, callback=None):
        if (self.busy or self.uncertain or self.awaiting_verification
                or action not in ('stop', 'cancel') or not server
                or not getattr(entry, 'uuid', None)):
            return False
        self.busy = True
        self._sequence += 1
        self.pending_uuid = str(entry.uuid)
        self.pending_server = server_key(server)
        self.pending_action = action
        self.callback = callback
        self.pool.start(_DvrWrite(
            self, self.backend_factory, self._sequence, server, action, entry
        ))
        return True

    @pyqtSlot(int, object, object)
    def _completed(self, sequence, result, error):
        if sequence != self._sequence:
            return
        self.busy = False
        self.uncertain = error is not None
        self.awaiting_verification = True
        callback, self.callback = self.callback, None
        if callback is not None:
            try:
                callback(result, error)
            except Exception:
                # Never allow an exception in a Qt slot to terminate the app.
                pass

    def reconcile(self, server, entries):
        """A successful *fresh* DVR read decides whether the exact job ended."""
        if (self.busy or not self.awaiting_verification or
                server_key(server) != self.pending_server):
            return False
        for entry in entries:
            if str(getattr(entry, 'uuid', '')) != self.pending_uuid:
                continue
            category = entry.category()
            if self.pending_action == 'stop' and category == 'recording':
                return False
            if self.pending_action == 'cancel' and category == 'upcoming':
                return False
        self.uncertain = False
        self.awaiting_verification = False
        self.pending_uuid = None
        self.pending_server = None
        self.pending_action = None
        return True
