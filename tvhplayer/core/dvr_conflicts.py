"""DVR identity rules shared by the player, channel menu and EPG views.

Never use a channel name alone to decide two recording requests are duplicates:
different programmes on the same channel can be scheduled independently.
"""

from __future__ import annotations

from .models import is_quick_recording


def _int(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def entry_event_id(entry):
    """The broadcast id, if supplied by HTTP or HTSP DVR metadata."""
    raw = entry.raw or {}
    for key in ('broadcast', 'eventId', 'event_id'):
        value = _int(raw.get(key))
        if value is not None and value > 0:
            return value
    return None


def planned_stop(entry):
    """DVR end time, with raw timestamp preferred over derived duration."""
    raw_stop = _int((entry.raw or {}).get('stop'))
    return raw_stop if raw_stop and raw_stop > 0 else int(entry.start + entry.duration)


def programme_recording(entries, channel, event):
    """Find a running/upcoming entry representing *this* EPG programme.

    Exact broadcast IDs take priority. An older manual Quick Record lacks an
    EPG id, so associate it with the programme in which it was started.
    A different event id is authoritative even if broadcast times overlap.
    """
    if channel is None or event is None:
        return None

    wanted_id = _int(getattr(event, 'event_id', None))
    begin, end = int(event.start), int(event.stop)
    if end <= begin:
        return None

    for entry in entries or ():
        if entry.category() not in ('recording', 'upcoming'):
            continue
        if not entry.matches_channel(channel):
            continue

        event_id = entry_event_id(entry)
        if wanted_id is not None and event_id is not None:
            if wanted_id == event_id:
                return entry
            continue

        if is_quick_recording(entry):
            # Manual Quick Record: the TVH profile can add pre-roll, so allow
            # a two-minute margin before the programme's EPG start.
            if (begin - 120 <= entry.start < end
                    and planned_stop(entry) > begin):
                return entry
        elif (
            (entry.title or '').strip().casefold()
            == (getattr(event, 'title', '') or '').strip().casefold()
            and abs(entry.start - begin) <= 600
            and planned_stop(entry) > begin
        ):
            # Fallback for EPG timers whose server metadata lacks broadcast id.
            return entry
    return None


def other_running_recording(entries, channel):
    """Conservative fallback when there is no EPG: another DVR is active."""
    if channel is None:
        return None
    for entry in entries or ():
        if entry.category() == 'recording' and entry.matches_channel(channel):
            return entry
    return None
