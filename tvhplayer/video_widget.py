"""OpenGL video widget for the libmpv engine.

Qt owns the OpenGL context and keeps painting the widget; each paint asks mpv
to draw the current frame into the widget's framebuffer. Nothing is a native
window, so the splash, spinner and fullscreen bar can sit on top as plain widgets.
"""

from __future__ import annotations

import ctypes

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QOpenGLContext
from PyQt6.QtOpenGLWidgets import QOpenGLWidget

GL_COLOR_BUFFER_BIT = 0x4000
# mpv render.h: PRESENT denotes a queued frame; REDRAW and REPEAT are
# not a new picture and must not dismiss the channel-logo cover.
MPV_FRAME_PRESENT = 1
MPV_FRAME_REDRAW = 2
MPV_FRAME_REPEAT = 4


def _new_video_picture(frame_info, frame_update):
    """True only for an actual new mpv video frame, never a redraw."""
    if frame_info is not None:
        flags = int(frame_info.get('flags', 0))
        return bool(flags & MPV_FRAME_PRESENT) and not bool(flags & (MPV_FRAME_REDRAW | MPV_FRAME_REPEAT))
    # Older python-mpv bindings might not expose next_frame_info.
    return bool(frame_update)



class MpvVideoWidget(QOpenGLWidget):
    """The picture surface. ``MpvPlayer.attach()`` binds the engine to it."""

    # mpv reports a new frame from its own thread; the signal repaints on this one.
    _frame_ready = pyqtSignal()
    video_frame_presented = pyqtSignal()


    def __init__(self, parent=None):
        super().__init__(parent)
        self._engine = None
        self._render_context = None
        self._wayland = None
        self._awaiting_new_picture = False
        self._accept_new_picture = False
        self._frame_ready.connect(self.update, Qt.ConnectionType.QueuedConnection)

    def bind(self, engine):
        self._engine = engine
        if self.isValid():
            self.makeCurrent()
            self._create_render_context()
            self.doneCurrent()

    def begin_stream(self):
        """A different channel is starting; old video frames cannot reveal it."""
        self._awaiting_new_picture = True
        self._accept_new_picture = False

    def accept_new_picture(self):
        """A new stream is playing; reveal it after its own decoded frame is rendered."""
        self._accept_new_picture = True
        self.update()

    def platform_name(self):
        """Qt's windowing platform, e.g. "wayland" or "xcb" (X11 or XWayland)."""
        return QGuiApplication.platformName()

    def initializeGL(self):
        self.context().aboutToBeDestroyed.connect(self.release)
        self._create_render_context()

    def _create_render_context(self):
        if self._engine is None or self._render_context is not None:
            return
        if self._wayland is None and QGuiApplication.platformName() == 'wayland':
            self._wayland = _WaylandConnection()
        wl_display = self._wayland.display if self._wayland is not None else None
        context = self._engine.create_render_context(_proc_address, wl_display)
        context.update_cb = self._frame_ready.emit
        self._render_context = context

    def paintGL(self):
        if self._render_context is None:
            self._create_render_context()
        if self._render_context is None:
            gl = self.context().functions()
            gl.glClearColor(0.0, 0.0, 0.0, 1.0)
            gl.glClear(GL_COLOR_BUFFER_BIT)
            return
        # A mouse-triggered repaint can redraw the previous frame. Query the
        # renderer's actual next-frame flags before rendering instead.
        updated = self._render_context.update()
        try:
            frame_info = self._render_context.next_frame_info
        except (AttributeError, ValueError, RuntimeError):
            frame_info = None
        ratio = self.devicePixelRatioF()
        self._render_context.render(
            flip_y=True,
            opengl_fbo={
                'w': round(self.width() * ratio),
                'h': round(self.height() * ratio),
                'fbo': self.defaultFramebufferObject(),
            },
        )
        if (self._awaiting_new_picture and self._accept_new_picture
                and _new_video_picture(frame_info, updated)
                and self._engine is not None and self._engine.has_video()):
            self._awaiting_new_picture = False
            self.video_frame_presented.emit()

    def release(self):
        """Free the render context while its OpenGL context still exists."""
        context, self._render_context = self._render_context, None
        if context is not None:
            context.update_cb = None
            self.makeCurrent()
            context.free()
            self.doneCurrent()
        wayland, self._wayland = self._wayland, None
        if wayland is not None:
            wayland.close()


def _proc_address(name):
    context = QOpenGLContext.currentContext()
    if context is None:
        return 0
    address = context.getProcAddress(name)
    return int(address) if address else 0


class _WaylandConnection:
    """A connection to the compositor of our own, for mpv's VA-API.

    PyQt6 does not expose Qt's ``wl_display``. mpv uses the display only to
    open VA-API; frames still reach Qt's OpenGL context as dma-bufs.
    """

    def __init__(self):
        self.display = None
        try:
            self._lib = ctypes.CDLL('libwayland-client.so.0')
        except OSError as exc:
            print(f'Debug: No Wayland client library for mpv: {exc}')
            return
        self._lib.wl_display_connect.restype = ctypes.c_void_p
        self._lib.wl_display_connect.argtypes = [ctypes.c_char_p]
        self._lib.wl_display_disconnect.argtypes = [ctypes.c_void_p]
        self.display = self._lib.wl_display_connect(None)
        if not self.display:
            print('Debug: Could not connect to the Wayland display for mpv')

    def close(self):
        display, self.display = self.display, None
        if display:
            self._lib.wl_display_disconnect(display)
