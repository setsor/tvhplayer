# TVHplayer v4.1 fork — isolated Intel Ventura validation

This is an **experimental mpv build**. The existing validated TVHplayer
application and `setsor/tvhplayer:main` must remain unchanged.

## What the v4.1 release proves and does not prove

Upstream v4.1 bundles libmpv and FFmpeg in its macOS apps. The upstream Intel
workflow runs on macOS 15; its DMG is **not verified for macOS 13 Ventura**.
Passing tests on macOS 15 does not establish Mach-O binary compatibility or
stable playback on Ventura.

The v4.1 fork branch keeps the server subtitle defaults, serialized server
DVR Stop/Cancel and macOS legacy migration from the existing fork. These need
separate live regression tests.

## Build without touching the installed application

Use the existing checkout or GitHub source files for branch
`integration/upstream-v4.1-ventura`. Build **on Ventura 13 Intel** with a
compatible Python 3.15, PyQt6 and libmpv stack. Current Homebrew support
for Ventura is limited, so `brew install mpv` may not be available;
building or supplying a Ventura-compatible native libmpv is a prerequisite,
not an assumed success.

The v4.1 build script accepts separate app and bundle identifiers:

```sh
export TVHPLAYER_APP_NAME=TVHplayer-Ventura-MPV-LAB
export TVHPLAYER_BUNDLE_ID=io.github.setsor.tvhplayer.ventura.lab
bash macos/build-macos.sh
```

Run the resulting app only with isolated configuration, cache, log and picon
directories (the latter two prevent writes to the validated app's data):

```sh
TVHPLAYER_CONFIG_DIR="$HOME/Library/Application Support/TVHplayer-MPV-LAB" \
TVHPLAYER_CACHE_DIR="$HOME/Library/Caches/TVHplayer-MPV-LAB" \
TVHPLAYER_LOG_DIR="$HOME/Library/Logs/TVHplayer-MPV-LAB" \
TVHPLAYER_PICON_DIR="$HOME/Library/Application Support/TVHplayer-MPV-LAB/picons" \
TVHPLAYER_ENGINE=mpv \
macos/dist/TVHplayer-Ventura-MPV-LAB.app/Contents/MacOS/TVHplayer-Ventura-MPV-LAB
```

An isolated configuration directory deliberately **does not auto-import**
`~/.tvhplayer.conf`. Re-add a test server manually; do not copy credentials
into public CI logs. The normal application still performs its one-time legacy
import when needed.

## Binary checks on Ventura

Confirm every Mach-O binary (including nested libraries) supports macOS 13,
rather than checking the main executable alone:

```sh
APP=macos/dist/TVHplayer-Ventura-MPV-LAB.app
find "$APP/Contents" -type f \( -name '*.dylib' -o -name '*.so' \) -print \
  | while IFS= read -r file; do
      echo "=== $file"
      otool -l "$file" | grep -A 4 -E 'LC_BUILD_VERSION|LC_VERSION_MIN_MACOSX' \
        | grep -E 'LC_BUILD_VERSION|LC_VERSION_MIN_MACOSX|minos|version' || true
    done
codesign --verify --deep --verbose=2 "$APP"
```

The build also checks for accidental links into Homebrew paths; run-time
loading still must be tested with the bundle on a clean Ventura installation.
Do not assume `MACOSX_DEPLOYMENT_TARGET=13` can lower already-compiled
native-library requirements.

## Required live checks

- Launch using bundled libmpv; verify the chosen engine in a redacted log
- Tune real HDHomeRun-backed DVB-C channels; verify video/audio and fullscreen
- Switch repeatedly; test stop then play and spontaneous stream errors
- Verify Romanian DVB subtitles default, delayed track discovery, manual Off,
  per-server remembrance and later channel changes
- Test server DVR Stop and Cancel with exact UUID; verify a timeout cannot
  cause an automatic repeated command
- Verify legacy migration **separately**, using fake files and never the
  installed app's actual configuration
- Verify local recording, MP4 finalization, wake/sleep behavior, and crash logs

Passing these tests does **not** prove mpv fixes any libVLC native deadlock;
the two media backends have different code paths and must be evaluated as
alternatives.
