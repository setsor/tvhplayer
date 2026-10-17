"""Offline network-poller tests: no real server or credentials."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tvhplayer"))

from recording_poll import RecordingPollWorker, RecordingStopWorker


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
        self.assertEqual(get.call_args.kwargs["params"], {"start": 0, "limit": 500})
        self.assertEqual(results[0]["entries"], entries)

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



class RecordingStopTests(unittest.TestCase):
    server = {"name": "test", "url": "http://tvh.invalid:9981"}

    def test_only_one_uuid_posted_for_selected_recording(self):
        worker = RecordingStopWorker(self.server, {"uuid": "selected-uuid"})
        results = []
        worker.signals.completed.connect(results.append)
        reply = Mock(status_code=200)
        with patch("recording_poll.requests.post", return_value=reply) as post:
            worker.run()
        self.assertEqual(post.call_count, 1)
        self.assertEqual(
            post.call_args.args[0], "http://tvh.invalid:9981/api/dvr/entry/stop"
        )
        self.assertEqual(post.call_args.kwargs["data"], {"uuid": "selected-uuid"})
        self.assertEqual(post.call_args.kwargs["timeout"], (2, 7))
        self.assertEqual(results[0]["outcome"], "accepted")
        self.assertEqual(results[0]["http_status"], 200)

    def test_non_200_is_rejected_without_retries(self):
        worker = RecordingStopWorker(self.server, {"uuid": "selected-uuid"})
        results = []
        worker.signals.completed.connect(results.append)
        with patch(
            "recording_poll.requests.post", return_value=Mock(status_code=403)
        ) as post:
            worker.run()
        self.assertEqual(post.call_count, 1)
        self.assertEqual(results[0]["outcome"], "rejected")
        self.assertEqual(results[0]["http_status"], 403)

    def test_timeout_has_unknown_result_and_never_retries(self):
        from requests.exceptions import ReadTimeout
        worker = RecordingStopWorker(self.server, {"uuid": "selected-uuid"})
        results = []
        worker.signals.completed.connect(results.append)
        with patch(
            "recording_poll.requests.post",
            side_effect=ReadTimeout("No response from server")
        ) as post:
            worker.run()
        self.assertEqual(post.call_count, 1)
        self.assertEqual(results[0]["outcome"], "unknown")
        self.assertIsNone(results[0]["http_status"])

    def test_stop_uuid_required(self):
        with self.assertRaises(ValueError):
            RecordingStopWorker(self.server, {"uuid": None})

    def test_auth_not_embedded_in_stop_url_or_result(self):
        server = dict(self.server, username="example", password="not-a-real-secret")
        worker = RecordingStopWorker(server, {"uuid": "selected"})
        results = []
        worker.signals.completed.connect(results.append)
        with patch(
            "recording_poll.requests.post", return_value=Mock(status_code=200)
        ) as post:
            worker.run()
        self.assertEqual(
            post.call_args.kwargs["auth"], ("example", "not-a-real-secret")
        )
        self.assertNotIn("not-a-real-secret", post.call_args.args[0])
        self.assertNotIn("not-a-real-secret", repr(results))


if __name__ == "__main__":
    unittest.main()
