"""EPG-based metadata for instant and scheduled TVHeadend DVR recordings.

Keep the recording interval independent from EPG metadata. An instant recording
must always keep the user-selected duration, including when an EPG event ends.
"""


def localized_text(value):
    """Convert EPG string/multilingual values into the DVR API's language map."""
    if isinstance(value, dict):
        return {
            language: text.strip()
            for language, text in value.items()
            if isinstance(language, str)
            and isinstance(text, str)
            and text.strip()
        }
    if isinstance(value, str) and value.strip():
        return {"eng": value.strip()}
    return {}


def current_epg_event(entries, channel_uuid, when):
    """Select a current programme on exactly the requested channel, or None.

    Verify both the channel UUID and broadcast interval: TVHeadend can return
    events for every channel when an invalid channel filter is supplied.
    """
    matching = []
    for event in entries if isinstance(entries, list) else []:
        if not isinstance(event, dict):
            continue
        if event.get("channelUuid") != channel_uuid:
            continue
        if not localized_text(event.get("title")):
            continue
        try:
            start = int(event["start"])
            stop = int(event["stop"])
        except (KeyError, TypeError, ValueError):
            continue
        if start <= when < stop:
            matching.append((start, event))
    return max(matching, key=lambda item: item[0])[1] if matching else None


def recording_config(channel_uuid, start, stop, event=None, *, instant=False):
    """Build the common TVHeadend /api/dvr/entry/create conf payload."""
    if not isinstance(event, dict):
        event = {}

    default_title = "Instant Recording" if instant else "Scheduled Recording"
    title = localized_text(event.get("title")) or {"eng": default_title}

    # EPG sources may return description, summary, or extraText. Preserve
    # whichever descriptive field is actually present, without inventing text.
    description = (
        localized_text(event.get("description"))
        or localized_text(event.get("summary"))
        or localized_text(event.get("extraText"))
    )

    conf = {
        "start": int(start),
        "stop": int(stop),
        "channel": channel_uuid,
        "title": title,
        "description": description or {"eng": ""},
        "comment": (
            "Instant recording via TVHplayer"
            if instant else "Scheduled via TVHplayer"
        ),
    }

    subtitle = localized_text(event.get("subtitle"))
    if subtitle:
        conf["subtitle"] = subtitle
    return conf
