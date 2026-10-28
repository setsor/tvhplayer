"""Offline regression tests for migrating working Qt5 macOS TVHplayer settings.

No network calls and no real user configuration files are accessed.
"""

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tvhplayer.core import config as cfg

# Preserve the real resolver before setUp patches it for legacy-migration tests.
_REAL_LEGACY_MACOS_CONFIG_PATH = cfg.legacy_macos_config_path


class MacOSMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.old = self.root / ".tvhplayer.conf"
        self.new = self.root / "Library" / "Application Support" / "TVHplayer" / "tvhplayer.conf"
        self.legacy_patch = patch.object(
            cfg, "legacy_macos_config_path", return_value=self.old
        )
        self.current_patch = patch.object(
            cfg, "default_config_path", return_value=self.new
        )
        self.legacy_patch.start()
        self.current_patch.start()
        self.addCleanup(self.legacy_patch.stop)
        self.addCleanup(self.current_patch.stop)

    def _legacy_settings(self):
        return {
            "volume": 31,
            "last_server": 0,
            "recording_path": "/tmp/recordings",
            "window_geometry": {"x": 50, "y": 60, "width": 1360, "height": 770},
            "servers": [
                {
                    "name": "existing-external-tvheadend",
                    "url": "https://tvh.invalid",
                    "username": "test-only-user",
                    "password": "test-only-password",
                }
            ],
        }

    def test_fresh_install_imports_legacy_and_keeps_original_untouched(self):
        self.old.write_text(json.dumps(self._legacy_settings()), encoding="utf-8")
        original = self.old.read_bytes()

        store = cfg.ConfigStore()
        self.assertEqual(store.servers[0]["name"], "existing-external-tvheadend")
        self.assertEqual(store.servers[0]["username"], "test-only-user")
        self.assertEqual(store.servers[0]["password"], "test-only-password")
        self.assertEqual(store.servers[0]["protocol"], "http")
        self.assertEqual(store.servers[0]["htsp_port"], 9982)
        self.assertEqual(store.data["volume"], 31)
        self.assertEqual(store.data["window_geometry"]["width"], 1360)
        self.assertTrue(self.new.is_file())
        self.assertEqual(self.old.read_bytes(), original)
        self.assertEqual(
            json.loads(self.new.read_text())["servers"][0]["password"],
            "test-only-password",
        )
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(self.new.stat().st_mode), 0o600)

    def test_current_config_is_preferred_and_never_overwritten_by_legacy(self):
        self.old.write_text(json.dumps(self._legacy_settings()), encoding="utf-8")
        self.new.parent.mkdir(parents=True)
        self.new.write_text(
            json.dumps({"volume": 72, "servers": [{"name": "new", "url": "http://localhost"}]}),
            encoding="utf-8",
        )
        before = self.new.read_bytes()
        store = cfg.ConfigStore()
        self.assertEqual(store.data["volume"], 72)
        self.assertEqual(store.servers[0]["name"], "new")
        self.assertEqual(self.new.read_bytes(), before)

    def test_corrupt_legacy_config_does_not_create_new_config(self):
        self.old.write_text("{not json", encoding="utf-8")
        store = cfg.ConfigStore()
        self.assertEqual(store.servers, [])
        self.assertFalse(self.new.exists())
        self.assertEqual(self.old.read_text(), "{not json")

    def test_explicit_test_path_does_not_import_legacy_config(self):
        self.old.write_text(json.dumps(self._legacy_settings()), encoding="utf-8")
        custom = self.root / "other.conf"
        store = cfg.ConfigStore(custom)
        self.assertFalse(custom.exists())
        self.assertEqual(store.servers, [])

    def test_isolated_test_build_does_not_import_legacy(self):
        self.old.write_text(json.dumps(self._legacy_settings()), encoding='utf-8')
        old_bytes = self.old.read_bytes()
        with patch.dict(os.environ, {'TVHPLAYER_CONFIG_DIR': str(self.root / 'lab')}):
            # setUp stubs default_config_path() to the normal user's path;
            # use its real implementation for this isolated-build test.
            with patch.object(cfg, 'default_config_path',
                              side_effect=lambda: cfg.default_config_dir() / 'tvhplayer.conf'), \
                    patch.object(cfg, 'legacy_macos_config_path',
                                 side_effect=_REAL_LEGACY_MACOS_CONFIG_PATH):
                store = cfg.ConfigStore()
        self.assertEqual(store.servers, [])
        self.assertFalse(self.new.exists())
        self.assertEqual(self.old.read_bytes(), old_bytes)

    def test_atomic_save_secures_existing_file(self):
        self.new.parent.mkdir(parents=True)
        self.new.write_text('{"servers":[]}', encoding="utf-8")
        if os.name != "nt":
            os.chmod(self.new, 0o644)
        store = cfg.ConfigStore()
        store.servers = [{"name": "external", "url": "http://localhost"}]
        store.save()
        self.assertEqual(json.loads(self.new.read_text())["servers"][0]["name"], "external")
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(self.new.stat().st_mode), 0o600)

    def test_new_ui_does_not_print_config_or_authenticated_stream_url(self):
        source = (Path(__file__).resolve().parents[1] / "tvhplayer" / "tvhplayer.py").read_text(encoding="utf-8")
        self.assertNotIn("Debug: Current config:", source)
        self.assertNotIn("Debug: Stream URL:", source)
        self.assertNotIn("self.logger.info(f\"{key}={value}\")", source)


if __name__ == "__main__":
    unittest.main()
