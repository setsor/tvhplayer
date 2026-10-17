"""Tests for instant-recording EPG matching and TVHeadend DVR payloads."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tvhplayer"))
from recording_metadata import (
    current_epg_event,
    localized_text,
    recording_config,
)


class CurrentEPGTests(unittest.TestCase):
    channel = "0123456789abcdef0123456789abcdef"
    different_channel = "ffffffffffffffffffffffffffffffff"
    now = 1_800_000_000

    def event(self, **kw):
        return {
            "channelUuid": self.channel,
            "start": self.now - 60,
            "stop": self.now + 1200,
            "title": "Programul curent",
            "description": "Descrierea programului.",
            **kw,
        }

    def test_live_event_found(self):
        selected = current_epg_event([self.event()], self.channel, self.now)
        self.assertEqual(selected["title"], "Programul curent")

    def test_wrong_channel_is_never_selected(self):
        # TVHeadend can return all channels for an invalid channel filter.
        other = self.event(channelUuid=self.different_channel)
        self.assertIsNone(current_epg_event([other], self.channel, self.now))

    def test_ignores_events_outside_live_window(self):
        previous = self.event(start=self.now - 3600, stop=self.now - 1)
        future = self.event(start=self.now + 60, stop=self.now + 1800)
        self.assertIsNone(
            current_epg_event([previous, future], self.channel, self.now)
        )

    def test_selects_later_start_when_events_overlap(self):
        older = self.event(title="Older", start=self.now - 300)
        newer = self.event(title="Newer", start=self.now - 20)
        self.assertEqual(
            current_epg_event([older, newer], self.channel, self.now)["title"],
            "Newer",
        )

    def test_invalid_and_empty_epg_is_safe(self):
        self.assertIsNone(current_epg_event(None, self.channel, self.now))
        self.assertIsNone(current_epg_event([None, {}, {"title": "X"}], self.channel, self.now))

    def test_event_boundary(self):
        event = self.event(start=self.now - 20, stop=self.now)
        self.assertIsNone(current_epg_event([event], self.channel, self.now))


class RecordingConfigTests(unittest.TestCase):
    channel = "0123456789abcdef0123456789abcdef"
    start = 1_800_000_000
    stop = start + 1800

    def test_instant_keeps_user_duration_not_epg_interval(self):
        event = {
            "title": "Scandalos",
            "description": "Unity si Diana se infurie",
            "start": self.start - 900,
            "stop": self.start + 90,
        }
        conf = recording_config(
            self.channel, self.start, self.stop, event, instant=True
        )
        self.assertEqual(conf["start"], self.start)
        self.assertEqual(conf["stop"], self.stop)
        self.assertEqual(conf["stop"] - conf["start"], 1800)
        self.assertEqual(conf["title"], {"eng": "Scandalos"})
        self.assertEqual(conf["description"], {"eng": "Unity si Diana se infurie"})
        self.assertEqual(conf["comment"], "Instant recording via TVHplayer")
        self.assertNotIn("Recorded via TVHplayer", str(conf["description"]))

    def test_same_epg_metadata_for_instant_and_scheduled(self):
        event = {
            "title": {"ron": "Titlu românesc", "eng": "English title"},
            "description": {"ron": "Descriere românească"},
            "subtitle": {"ron": "Episodul 2"},
        }
        instant = recording_config(
            self.channel, self.start, self.stop, event, instant=True
        )
        scheduled = recording_config(
            self.channel, self.start, self.stop, event, instant=False
        )
        for field in ("title", "description", "subtitle"):
            self.assertEqual(instant[field], scheduled[field])
        self.assertEqual(scheduled["comment"], "Scheduled via TVHplayer")

    def test_summary_used_when_description_missing(self):
        event = {"title": "Documentar", "summary": "Rezumat din EPG"}
        conf = recording_config(
            self.channel, self.start, self.stop, event, instant=True
        )
        self.assertEqual(conf["description"], {"eng": "Rezumat din EPG"})

    def test_extratext_fallback(self):
        event = {"title": "News", "extraText": "Detalii suplimentare"}
        conf = recording_config(
            self.channel, self.start, self.stop, event, instant=True
        )
        self.assertEqual(conf["description"], {"eng": "Detalii suplimentare"})

    def test_no_epg_still_creates_valid_recording(self):
        conf = recording_config(
            self.channel, self.start, self.stop, None, instant=True
        )
        self.assertEqual(conf["title"], {"eng": "Instant Recording"})
        self.assertEqual(conf["comment"], "Instant recording via TVHplayer")
        self.assertEqual(conf["stop"], self.stop)
        self.assertEqual(conf["description"], {"eng": ""})

    def test_invalid_title_defaults(self):
        conf = recording_config(
            self.channel, self.start, self.stop, {"title": "   "}, instant=True
        )
        self.assertEqual(conf["title"], {"eng": "Instant Recording"})

    def test_scheduled_without_description_still_has_valid_structure(self):
        conf = recording_config(
            self.channel, self.start, self.stop,
            {"title": "Scheduled show"}, instant=False
        )
        self.assertEqual(conf["description"], {"eng": ""})

    def test_language_maps_preserved(self):
        self.assertEqual(
            localized_text({"ron": "  titlu  ", "eng": "  "}),
            {"ron": "titlu"},
        )
        self.assertEqual(localized_text(None), {})


if __name__ == "__main__":
    unittest.main()
