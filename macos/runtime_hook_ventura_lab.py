"""Isolated Ventura LAB settings: installed builds cannot touch normal TVHplayer data."""
from pathlib import Path
import os

home = Path.home()
os.environ.setdefault(
    'TVHPLAYER_CONFIG_DIR',
    str(home / 'Library' / 'Application Support' / 'TVHplayer-MPV-LAB'),
)
os.environ.setdefault(
    'TVHPLAYER_CACHE_DIR',
    str(home / 'Library' / 'Caches' / 'TVHplayer-MPV-LAB'),
)
os.environ.setdefault(
    'TVHPLAYER_LOG_DIR',
    str(home / 'Library' / 'Logs' / 'TVHplayer-MPV-LAB'),
)
