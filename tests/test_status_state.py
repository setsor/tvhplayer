"""Regression tests for live playback + transient feedback + DVR state."""

import ast
import unittest
from pathlib import Path

from tvhplayer.core.status_state import StatusState, server_recording_count

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "tvhplayer" / "tvhplayer.py"


def gui_method(class_name, method_name):
    source = GUI.read_text(encoding="utf-8")
    tree = ast.parse(source)
    klass = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    method = next(
        node for node in klass.body
        if isinstance(node, ast.FunctionDef) and node.name == method_name
    )
    return ast.get_source_segment(source, method)


class StatusStateTests(unittest.TestCase):
    def test_start_and_finish_one_minute_recording(self):
        state = StatusState(playing_channel="TVR 1 HD")
        state.set_server_tasks([
            {"kind": "Server", "bucket": "recording", "title": "TVR 1"},
        ])
        self.assertEqual(state.playback_label, "Playing: TVR 1 HD")
        self.assertEqual(state.recording_label, "REC 1")
        state.set_server_tasks([{"kind": "Server", "bucket": "completed", "title": "TVR 1"}])
        self.assertEqual(state.playback_label, "Playing: TVR 1 HD")
        self.assertEqual(state.recording_label, "REC 0")
        self.assertFalse(state.has_active_recordings)

    def test_pro_tv_recording_remains_after_tvr1_finishes(self):
        state = StatusState(playing_channel="TVR 1 HD")
        state.set_server_tasks([
            {"kind": "Server", "bucket": "recording", "title": "PRO TV"},
            {"kind": "Server", "bucket": "recording", "title": "TVR 1"},
        ])
        self.assertEqual(state.recording_label, "REC 2")
        state.set_server_tasks([
            {"kind": "Server", "bucket": "recording", "title": "PRO TV"},
            {"kind": "Server", "bucket": "completed", "title": "TVR 1"},
        ])
        self.assertEqual(state.recording_label, "REC 1")
        self.assertTrue(state.has_active_recordings)

    def test_more_than_four_concurrent_streams_are_not_capped(self):
        tasks = [
            {"kind": "Server", "bucket": "recording"} for _ in range(6)
        ]
        self.assertEqual(server_recording_count(tasks), 6)

    def test_server_failure_is_unknown_not_zero(self):
        state = StatusState()
        state.set_server_tasks([{"kind": "Server", "bucket": "recording"}])
        state.set_server_tasks(None)
        self.assertEqual(state.recording_label, "REC ?")
        self.assertFalse(state.has_active_recordings)

    def test_local_and_server_recordings_are_distinct(self):
        state = StatusState(local_recording=True)
        state.set_server_tasks([{"kind": "Server", "bucket": "recording"}])
        self.assertEqual(state.recording_label, "REC 1 · LOCAL")
        state.set_server_tasks([])
        self.assertEqual(state.recording_label, "REC 0 · LOCAL")
        self.assertTrue(state.has_active_recordings)

    def test_no_playback_returns_ready(self):
        state = StatusState(playing_channel="TVR 1 HD")
        state.playing_channel = ""
        self.assertEqual(state.playback_label, "Ready")

    def test_only_running_server_jobs_are_counted(self):
        tasks = [
            {"kind": "Server", "bucket": "scheduled"},
            {"kind": "Local", "bucket": "recording"},
            {"kind": "Server", "bucket": "completed"},
            {"kind": "Server", "bucket": "recording"},
            {"kind": "Server", "bucket": "failed"},
        ]
        self.assertEqual(server_recording_count(tasks), 1)


class StatusWiringTests(unittest.TestCase):
    def test_no_show_message_monkeypatch(self):
        source = GUI.read_text(encoding="utf-8")
        self.assertNotIn("self.statusbar.showMessage =", source)
        self.assertNotIn("custom_show_message(", source)
        self.assertNotIn("self.statusbar.showMessage(", source)

    def test_short_messages_expire_without_overwriting_playback(self):
        method = gui_method("TVHeadendClient", "show_status")
        self.assertIn("self.status_notice_label", method)
        self.assertIn("self._status_notice_timer.start(", method)
        self.assertNotIn("self.status_label.setText(", method)
        expire = gui_method("TVHeadendClient", "_clear_status_notice")
        self.assertIn("self.status_notice_label.clear()", expire)
        self.assertNotIn("self.status_label", expire)

    def test_dvr_refresh_updates_badge_without_new_http_request(self):
        method = gui_method("TasksPanel", "refresh")
        self.assertIn("host.update_recording_activity(", method)
        self.assertIn("self._server_tasks if server_ok else None", method)
        self.assertIn("refresh_server=False", method)
        badge = gui_method("TVHeadendClient", "update_recording_activity")
        self.assertIn("self._status_state.set_server_tasks(", badge)
        self.assertNotIn("list_dvr_entries(", badge)

    def test_maintains_three_distinct_status_regions(self):
        source = GUI.read_text(encoding="utf-8")
        self.assertIn("self.status_label = QLabel", source)
        self.assertIn("self.status_notice_label = QLabel", source)
        self.assertIn("self.statusbar.addPermanentWidget(self.recording_indicator)", source)

    def test_playback_events_reconcile_live_label(self):
        for name in ("_on_playback_started", "_on_playback_failed", "stop_playback"):
            with self.subTest(event=name):
                self.assertIn(
                    "self._refresh_playback_status()",
                    gui_method("TVHeadendClient", name),
                )

    def test_reject_false_recording_state_from_start_notice(self):
        method = gui_method("TVHeadendClient", "start_recording")
        self.assertIn("self._refresh_tasks()", method)
        self.assertNotIn("self.start_recording_indicator()", method)


if __name__ == "__main__":
    unittest.main()
