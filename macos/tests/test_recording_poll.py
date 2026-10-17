"""Offline network-poller tests: no real server or credentials."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tvhplayer"))

from recording_poll import RecordingPollWorker


class RecordingPollTests(unittest.TestCase):
    server = {"name": "test", "url": "http://tvh.invalid:9981"}

    def test_concurrent_recording_count_from_live_server_grid(self):
        entries = [
            {"uuid": str(i), "status": "Running", "sched_status": "recording",
             "channelname": f"Channel {i}", "disp_title": f"Show {i}", "start": i}
            for i in range(6)
        ]
        reply = Mock(status_code=200)
        reply.json.return_value = {"entries": entries}
        results = []
        worker = RecordingPollWorker(self.server)
        worker.signals.completed.connect(results.append)
        with patch("recording_poll.requests.get", return_value=reply) as get:
            worker.run()
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["success"])
        self.assertEqual(len(results[0]["recordings"]), 6)
        self.assertEqual(get.call_args.kwargs["timeout"], (2, 4))
        self.assertEqual(get.call_args.args[0], "http://tvh.invalid:9981/api/dvr/entry/grid")

    def test_server_error_does_not_falsely_report_zero_recordings(self):
        from requests.exceptions import Timeout
        worker = RecordingPollWorker(self.server)
        results = []
        worker.signals.completed.connect(results.append)
        with patch("recording_poll.requests.get", side_effect=Timeout("offline")):
            worker.run()
        self.assertFalse(results[0]["success"])
        # Qt renders REC ? rather than REC 0 when the server is unavailable.
        self.assertEqual(results[0]["recordings"], [])

    def test_server_auth_sent_in_auth_tuple_not_url(self):
        server = {**self.server, "username": "tester", "password": "example-only"}
        worker = RecordingPollWorker(server)
        worker.signals.completed.connect(lambda payload: None)
        reply = Mock(status_code=200)
        reply.json.return_value = {"entries": []}
        with patch("recording_poll.requests.get", return_value=reply) as get:
            worker.run()
        self.assertEqual(get.call_args.kwargs["auth"], ("tester", "example-only"))
        self.assertNotIn("example-only", get.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
