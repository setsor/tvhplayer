"""Background DVR status polling for the macOS Qt interface.

Do not block live playback/UI while retrieving TVHeadend recording status.
Network requests use the same session credentials already configured for TVH.
No credentials or server responses are emitted in status signals/logs.
"""

import requests
from PyQt5.QtCore import QObject, QRunnable, pyqtSignal

try:
    from .recording_activity import active_recordings
except ImportError:
    from recording_activity import active_recordings


class RecordingPollSignals(QObject):
    completed = pyqtSignal(object)


class RecordingPollWorker(QRunnable):
    def __init__(self, server):
        super().__init__()
        self.server = dict(server)
        self.signals = RecordingPollSignals()

    def run(self):
        server_url = str(self.server.get("url") or "").rstrip("/")
        if not server_url.startswith(("http://", "https://")):
            server_url = "http://" + server_url

        result = {
            "url": self.server.get("url"),
            "success": False,
            "recordings": [],
        }
        try:
            auth = None
            if self.server.get("username") or self.server.get("password"):
                auth = (self.server.get("username", ""), self.server.get("password", ""))
            response = requests.get(
                f"{server_url}/api/dvr/entry/grid",
                auth=auth,
                timeout=(2, 4),
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("entries"), list):
                raise ValueError("DVR grid returned an invalid entry list")
            result["recordings"] = active_recordings(payload["entries"])
            result["success"] = True
        except (requests.RequestException, ValueError, TypeError):
            # Unknown is not zero: do not pretend there are no recordings.
            pass
        finally:
            self.signals.completed.emit(result)
