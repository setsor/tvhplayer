"""Persistent playback state and temporary status messages.

This module does not depend on Qt, so the behaviour is regression-testable.
The Qt widget supplies the timer for expiring temporary messages.
"""


class PlaybackStatus:
    def __init__(self):
        self.channel = None
        self._notification = None

    @property
    def persistent_text(self):
        return f"Playing: {self.channel}" if self.channel else "Ready"

    @property
    def visible_text(self):
        return self._notification if self._notification is not None else self.persistent_text

    def start_playback(self, channel):
        name = str(channel or "").strip()
        self.channel = name or None
        self._notification = None

    def stop_playback(self):
        self.channel = None
        self._notification = None

    def notify(self, message):
        self._notification = str(message)

    def restore(self):
        self._notification = None
