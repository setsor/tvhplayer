"""Diagnostic-only Windows QLocalSocket activation probe.

This test intentionally reports Qt's write/flush state rather than asserting a
fix. It runs in the existing cross-platform pytest workflow, so no separate
workflow registration in the default branch is required.
"""
import sys
import tempfile
from pathlib import Path

import pytest
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtNetwork import QLocalSocket

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows QLocalSocket diagnostic")

def test_windows_local_socket_activation_probe():
    from tvhplayer.app_instance import AppInstance

    app = QCoreApplication.instance() or QCoreApplication([])
    with tempfile.TemporaryDirectory() as directory:
        owner = AppInstance(Path(directory))
        second = AppInstance(Path(directory))
        received = []
        owner.show_requested.connect(lambda: received.append("show"))
        try:
            assert owner.acquire() is True
            print("owner listening:", owner.server.isListening(), flush=True)
            print("server name:", owner.name, flush=True)
            try:
                result = second.acquire()
                print("second.acquire result:", result, flush=True)
            except RuntimeError as exc:
                print("second.acquire error:", repr(exc), flush=True)

            app.processEvents()
            print("owner received after acquire:", received, flush=True)

            probe = QLocalSocket()
            probe.connectToServer(owner.name)
            connected = probe.waitForConnected(3000)
            print("probe connected:", connected, flush=True)
            print("probe state:", probe.state().name, flush=True)
            print("probe error:", probe.errorString(), flush=True)
            if connected:
                count = probe.write(b"show\n")
                print("probe write bytes:", count, flush=True)
                print("bytesToWrite before wait:", probe.bytesToWrite(), flush=True)
                acknowledged = probe.waitForBytesWritten(1000)
                print("waitForBytesWritten:", acknowledged, flush=True)
                print("bytesToWrite after wait:", probe.bytesToWrite(), flush=True)
                print("probe error after wait:", probe.errorString(), flush=True)
                app.processEvents()
                print("owner received after processEvents:", received, flush=True)
                probe.disconnectFromServer()
        finally:
            second.close()
            owner.close()
