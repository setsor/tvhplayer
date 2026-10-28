"""Ensure Finder-launch mpv lab build isolates its persistent directories."""
from __future__ import annotations
import os
import pathlib
import sys
from unittest.mock import patch


def test_lab_runtime_hook_redirects_paths_without_touching_existing_settings(tmp_path):
    source = pathlib.Path(__file__).resolve().parents[1] / "macos" / "lab_runtime_hook.py"
    env = os.environ.copy()
    for variable in (
        "TVHPLAYER_CONFIG_DIR", "TVHPLAYER_CACHE_DIR",
        "TVHPLAYER_LOG_DIR", "TVHPLAYER_PICON_DIR",
    ):
        env.pop(variable, None)
    with patch.dict(os.environ, env, clear=True), patch("pathlib.Path.home", return_value=tmp_path):
        namespace = {"__name__": "__tvhplayer_lab_runtime_hook__"}
        exec(compile(source.read_text(encoding="utf-8"), str(source), "exec"), namespace)
        profile = tmp_path / "Library" / "Application Support" / "TVHplayer-MPV-LAB"
        assert pathlib.Path(os.environ["TVHPLAYER_CONFIG_DIR"]) == profile
        assert pathlib.Path(os.environ["TVHPLAYER_CACHE_DIR"]) == tmp_path / "Library" / "Caches" / "TVHplayer-MPV-LAB"
        assert pathlib.Path(os.environ["TVHPLAYER_LOG_DIR"]) == tmp_path / "Library" / "Logs" / "TVHplayer-MPV-LAB"
        assert pathlib.Path(os.environ["TVHPLAYER_PICON_DIR"]) == profile / "picons"


def test_lab_runtime_hook_respects_explicit_config_path(tmp_path):
    source = pathlib.Path(__file__).resolve().parents[1] / "macos" / "lab_runtime_hook.py"
    with patch.dict(os.environ, {"TVHPLAYER_CONFIG_DIR": str(tmp_path / "explicit")}, clear=False):
        exec(compile(source.read_text(encoding="utf-8"), str(source), "exec"), {"__name__": "__tvhplayer_lab_runtime_hook__"})
        assert os.environ["TVHPLAYER_CONFIG_DIR"] == str(tmp_path / "explicit")
