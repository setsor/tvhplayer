"""MPV playback artwork regression: TV -> audio-only radio -> TV."""

from types import SimpleNamespace
from unittest.mock import Mock

from tvhplayer.core.engine import ENGINE_MPV
from tvhplayer.core.mpv_player import MpvPlayer
from tvhplayer.tvhplayer import TVHeadendClient
from tvhplayer.video_widget import _new_video_picture


def test_mpvrender_requires_real_new_frame_not_redraw_or_repeat():
    assert _new_video_picture({'flags': 1}, True)
    assert not _new_video_picture({'flags': 0}, True)
    assert not _new_video_picture({'flags': 1 | 2}, True)   # redraw
    assert not _new_video_picture({'flags': 1 | 4}, True)   # repeated old frame
    assert not _new_video_picture(None, False)
    assert _new_video_picture(None, True)   # compatibility without frame_info


def test_audio_only_playback_does_not_have_a_decoded_video_track():
    player = object.__new__(MpvPlayer)
    player._mpv = SimpleNamespace(video_codec=None)
    assert not player.has_video()
    player._mpv.video_codec = 'H.264 / AVC'
    assert player.has_video()


def _window_stub():
    return SimpleNamespace(
        engine=ENGINE_MPV,
        _playback_active=False,
        _awaiting_playback=False,
        _splash_idle_timer=SimpleNamespace(stop=Mock()),
        _sync_play_button=Mock(),
        _set_idle_splash=Mock(),
        _set_channel_cover=Mock(),
    )


def test_audio_start_keeps_cover_until_actual_video_frame():
    win = _window_stub()
    # A radio station can report playback started without a picture.
    TVHeadendClient._protect_video_surface(win, True)
    assert win._playback_active
    win._set_idle_splash.assert_called_once_with(False)
    win._set_channel_cover.assert_not_called()

    # A signal from a previous channel must not remove the new cover.
    win._awaiting_playback = True
    TVHeadendClient._on_video_frame_presented(win)
    win._set_channel_cover.assert_not_called()

    # An actual frame from the newly playing TV channel removes it.
    win._awaiting_playback = False
    TVHeadendClient._on_video_frame_presented(win)
    win._set_channel_cover.assert_called_once_with(False)


def test_stop_hides_channel_cover_and_restores_idle_splash():
    win = _window_stub()
    TVHeadendClient._protect_video_surface(win, False)
    win._set_channel_cover.assert_called_once_with(False)
    win._set_idle_splash.assert_called_once_with(True)
