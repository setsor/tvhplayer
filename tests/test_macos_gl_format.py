"""Check macOS-only OpenGL contract without opening a video window."""
from PyQt6.QtGui import QSurfaceFormat
from tvhplayer.video_widget import configure_macos_opengl


def test_macos_gl32_core_format():
    before = QSurfaceFormat.defaultFormat()
    try:
        configure_macos_opengl('darwin')
        actual = QSurfaceFormat.defaultFormat()
        assert (actual.majorVersion(), actual.minorVersion()) == (3, 2)
        assert actual.profile() == QSurfaceFormat.OpenGLContextProfile.CoreProfile
    finally:
        QSurfaceFormat.setDefaultFormat(before)


def test_non_macos_does_not_change_format():
    before = QSurfaceFormat.defaultFormat()
    assert configure_macos_opengl('linux') is None
    after = QSurfaceFormat.defaultFormat()
    assert (before.majorVersion(), before.minorVersion(), before.profile()) == (
        after.majorVersion(), after.minorVersion(), after.profile()
    )
