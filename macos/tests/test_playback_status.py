"""Playback status and TVHeadend HTTP server information regression tests."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tvhplayer"))

from playback_status import PlaybackStatus
from server_info import format_server_information


class ServerInfoTests(unittest.TestCase):
    def test_api_uses_name_not_server_name(self):
        info = format_server_information(
            {"name": "tvheadend", "url": "http://example.invalid:9981"},
            {
                "name": "Tvheadend",
                "sw_version": "4.3-2653",
                "api_version": 19,
                "capabilities": ["libav", "tvadapters"],
            },
        )
        self.assertIn("Server Name: tvheadend", info)
        self.assertIn("Software: Tvheadend", info)
        self.assertIn("Server Version: 4.3-2653", info)
        self.assertIn("API Version: 19", info)
        self.assertNotIn("Unknown", info)
        self.assertNotIn("server_name", info)

    def test_displays_configured_name_without_api_response(self):
        info = format_server_information(
            {"name": "My NAS", "url": "http://example.invalid:9981"}
        )
        self.assertIn("Server Name: My NAS", info)
        self.assertNotIn("Unknown", info)

    def test_api_missing_software_name_does_not_invent_one(self):
        info = format_server_information(
            {"name": "TVH", "url": "http://example.invalid"},
            {"sw_version": "4.3", "api_version": 19},
        )
        self.assertIn("Software: Not reported", info)
        self.assertIn("Server Name: TVH", info)


class PlaybackStatusTests(unittest.TestCase):
    def setUp(self):
        self.status = PlaybackStatus()

    def test_initial_ready(self):
        self.assertEqual(self.status.visible_text, "Ready")

    def test_playing_channel_is_persistent(self):
        self.status.start_playback("Chefi.ro HD")
        self.assertEqual(self.status.visible_text, "Playing: Chefi.ro HD")
        self.assertEqual(self.status.persistent_text, "Playing: Chefi.ro HD")

    def test_record_action_is_temporary(self):
        self.status.start_playback("Chefi.ro HD")
        self.status.notify("Recording started")
        self.assertEqual(self.status.visible_text, "Recording started")
        self.status.restore()
        self.assertEqual(self.status.visible_text, "Playing: Chefi.ro HD")

    def test_no_recording_to_stop_is_temporary(self):
        self.status.start_playback("BBC First HD")
        self.status.notify("No active recordings to stop")
        self.status.restore()
        self.assertEqual(self.status.visible_text, "Playing: BBC First HD")

    def test_fullscreen_restoration_keeps_playing_channel(self):
        self.status.start_playback("TVR 1 HD")
        self.status.notify("Temporary action")
        self.status.restore()
        self.assertEqual(self.status.visible_text, "Playing: TVR 1 HD")

    def test_switch_channel_changes_persistent_status(self):
        self.status.start_playback("BBC First HD")
        self.status.notify("Starting recording")
        self.status.start_playback("PRO TV HD")
        self.assertEqual(self.status.visible_text, "Playing: PRO TV HD")

    def test_stop_playback_clears_channel(self):
        self.status.start_playback("BBC First HD")
        self.status.stop_playback()
        self.status.notify("Playback stopped")
        self.assertEqual(self.status.visible_text, "Playback stopped")
        self.status.restore()
        self.assertEqual(self.status.visible_text, "Ready")

    def test_no_stream_restores_ready(self):
        self.status.notify("Channels loaded successfully")
        self.status.restore()
        self.assertEqual(self.status.visible_text, "Ready")


if __name__ == "__main__":
    unittest.main()
