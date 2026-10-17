"""Serialized DVR HTTP operations for the macOS Qt interface.

The main window owns one QThreadPool with maxThreadCount=1. All DVR list
requests and selective STOP commands go through this pool. They cannot
overlap from this client and never block the GUI thread.

A read timeout does NOT cancel processing on TVHeadend. Treat stop timeouts
as unknown outcomes; never auto-retry a stop request.
"""

import time

import requests
from PyQt5.QtCore import QObject, QRunnable, pyqtSignal

try:
    from .recording_activity import active_recordings, stop_payload
except ImportError:
    from recording_activity import active_recordings, stop_payload


def _server_connection(server):
    url = str(server.get("url") or "").rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    auth = None
    if server.get("username") or server.get("password"):
        auth = (server.get("username", ""), server.get("password", ""))
    return url, auth


class RecordingSignals(QObject):
    completed = pyqtSignal(object)


class RecordingPollWorker(QRunnable):
    """Fetch the full DVR grid once, also extracting the active recordings."""

    def __init__(self, server):
        super().__init__()
        self.setAutoDelete(False)
        self.server = dict(server)
        self.signals = RecordingSignals()

    def run(self):
        url, auth = _server_connection(self.server)
        result = {
            "url": self.server.get("url"),
            "success": False,
            "entries": [],
            "recordings": [],
            "total": None,
        }
        try:
            response = requests.get(
                f"{url}/api/dvr/entry/grid",
                params={"start": 0, "limit": 500},
                auth=auth,
                timeout=(2, 4),
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("entries"), list):
                raise ValueError("Invalid DVR grid")
            result["entries"] = payload["entries"]
            result["recordings"] = active_recordings(payload["entries"])
            result["total"] = payload.get("total")
            result["success"] = True
        except (requests.RequestException, ValueError, TypeError):
            # Unknown is not zero. Never expose credentials or response bodies.
            pass
        finally:
            self.signals.completed.emit(result)


class RecordingStopWorker(QRunnable):
    """Issue exactly one selected DVR stop request, never retrying it."""

    def __init__(self, server, recording):
        super().__init__()
        self.setAutoDelete(False)
        self.server = dict(server)
        self.uuid = stop_payload(recording)["uuid"]
        self.signals = RecordingSignals()

    def run(self):
        url, auth = _server_connection(self.server)
        result = {
            "url": self.server.get("url"),
            "uuid": self.uuid,
            "outcome": "unknown",
            "http_status": None,
            "elapsed_seconds": None,
        }
        started = time.monotonic()
        try:
            response = requests.post(
                f"{url}/api/dvr/entry/stop",
                data={"uuid": self.uuid},
                auth=auth,
                timeout=(2, 7),
            )
            result["http_status"] = response.status_code
            result["outcome"] = (
                "accepted" if response.status_code == 200 else "rejected"
            )
        except requests.RequestException:
            # Do not infer that the server did not process the request.
            # A timeout after transmission is an UNKNOWN stop result.
            pass
        finally:
            result["elapsed_seconds"] = round(time.monotonic() - started, 2)
            self.signals.completed.emit(result)
