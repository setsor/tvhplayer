"""PyInstaller startup hook for a strictly isolated TVHplayer mpv lab build.

This executes before the TVHplayer entry point: launching the .app from Finder
will not touch the validated installation's configuration, log or picon files.
Users can explicitly override individual paths in their environment.
"""
from __future__ import annotations

import os
from pathlib import Path

if os.name == "posix":
    home = Path.home()
    profile = home / "Library" / "Application Support" / "TVHplayer-MPV-LAB"
    defaults = {
        "TVHPLAYER_CONFIG_DIR": profile,
        "TVHPLAYER_CACHE_DIR": home / "Library" / "Caches" / "TVHplayer-MPV-LAB",
        "TVHPLAYER_LOG_DIR": home / "Library" / "Logs" / "TVHplayer-MPV-LAB",
        "TVHPLAYER_PICON_DIR": profile / "picons",
    }
    for name, folder in defaults.items():
        os.environ.setdefault(name, str(folder))
