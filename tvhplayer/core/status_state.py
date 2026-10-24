"""Small, Qt-independent state model for the TVHplayer status bar.

A short-lived action notice is not the status of an ongoing DVR job.
Server recordings are counted from a successful Tasks snapshot, never from
an earlier "Recording started" message.
"""

from dataclasses import dataclass


def server_recording_count(tasks):
    """Number of actual, currently running server DVR entries in a Tasks snapshot."""
    if not isinstance(tasks, list):
        return 0
    return sum(
        1 for task in tasks
        if isinstance(task, dict)
        and task.get("kind") == "Server"
        and task.get("bucket") == "recording"
    )


@dataclass
class StatusState:
    playing_channel: str = ""
    server_recordings: int | None = None
    local_recording: bool = False

    @property
    def playback_label(self):
        return f"Playing: {self.playing_channel}" if self.playing_channel else "Ready"

    @property
    def recording_label(self):
        label = (
            f"REC {self.server_recordings}"
            if self.server_recordings is not None else "REC ?"
        )
        return label + (" · LOCAL" if self.local_recording else "")

    @property
    def has_active_recordings(self):
        return self.local_recording or (
            self.server_recordings is not None and self.server_recordings > 0
        )

    def set_server_tasks(self, tasks):
        """Use None for server unavailable, never translate a timeout to zero."""
        self.server_recordings = (
            None if tasks is None else server_recording_count(tasks)
        )
