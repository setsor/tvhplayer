"""Regression tests for the channel-list Now/Next background refresh."""

from tvhplayer.core.channel_info import NowNext
from tvhplayer.core.models import Channel
from tvhplayer.tvhplayer import NowNextFetch


def test_background_now_next_refresh_uses_current_htsp_event_ids():
    """Old event IDs in the displayed rows must not be queried again."""
    old = Channel.from_raw({
        'channelId': 42, 'channelIdStr': 'channel', 'channelName': 'Channel',
        'eventId': 100, 'nextEventId': 101,
    })
    fresh = Channel.from_raw({
        'channelId': 42, 'channelIdStr': 'channel', 'channelName': 'Channel',
        'eventId': 200, 'nextEventId': 201,
    })
    result = {'channel': NowNext()}
    calls = []

    class Backend:
        def get_channels(self):
            calls.append('get_channels')
            return [fresh]

        def get_now_next(self, channels):
            calls.append(('get_now_next', channels[0].raw['eventId']))
            assert channels == [fresh]
            return result

        def close(self):
            calls.append('close')

    fetch = NowNextFetch(
        {'url': 'http://localhost:9981'}, [old],
        open_backend=lambda _: Backend(),
    )
    completed = []
    fetch.done.connect(lambda key, data: completed.append((key, data)))

    # Run synchronously to inspect this worker without starting its thread.
    fetch._run()

    assert calls == ['get_channels', ('get_now_next', 200), 'close']
    assert completed == [('http://localhost:9981', result)]


def test_background_now_next_refresh_reports_failure_and_closes_connection():
    calls = []

    class Backend:
        def get_channels(self):
            raise RuntimeError('metadata unavailable')

        def get_now_next(self, channels):
            raise AssertionError('must not query events with old metadata')

        def close(self):
            calls.append('close')

    fetch = NowNextFetch(
        {'url': 'http://localhost:9981'}, [],
        open_backend=lambda _: Backend(),
    )
    completed = []
    fetch.done.connect(lambda key, data: completed.append(data))
    fetch._run()

    assert calls == ['close']
    assert completed == [None]
