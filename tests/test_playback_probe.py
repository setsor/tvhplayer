"""HTTP classification without making live tuner/subscription requests."""
from io import BytesIO
from types import SimpleNamespace

from tvhplayer.core.playback_probe import classify_stream_payload, probe_http_stream


def _ts_packet():
    return bytes([0x47]) + bytes(187)


def test_ts_sync_detected_with_or_without_alignment():
    stream = _ts_packet() * 4
    assert classify_stream_payload('video/mp2t', stream) == 'mpeg-ts'
    assert classify_stream_payload('application/octet-stream', b'hello' + stream) == 'mpeg-ts'


def test_html_masquerading_as_successful_stream_detected():
    assert classify_stream_payload('text/html; charset=UTF-8', b'<!DOCTYPE html><html>login</html>') == 'html'
    assert classify_stream_payload('video/mp2t', b'<!doctype html>no stream') == 'html'


def test_empty_and_unexpected_payload_distinguished():
    assert classify_stream_payload('video/mp2t', b'') == 'empty'
    assert classify_stream_payload('text/plain', b'not a video') == 'unexpected-payload'


def test_redacted_probe_only_returns_safe_status_fields():
    class Response:
        status_code = 200
        headers = {'Content-Type': 'text/html; charset=UTF-8'}

        def __init__(self):
            self.raw = BytesIO(b'<!DOCTYPE html><html>login</html>')
            self.closed = False

        def close(self):
            self.closed = True

    response = Response()
    class Session:
        def get(self, url, **kwargs):
            assert 'PASSWORD_SHOULD_NOT_LEAK' in url
            assert kwargs['stream'] and kwargs['timeout'] == (3, 5)
            return response

    report = probe_http_stream(
        'http://user:PASSWORD_SHOULD_NOT_LEAK@tvh.example/stream?ticket=PRIVATE', session=Session()
    )
    assert report.status == 200
    assert report.media_type == 'text/html'
    assert report.payload_type == 'html'
    assert not any('PASSWORD' in str(field) for field in vars(report).values())
    assert response.closed
