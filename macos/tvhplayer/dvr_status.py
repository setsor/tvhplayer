"""Small, dependency-free helpers for categorizing TVHeadend DVR entries.

Statuses are taken from /api/dvr/entry/grid. TVHeadend may report both
a human-facing `status` and a machine `sched_status`.
"""

def _nonzero(value):
    try:
        return int(value or 0) != 0
    except (TypeError, ValueError):
        return False


def categorize_recording(entry):
    """Return (section, display_status): upcoming, finished or failed."""
    status = str(entry.get("status") or "").strip()
    sched = str(entry.get("sched_status") or "").strip().lower()
    s = status.lower()

    if s in {"running", "recording"} or sched == "recording":
        return "upcoming", "Recording"

    if "scheduled" in s or sched in {"scheduled", "pending"}:
        return "upcoming", "Scheduled"

    # A missed/vanished recording must not be hidden by the generic
    # `completed` prefix, and errors must take priority over completion.
    failure_terms = (
        "file missing", "time missed", "failed", "invalid", "error",
        "aborted", "cancelled", "canceled", "no input", "no data",
        "missed", "tuner unavailable",
    )
    explicitly_failed = (
        any(term in s for term in failure_terms)
        or sched in {"completederror", "completedrerecord", "missed", "invalid"}
    )
    # "Completed OK" remains Finished even if TVHeadend reports
    # non-fatal stream errors. The server's explicit status takes priority.
    is_failure = explicitly_failed or (
        s not in {"completed ok", "finished"}
        and (_nonzero(entry.get("errors")) or _nonzero(entry.get("errorcode")))
    )
    if is_failure:
        error_text = entry.get("error")
        if isinstance(error_text, str) and error_text.strip():
            detail = error_text.strip()
        elif status:
            detail = status
        elif _nonzero(entry.get("errorcode")):
            detail = f"Error code: {entry['errorcode']}"
        elif _nonzero(entry.get("errors")):
            detail = f"Recording reported {entry['errors']} error(s)"
        else:
            detail = f"Recording failed ({sched or 'unknown reason'})"
        return "failed", detail

    if "completed" in s or s == "finished" or sched == "completed":
        return "finished", "Completed"

    # Preserve an unrecognised entry in Failed instead of silently dropping it.
    return "failed", f"Unrecognized DVR status: {status or sched or 'unknown'}"
