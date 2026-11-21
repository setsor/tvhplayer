"""Windows-only read-only diagnostic of QLocalSocket activation handoff."""
import tempfile
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtNetwork import QLocalSocket
from tvhplayer.app_instance import AppInstance

app = QCoreApplication.instance() or QCoreApplication([])
with tempfile.TemporaryDirectory() as directory:
    owner = AppInstance(Path(directory))
    second = AppInstance(Path(directory))
    owner.show_requested.connect(lambda: print("show_requested emitted", flush=True))
    try:
        print("owner.acquire:", owner.acquire(), flush=True)
        print("owner listening:", owner.server.isListening(), flush=True)
        print("server name:", owner.name, flush=True)
        print("server full name:", owner.server.fullServerName(), flush=True)
        try:
            print("second.acquire:", second.acquire(), flush=True)
        except RuntimeError as exc:
            print("second.acquire raised:", repr(exc), flush=True)
        app.processEvents()
        # Explicit probe to distinguish write acknowledgement from delivery.
        probe = QLocalSocket()
        probe.connectToServer(owner.name)
        connected = probe.waitForConnected(3000)
        print("probe waitForConnected:", connected, flush=True)
        print("probe state:", probe.state().name, flush=True)
        print("probe error:", probe.errorString(), flush=True)
        if connected:
            written = probe.write(b"show\n")
            print("probe write bytes:", written, flush=True)
            print("probe bytesToWrite before wait:", probe.bytesToWrite(), flush=True)
            acknowledged = probe.waitForBytesWritten(1000)
            print("probe waitForBytesWritten:", acknowledged, flush=True)
            print("probe bytesToWrite after wait:", probe.bytesToWrite(), flush=True)
            print("probe error after wait:", probe.errorString(), flush=True)
            app.processEvents()
        probe.disconnectFromServer()
    finally:
        second.close()
        owner.close()
