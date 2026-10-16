"""Regression tests for macOS TVHplayer diagnostics and DVR classification."""

import contextlib
import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tvhplayer"))

from dvr_status import categorize_recording
from diagnostics import debug_print, redact


class DVRStatusTests(unittest.TestCase):
    def test_running(self):
        self.assertEqual(categorize_recording({"status": "Running", "sched_status": "recording"}), ("upcoming", "Recording"))

    def test_scheduled(self):
        self.assertEqual(categorize_recording({"status": "Scheduled", "sched_status": "scheduled"}), ("upcoming", "Scheduled"))

    def test_finished(self):
        self.assertEqual(categorize_recording({"status": "Completed OK", "sched_status": "completed"}), ("finished", "Completed"))

    def test_file_missing(self):
        self.assertEqual(categorize_recording({"status": "File missing", "sched_status": "completederror"}), ("failed", "File missing"))

    def test_time_missed(self):
        self.assertEqual(categorize_recording({"status": "Time missed", "sched_status": "completedrerecord"}), ("failed", "Time missed"))

    def test_recorded_with_errors(self):
        self.assertEqual(categorize_recording({"status": "Completed OK", "errors": 2}), ("failed", "Completed OK"))

    def test_explicit_error(self):
        self.assertEqual(categorize_recording({"status": "Failed", "error": "No input"}), ("failed", "No input"))

    def test_unknown_is_visible(self):
        section, detail = categorize_recording({"status": "Unknown future DVR state"})
        self.assertEqual(section, "failed")
        self.assertIn("Unknown future", detail)


class DiagnosticTests(unittest.TestCase):
    def test_url_credentials_redacted(self):
        actual = redact("Stream: http://tvh-user:test-secret@example.local/stream/channel")
        self.assertNotIn("tvh-user", actual)
        self.assertNotIn("test-secret", actual)
        self.assertIn("[credentials]@", actual)

    def test_dictionary_password_redacted(self):
        actual = redact("{'name': 'demo', 'password': 'test-secret'}")
        self.assertNotIn("test-secret", actual)

    def test_json_password_redacted(self):
        actual = redact('{"password": "test-secret", "port": 9981}')
        self.assertNotIn("test-secret", actual)

    def test_bearer_redacted(self):
        self.assertNotIn("example-token", redact("Bearer example-token"))

    def test_off_by_default(self):
        output = io.StringIO()
        with patch.dict(os.environ, {"TVHPLAYER_DEBUG": "0"}):
            with contextlib.redirect_stderr(output):
                debug_print("secret")
        self.assertEqual(output.getvalue(), "")

    def test_opt_in_and_redaction(self):
        output = io.StringIO()
        with patch.dict(os.environ, {"TVHPLAYER_DEBUG": "1"}):
            debug_print("http://user:test-secret@nas.local/", file=output)
        self.assertNotIn("test-secret", output.getvalue())
        self.assertIn("[credentials]", output.getvalue())


if __name__ == "__main__":
    unittest.main()
