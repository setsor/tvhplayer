"""On-demand, redacted HTTP sniff for a TVHeadend playback URL.

Never log or expose the URL or the stream bytes: HTSP ticket and Basic credentials
may be part of the URL. A single short-lived request is issued only after mpv
fails to report START_FILE within the startup window on the macOS test package.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class StreamProbeResult:
    status: int
    media_type: str
    payload_type: str
    sample_bytes: int


def classify_stream_payload(content_type: str, payload: bytes) -> str:
    data = bytes(payload)
    mime = str(content_type).split(';', 1)[0].strip().lower()
    # MPEG-TS packets are 188 bytes; do not assume the first sampled byte aligns.
    if len(data) >= 377 and any(
        data[offset] == 0x47 and data[offset + 188] == 0x47 and data[offset + 376] == 0x47
        for offset in range(min(188, len(data) - 376))
    ):
        return 'mpeg-ts'
    if mime in ('text/html', 'application/xhtml+xml') or data.lstrip()[:32].lower().startswith((
        b'<!doctype html', b'<html',
    )):
        return 'html'
    if data and (mime in ('video/mp2t', 'video/mp4', 'application/octet-stream')):
        return 'media-unclassified'
    return 'empty' if not data else 'unexpected-payload'


def probe_http_stream(url: str, session=None) -> StreamProbeResult:
    """Inspect up to 752 bytes, then close subscription; no URL in result/log."""
    if session is None:
        import requests
        session = requests
    response = session.get(
        url, stream=True, allow_redirects=True,
        headers={'User-Agent': 'TVHplayer-Playback-Check'},
        timeout=(3, 5),
    )
    try:
        status = int(response.status_code)
        raw_type = str(response.headers.get('Content-Type', '')).split(';', 1)[0].strip().lower()
        media_type = re.sub('[^a-z0-9.+/-]', '', raw_type)[:64] or 'unspecified'
        data = response.raw.read(188 * 4)
        return StreamProbeResult(status, media_type, classify_stream_payload(raw_type, data), len(data))
    finally:
        response.close()
