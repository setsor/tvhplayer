# TODO

## TVHeadend unavailable: old server data and partial video frame

Reported on 31 October 2026 with TVHplayer 4.5.0 on macOS Ventura Intel (`5833e766`).

The Mac was outside the home network and could not reach TVHeadend. TVHplayer still displayed server information, and a partial video frame with artifacts appeared during a playback attempt. We have not established whether that frame came from a previous render or from incomplete stream data. The bundled MPV 0.41 is built without Cocoa.

Things to check:

- Start TVHplayer with the NAS unreachable. It should distinguish a configured server from a connected one. Keep the saved settings, channels and EPG, but make it clear when displayed information is no longer current.
- Start playback on the LAN, disconnect, then reconnect. Check the channel list and Server Status after failed requests. Relevant code: `fetch_channels()`, `_on_channels_failed()` and `ServerStatusDialog.update_status()` in `tvhplayer/tvhplayer.py`.
- Check what the video area shows after a failed start or interrupted stream. Follow `play_channel_by_data()`, `_on_playback_failed()` and `stop_playback()`, then `MpvPlayer._on_event()` and `MpvVideoWidget.paintGL()`. In particular, `PLAYBACK_RESTART` does not by itself prove that a new, valid video frame has been drawn.
- Check that delayed callbacks from an earlier stream cannot incorrectly mark a new attempt as playing. Cover channel changes, retry and network recovery with regression tests.

Keep network requests off the Qt UI thread. Do not clear the user's saved server settings, EPG or recordings when a connection fails. Leave TVHeadend, its MPEG-TS profiles and the validated Ventura DMG unchanged while investigating.

Test the behavior on Ventura Intel before releasing a fix.
