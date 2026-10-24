"""Regression coverage: Qt must never request the X11 xcb plugin on macOS.

These tests are portable and do not need the Qt runtime. The macOS Actions
workflow additionally launches a smoke check in the actual PyInstaller .app.
"""

import ast
import unittest
from pathlib import Path

from tvhplayer.core.qt_platform import prepare_qt_platform


class QtPlatformTests(unittest.TestCase):
    def test_macos_ventura_uses_qt_default_cocoa(self):
        env = {}
        prepare_qt_platform(platform="darwin", environment=env)
        self.assertNotIn("QT_QPA_PLATFORM", env)

    def test_macos_preserves_user_platform_override(self):
        env = {"QT_QPA_PLATFORM": "offscreen"}
        prepare_qt_platform(platform="darwin", environment=env)
        self.assertEqual(env["QT_QPA_PLATFORM"], "offscreen")

    def test_linux_defaults_to_xcb_for_vlc3(self):
        env = {}
        prepare_qt_platform(platform="linux", environment=env)
        self.assertEqual(env["QT_QPA_PLATFORM"], "xcb")

    def test_linux_preserves_explicit_wayland_or_offscreen(self):
        for choice in ("wayland", "offscreen"):
            with self.subTest(choice=choice):
                env = {"QT_QPA_PLATFORM": choice}
                prepare_qt_platform(platform="linux", environment=env)
                self.assertEqual(env["QT_QPA_PLATFORM"], choice)

    def test_no_unconditional_xcb_setting_in_gui_entrypoint(self):
        gui = Path(__file__).resolve().parents[1] / "tvhplayer" / "tvhplayer.py"
        source = gui.read_text(encoding="utf-8")
        self.assertNotIn('os.environ.setdefault("QT_QPA_PLATFORM", "xcb")', source)
        self.assertIn("prepare_qt_platform()", source)
        ast.parse(source)

    def test_gui_has_pre_initialization_smoke_entrypoint(self):
        gui = Path(__file__).resolve().parents[1] / "tvhplayer" / "tvhplayer.py"
        source = gui.read_text(encoding="utf-8")
        self.assertIn("--tvhplayer-qt-smoke-test", source)
        self.assertLess(source.index("prepare_qt_platform()"), source.index("app = QApplication(args)"))
        self.assertIn('platform_name != "cocoa"', source)


if __name__ == "__main__":
    unittest.main()
