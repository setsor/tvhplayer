"""Prepare the Qt windowing backend without breaking non-Linux platforms.

libVLC 3 currently embeds into an X11 child on Linux, so that platform
uses xcb as before. Intel macOS must use the default Cocoa plugin.
"""


def prepare_qt_platform(platform=None, environment=None):
    import os
    import sys

    if platform is None:
        platform = sys.platform
    if environment is None:
        environment = os.environ

    if platform.startswith("linux"):
        environment.setdefault("QT_QPA_PLATFORM", "xcb")
    # On macOS, never force xcb: it is a Linux/X11-only platform plugin.
    # Let Qt select the native cocoa plugin by default.
