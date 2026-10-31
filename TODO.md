# TODO

This file tracks deferred work in the fork. Keep implementation and validation separate from this list.

## Open — Offline TVHeadend connection state and stale playback surface

**Status:** Deferred for later investigation (reported 2026-10-31)  
**Priority:** Normal — investigate before changing playback internals  
**Affected build to inspect:** TVHplayer 4.5.0, macOS Ventura 13 Intel, commit `5833e7667731f79e076f8151d698b10b4e38b9ab`  
**Stable release:** [Ventura 4.5.0 Intel](https://github.com/setsor/tvhplayer/releases/tag/ventura-4.5.0-intel-20261031)

### Report

TVHplayer was used while the Mac was connected to the Internet **outside the home LAN** and therefore could not access its LAN-only TVHeadend server. Saved server-related information remained visible. A partial picture containing visual artifacts was also observed.

This report does **not** establish that any buffered frames were persisted across launches, nor that the MPV Cocoa backend was enabled. The release's MPV 0.41 build still uses `-Dcocoa=disabled`, `-Dgl-cocoa=disabled`, and `-Dplain-gl=enabled`. A residual OpenGL frame, an incomplete stream, or a partially decoded frame should be distinguished through testing.

### Code paths to review (release/ventura-4.5.0-intel)

- `tvhplayer/tvhplayer.py`: `fetch_channels()`, `_on_channels_failed()`, `_clear_channels()`. A failed refresh on the same server deliberately preserves the previously loaded channel list. Determine how to label the displayed snapshot as stale/offline.
- `tvhplayer/tvhplayer.py`: `ServerStatusDialog.update_status()`. Verify that failed status queries do not leave old signal/subscription values looking current.
- `tvhplayer/tvhplayer.py`: `play_channel_by_data()`, `_show_playback_wait()`, `_on_playback_failed()`, `stop_playback()`. Review state changes, timeouts, and errors when a LAN-only stream is unreachable.
- `tvhplayer/core/mpv_player.py`: `play()`, `stop()`, `_on_event()`. Distinguish MPV's `PLAYBACK_RESTART` notification from evidence of a newly rendered, valid video frame.
- `tvhplayer/video_widget.py`: `MpvVideoWidget.paintGL()` and the render context lifecycle. Determine whether an old framebuffer or partially decoded frame is displayed on a failed start. Avoid unnecessary renderer reinitialization.

### Action items

- [ ] Reproduce with a **fresh application launch** outside the home LAN (without VPN).
- [ ] Reproduce a **network loss after successful playback** on the LAN, then reconnect.
- [ ] Check saved server configuration versus live connectivity status. The selected server should remain saved but must not imply a verified connection.
- [ ] Define explicit UI states such as Connecting / Connected / Disconnected, and mark retained channels/EPG/status data as last-known or stale on failure.
- [ ] Ensure a failed stream start/stop cannot leave an old picture presented as current playback; verify the Qt splash/overlay and MPV OpenGL surface behavior.
- [ ] Verify that late callbacks from a previous stream/server cannot mark a newer failed attempt as playing.
- [ ] Add regression tests for offline initial load, failed refresh, failed playback, stream switch, network recovery, and user-triggered retry.
- [ ] Retest manually on macOS Ventura 13 Intel before any DMG replacement.

### Constraints

Do not delete saved TVHeadend server settings, stored EPG, recording entries, or recordings as part of an offline/error UI reset. Do not change TVHeadend or MPEG-TS profiles, re-enable Cocoa, or alter the protected 4.5.0 release without evidence and a separately validated replacement. Keep all network operations off the Qt UI thread.

**Scope:** This is a tracking item only. No code change or diagnosis of the video's artifact source is claimed here.
