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


## Update Python and macOS dependencies

Do this on separate branches from UI changes. The Ventura Intel build currently uses Python 3.15.0 and the pins in `macos/requirements-build.txt`. Python 3.15.2 (25 October 2026) includes security fixes and is the first update to test.

- First PR: update **Python only**, from 3.15.0 to 3.15.2. Verify the official macOS installer and its SHA-256; update the active build workflow and `macos/BUILDING.md`. Leave the package versions and native MPV/FFmpeg unchanged so regressions are attributable to the Python update.
- Second PR: review the pinned packages individually. Candidates are `requests` 2.32.5 → 2.34.2 and `urllib3` 2.6.3 → 2.8.0. Test each change before pinning it. Keep `PyInstaller` 6.22.3 and `python-mpv` 1.0.8 unless there is a specific reason to move them.
- Keep `PyQt6` 6.10.2 on Ventura until a newer combination has been proven compatible. The PyQt6 6.12.0 macOS wheel is tagged for macOS 14+, even though its Qt runtime package has a lower minimum. Treat Pillow 13 as a separate major-version test; the current build accepts Pillow 12.x.
- Keep the existing MPV 0.41 build **without Cocoa** and the current FFmpeg toolchain while updating Python packages. Native library upgrades need their own build and playback tests.
- For every candidate: record the actual package versions in the build log, run `pip check` and the Qt/DVR tests, verify the MPEG-TS playback smoke test, then audit **every bundled Mach-O** with `macos/audit-native-minos.py` for macOS 13 compatibility. Check for unwanted Homebrew runtime links.
- Before publishing, test the DMG on a real Ventura Intel Mac: channel switching, EPG, DVB subtitles, live playback, local/server recording and stopping, network failure, and clean application exit. Keep the SHA-256 alongside the DMG.

Publish successful builds as previews first. Do not replace the verified Ventura release until the new build has passed the manual test.

## Player startup logo and EPG overlay

Keep this UI work separate from Python and dependency changes.

- First UI PR: show the TVHplayer logo before a channel is chosen; afterwards show that channel's logo (or its name if no image is available) while playback is idle or starting. Reuse the existing asynchronous logo loader and cache. Put the startup and tuner status directly below the channel logo.
- Second UI PR: after playback actually starts, show the current EPG title, start/end time, total duration and available description in a discreet overlay for **five seconds**. Read the existing `_now_next` data rather than blocking the interface with another request. Cancel the overlay when playback stops or another channel starts, and leave room for subtitles.
- Test rapid channel switching, delayed logos and EPG replies, missing EPG data, and fullscreen. A late response must never display another channel's information.
