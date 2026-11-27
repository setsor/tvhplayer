import ctypes
from types import SimpleNamespace

import pytest
from PyQt6.QtGui import QSurfaceFormat

from tvhplayer import video_widget
from tvhplayer.video_widget import (
    MpvVideoWidget, configure_macos_opengl, live_splitter_keeps_up, use_live_resize,
)


def test_paint_does_not_wait_for_mpv_presentation():
    rendered = []

    class DelayedPresentation:
        def render(self, **params):
            # A delayed VO must not hold Qt's paint call until presentation.
            assert params.get('block_for_target_time') is False
            rendered.append(params)

    widget = SimpleNamespace(
        _render_context=DelayedPresentation(),
        devicePixelRatioF=lambda: 2.0,
        width=lambda: 640,
        height=lambda: 360,
        defaultFramebufferObject=lambda: 7,
    )
    # Cover both the first frame and repaints caused by the spinner/resize.
    for _ in range(3):
        MpvVideoWidget.paintGL(widget)
    assert len(rendered) == 3
    assert rendered[0]['opengl_fbo'] == {'w': 1280, 'h': 720, 'fbo': 7}
    assert rendered[0]['flip_y'] is True


def test_live_splitter_keeps_up_from_qt_6_11():
    assert not live_splitter_keeps_up('6.10.2')
    assert not live_splitter_keeps_up('6.10.0')
    assert live_splitter_keeps_up('6.11.0')
    assert live_splitter_keeps_up('6.11.2')
    assert live_splitter_keeps_up('6.12.0')
    assert live_splitter_keeps_up('7.0.0')


def test_live_resize_follows_qt_until_chosen():
    assert not use_live_resize(None, '6.10.2')
    assert use_live_resize(None, '6.11.0')
    assert use_live_resize(True, '6.10.2')
    assert not use_live_resize(False, '6.11.0')


def test_release_keeps_native_callback_alive_until_render_context_is_freed():
    """The libmpv VO thread may still call the old ctypes closure on shutdown."""
    called = []

    class FakeContext:
        def __init__(self):
            self._callback = object()

        @property
        def update_cb(self):
            return self._callback

        @update_cb.setter
        def update_cb(self, new_value):
            raise AssertionError('Do not replace an active ctypes callback before free()')

        def free(self):
            assert self.update_cb is not None
            called.append('free')

    fake = SimpleNamespace(
        _render_context=FakeContext(),
        _wayland=None,
        makeCurrent=lambda: called.append('makeCurrent'),
        doneCurrent=lambda: called.append('doneCurrent'),
    )
    MpvVideoWidget.release(fake)
    assert called == ['makeCurrent', 'free', 'doneCurrent']
    assert fake._render_context is None


def test_macos_requests_core_profile_and_preserves_other_format_settings():
    original = QSurfaceFormat.defaultFormat()
    try:
        legacy = QSurfaceFormat(original)
        legacy.setVersion(2, 1)
        legacy.setProfile(QSurfaceFormat.OpenGLContextProfile.NoProfile)
        legacy.setDepthBufferSize(24)
        QSurfaceFormat.setDefaultFormat(legacy)
        requested = configure_macos_opengl('darwin')
        actual = QSurfaceFormat.defaultFormat()
        for fmt in (requested, actual):
            assert (fmt.majorVersion(), fmt.minorVersion()) == (3, 2)
            assert fmt.profile() == QSurfaceFormat.OpenGLContextProfile.CoreProfile
            assert fmt.depthBufferSize() == 24
    finally:
        QSurfaceFormat.setDefaultFormat(original)


@pytest.mark.parametrize('platform_name', ['linux', 'win32'])
def test_non_macos_does_not_change_opengl_format(platform_name):
    original = QSurfaceFormat.defaultFormat()
    assert configure_macos_opengl(platform_name) is None
    assert QSurfaceFormat.defaultFormat() == original


@pytest.mark.parametrize('codes, expected', [
    ([0], ((), True)),
    ([0x0500, 0x0502, 0], ((0x0500, 0x0502), True)),
])
def test_gl_error_drain_preserves_all_codes(codes, expected):
    assert video_widget._read_gl_errors(iter(codes).__next__) == expected


def test_gl_error_drain_is_bounded():
    calls = []

    def always_invalid():
        calls.append(True)
        return 0x0500

    assert video_widget._read_gl_errors(always_invalid) == ((0x0500,) * 16, False)
    assert len(calls) == 16


def test_gl_boundary_reports_missing_current_context(monkeypatch, capsys):
    monkeypatch.setattr(video_widget, '_proc_address', lambda name: 0)
    assert not video_widget._check_gl_boundary("before libmpv context initialization")
    assert "OpenGL boundary unavailable before libmpv" in capsys.readouterr().out


def test_macos_gl_boundary_records_incoming_errors_and_checks_outgoing_context(monkeypatch, capsys):
    calls = []
    codes = iter([0x0500, 0, 0])

    @ctypes.CFUNCTYPE(ctypes.c_uint)
    def get_error():
        calls.append("glGetError")
        return next(codes)

    def proc_address(name):
        assert name == b'glGetError'
        return ctypes.cast(get_error, ctypes.c_void_p).value

    renderer = SimpleNamespace(update_cb=None)

    def create_renderer(get_proc_address, wl_display):
        assert calls == ["glGetError", "glGetError"]
        assert wl_display is None
        calls.append("create renderer")
        return renderer

    monkeypatch.setattr(video_widget.sys, 'platform', 'darwin')
    monkeypatch.setattr(video_widget, '_proc_address', proc_address)
    widget = SimpleNamespace(
        _engine=SimpleNamespace(create_render_context=create_renderer),
        _render_context=None,
        _wayland=None,
        _frame_ready=SimpleNamespace(emit=lambda: None),
    )
    MpvVideoWidget._create_render_context(widget)
    assert calls == ["glGetError", "glGetError", "create renderer", "glGetError"]
    assert widget._render_context is renderer
    assert renderer.update_cb is widget._frame_ready.emit
    log = capsys.readouterr().out
    assert "OpenGL errors before libmpv context initialization: 0x0500 (recorded and cleared)" in log
    assert "OpenGL boundary clean after libmpv context initialization" in log
