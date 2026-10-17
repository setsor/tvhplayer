"""Normalize currently recording TVHeadend DVR entries.

Do not infer active recordings from tuners or from which app created them.
The DVR grid is the authoritative source. A UUID identifies an individual
recording even if its title or channel name is duplicated.
"""

try:
    from .dvr_status import categorize_recording
except ImportError:
    from dvr_status import categorize_recording


def active_recordings(entries):
    """Return all active DVR entries, sorted by start time, without a tuner cap."""
    result = []
    if not isinstance(entries, list):
        return result
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if categorize_recording(entry) != ("upcoming", "Recording"):
            continue

        uuid = entry.get("uuid")
        if not isinstance(uuid, str) or not uuid.strip():
            uuid = None

        channel = entry.get("channelname") or "Unknown channel"
        title = entry.get("disp_title") or entry.get("title") or "Untitled"
        if isinstance(title, dict):
            title = (title.get("eng") or title.get("ron")
                     or next(iter(title.values()), "Untitled"))
        try:
            start = int(entry.get("start") or 0)
        except (ValueError, TypeError):
            start = 0

        result.append({
            "uuid": uuid,
            "channel": str(channel),
            "title": str(title),
            "start": start,
        })

    result.sort(key=lambda item: (item["start"], item["channel"], item["title"]))
    return result


def stop_payload(recording):
    """Payload for *one* confirmed recording, never a group of recordings."""
    if not isinstance(recording, dict):
        raise ValueError("No recording selected")
    uuid = recording.get("uuid")
    if not isinstance(uuid, str) or not uuid.strip():
        raise ValueError("Selected recording has no UUID")
    return {"uuid": uuid}
