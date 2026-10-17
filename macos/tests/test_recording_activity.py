"""Regression tests for concurrent DVR status and selective stopping."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tvhplayer"))

from recording_activity import active_recordings, stop_payload


class RecordingActivityTests(unittest.TestCase):
    def setUp(self):
        self.entries = [
            {"uuid": "uuid-1", "status": "Running", "sched_status": "recording",
             "channelname": "BBC First HD", "disp_title": "Crima in Paradis",
             "start": 100},
            {"uuid": "uuid-2", "status": "Running", "sched_status": "recording",
             "channelname": "Chefi.ro HD", "disp_title": "Hotel Portofino",
             "start": 110},
            {"uuid": "uuid-3", "status": "Recording", "sched_status": "recording",
             "channelname": "TVR 1 HD", "disp_title": "Stiri", "start": 120},
            {"uuid": "uuid-4", "status": "Running", "sched_status": "recording",
             "channelname": "TVR 2 HD", "disp_title": "Documentar",
             "start": 130},
            {"uuid": "future", "status": "Scheduled", "sched_status": "scheduled",
             "channelname": "TVR 3 HD", "disp_title": "Future", "start": 200},
            {"uuid": "done", "status": "Completed OK", "sched_status": "completed",
             "channelname": "TVR 3 HD", "disp_title": "Past", "start": 0},
            {"uuid": "lost", "status": "File missing", "sched_status": "completederror",
             "channelname": "TVR 3 HD", "disp_title": "Lost", "start": 0},
        ]

    def test_four_simultaneous_recordings_are_listed(self):
        active = active_recordings(self.entries)
        self.assertEqual(len(active), 4)
        self.assertEqual([r["uuid"] for r in active], ["uuid-1", "uuid-2", "uuid-3", "uuid-4"])

    def test_future_and_completed_not_in_active_list(self):
        self.assertNotIn("future", [r["uuid"] for r in active_recordings(self.entries)])
        self.assertNotIn("done", [r["uuid"] for r in active_recordings(self.entries)])
        self.assertNotIn("lost", [r["uuid"] for r in active_recordings(self.entries)])

    def test_duplicate_titles_are_distinguished_by_uuid(self):
        a = {"uuid": "first", "status": "Running", "sched_status": "recording",
             "disp_title": "Same Title", "channelname": "TVR 1 HD", "start": 1}
        b = dict(a, uuid="second", channelname="TVR 2 HD")
        active = active_recordings([a, b])
        self.assertEqual({r["uuid"] for r in active}, {"first", "second"})
        self.assertEqual(stop_payload(active[0]), {"uuid": "first"})

    def test_stop_payload_only_contains_selected_uuid(self):
        selected = active_recordings(self.entries)[2]
        self.assertEqual(stop_payload(selected), {"uuid": "uuid-3"})
        self.assertNotIn("uuid-1", str(stop_payload(selected)))

    def test_stop_without_uuid_is_rejected(self):
        for item in ({}, {"uuid": None}, {"uuid": " "}, None):
            with self.subTest(item=item):
                with self.assertRaises(ValueError):
                    stop_payload(item)

    def test_active_entry_without_uuid_is_counted_but_not_stoppable(self):
        active = active_recordings([{"status": "Running", "channelname": "BBC First HD"}])
        self.assertEqual(len(active), 1)
        self.assertIsNone(active[0]["uuid"])
        with self.assertRaises(ValueError):
            stop_payload(active[0])

    def test_malformed_grid_is_safe(self):
        self.assertEqual(active_recordings(None), [])
        self.assertEqual(active_recordings({}), [])
        self.assertEqual(active_recordings([None, False, 14]), [])

    def test_multilingual_title_fallback(self):
        a = {"uuid": "x", "status": "Running", "title": {"ron": "Film"}}
        self.assertEqual(active_recordings([a])[0]["title"], "Film")


if __name__ == "__main__":
    unittest.main()
