"""No extra recording must be created for the same broadcast."""

from tvhplayer.core.dvr_conflicts import (
    entry_event_id,
    other_running_recording,
    planned_stop,
    programme_recording,
)
from tvhplayer.core.models import Channel, DvrEntry, EpgEvent, QUICK_RECORD_COMMENT


def event(eid=101, start=1000, stop=1600, title='Programme A'):
    return EpgEvent(event_id=eid, start=start, stop=stop, title=title,
                    channel_uuid='one')


def entry(uuid='timer', *, start=970, stop=1600, title='Programme A',
          channel='one', broadcast=None, quick=False, state='recording'):
    raw = {'channel': channel, 'stop': stop,
           'comment': QUICK_RECORD_COMMENT if quick else 'Scheduled via TVHplayer'}
    if broadcast is not None:
        raw['broadcast'] = broadcast
    return DvrEntry(uuid=uuid, title=title, channel_name=channel,
                    start=start, duration=stop - start,
                    status='Running' if state == 'recording' else 'Scheduled',
                    sched_status=state, raw=raw)


def test_exact_broadcast_matches_quick_and_scheduled():
    channel = Channel(uuid='one', name='one')
    scheduled = entry(broadcast=101)
    quick = entry(uuid='quick', broadcast=101, quick=True)
    assert programme_recording([scheduled], channel, event()) is scheduled
    assert programme_recording([quick], channel, event()) is quick
    assert entry_event_id(quick) == 101


def test_other_epg_event_is_not_duplicate_even_with_overlapping_times():
    channel = Channel(uuid='one', name='one')
    previous = entry(broadcast=100, start=900, stop=1700)
    assert programme_recording([previous], channel, event()) is None
    next_event = event(eid=102, start=1600, stop=2200, title='Programme B')
    assert programme_recording([entry(broadcast=101)], channel, next_event) is None


def test_manual_quick_from_this_programme_blocks_duplicate_schedule():
    channel = Channel(uuid='one', name='one')
    manual = entry(uuid='quick', start=1250, stop=1900,
                   title='one 2026-11-07 11:15:00', quick=True)
    assert programme_recording([manual], channel, event()) is manual
    assert planned_stop(manual) == 1900


def test_quick_started_before_next_programme_does_not_block_it():
    channel = Channel(uuid='one', name='one')
    manual = entry(uuid='quick', start=1250, stop=2200, quick=True)
    future = event(eid=102, start=1600, stop=2200, title='Programme B')
    assert programme_recording([manual], channel, future) is None


def test_manual_quick_preroll_matches_start_of_programme():
    channel = Channel(uuid='one', name='one')
    quick = entry(start=950, stop=1450, quick=True)
    assert programme_recording([quick], channel, event()) is quick


def test_same_title_on_different_channel_is_independent():
    channel = Channel(uuid='one', name='one')
    duplicate_name = entry(channel='two', broadcast=101)
    assert programme_recording([duplicate_name], channel, event()) is None


def test_timers_without_epg_id_match_title_and_start_not_just_overlap():
    channel = Channel(uuid='one', name='one')
    timer = entry(start=970, stop=1630)
    assert programme_recording([timer], channel, event()) is timer
    assert programme_recording([timer], channel,
                               event(eid=999, title='Different')) is None


def test_finished_recording_does_not_block_new_dvr_request():
    channel = Channel(uuid='one', name='one')
    finished = entry(broadcast=101)
    finished.sched_status = 'completed'
    finished.status = 'Completed OK'
    assert programme_recording([finished], channel, event()) is None


def test_no_epg_blocks_only_running_jobs_on_same_channel():
    channel = Channel(uuid='one', name='one')
    running = entry()
    upcoming = entry(uuid='future', state='scheduled')
    assert other_running_recording([upcoming, running], channel) is running
    assert other_running_recording([upcoming], channel) is None
    assert other_running_recording([running], Channel(uuid='other', name='other')) is None
