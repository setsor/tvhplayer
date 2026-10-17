# Building TVHplayer for Intel macOS

This is a reproducible development build for **Intel (x86_64) macOS**, using Python **3.15.0**, PyInstaller **6.22.3**, and VLC **3.0.24**. Homebrew is not required.

## Build locally

Install [Python 3.15.0](https://www.python.org/downloads/release/python-3150/) and [VLC 3.0.24 for Intel macOS](https://get.videolan.org/vlc/3.0.24/macosx/vlc-3.0.24-intel64.dmg). VLC must be installed in `/Applications/VLC.app`.

From the repository root:

```bash
/Library/Frameworks/Python.framework/Versions/3.15/bin/python3.15 -m venv macos/.venv315
source macos/.venv315/bin/activate
python -m pip install -r macos/requirements-build.txt
bash macos/build-macos.sh
```

The output is `macos/dist/TVHplayer.app`. To prepare a drag-and-drop disk image, run:

```bash
bash macos/package-dmg.sh
```

This generates `macos/dist/TVHplayer.dmg` and an accompanying `.sha256` manifest. The disk image contains the `.app`, an Applications shortcut and installation instructions.

**Installation note:** The bundle uses the standard application name `TVHplayer.app`. Dragging it into `/Applications` may replace an existing `TVHplayer.app`; back up the original first if you want to retain it. The DMG includes an Applications shortcut.

**Runtime dependency:** The generated `.app` bundles Python/Qt and VLC plugins, but does **not** bundle the native `libvlc.dylib` and `libvlccore.dylib`. VLC 3.0.24 must therefore remain installed at `/Applications/VLC.app` on the destination Mac. This is a development application bundle, not a self-contained VLC distribution.

Start it from Terminal to see diagnostic output:

```bash
./macos/dist/TVHplayer.app/Contents/MacOS/TVHplayer
```

## VLC plugin cache correction

VLC's `plugins.dat` cache records plugin file metadata. PyInstaller copies/signs plugins, changing file metadata. Including the source cache produces many `stale plugins cache: modified ...` startup messages.

`macos/build-macos.sh` stages the VLC plugins into a temporary folder using `rsync --exclude=plugins.dat`, then packages that folder. The script checks that no `plugins.dat` exists in the completed application. LibVLC discovers the bundled plugins at runtime.

Do not copy an existing `plugins.dat` into the completed bundle. The VLC installation itself is never modified by the local build.

## Build from GitHub Actions

The dedicated [Build TVHplayer (macOS Intel)](../.github/workflows/build-macos.yml) workflow runs on `macos-15-intel`. Because the Python 3.15 stable package may not be available through `actions/setup-python` yet, the workflow instead downloads and verifies the official Python 3.15.0 macOS installer. It also downloads and SHA-256-verifies the official VLC 3.0.24 Intel DMG.

After building and checking the bundle, GitHub Actions produces `TVHplayer.dmg`, its SHA-256 manifest, and a ZIP archive of the `.app`. All are attached to the workflow's downloadable artifact.

An explicitly marked `release(macos):` commit on the fork's `release/macos-intel-all-improvements` branch also publishes the verified DMG to [fork Releases](https://github.com/setsor/tvhplayer/releases), as a prerelease tied to the exact commit. Regular builds and pull requests do **not** publish releases. The workflow runs on pushes to the packaging branch and matching pull requests. Once the workflow is on the default branch, it can also be launched manually from GitHub's **Actions** tab.

Builds use ad-hoc signing, not Apple Developer ID signing/notarization. The CI runner uses macOS 15. The preceding combined-fixes GitHub-generated build was tested successfully on Intel macOS Ventura 13.7.8; the **new DMG revision** still requires an actual Mac launch/playback test.

The workflow packages the **exact branch/commit it runs on**. The fork's integration/release branch includes both the EPG scheduling and DVR Status fixes. A clean `main` build will not include those changes before they are merged.

The build also runs standard-library regression tests:

```bash
python -m unittest discover -s macos/tests -v
```

The `File missing` and `Time missed` DVR statuses are placed in the Failed tab. The status bar shows the currently playing channel as a persistent baseline, while action messages automatically expire after 4.5 seconds and fullscreen restores the channel display. Server Info distinguishes the locally configured server name from the HTTP API's software name. Diagnostic output is quiet by default. For redacted technical diagnostics, launch with `TVHPLAYER_DEBUG=1`; configuration dumps, stream URLs and raw server-response bodies are excluded, and passwords/URL credentials are masked.

## Notes

- The older multi-platform tag workflow is separate; the packaging PR only corrects invalid matrix artifact expressions and does not modernize those other platform builds.
- Local output is confined to `macos/build/` and `macos/dist/`; the installed VLC and TVHplayer applications are not overwritten.
- Application runtime logs may contain TVHeadend credentials. Never attach unredacted logs or `~/.tvhplayer.conf` to a public GitHub issue or PR.

## Preview distribution

An installation-ready development DMG is published as a **prerelease** in the
[fork's Releases page](https://github.com/setsor/tvhplayer/releases). Each
published prerelease uses a unique source-commit tag. The DMG includes an
Applications shortcut, is checksum-verified by GitHub Actions, and must be
installed alongside VLC 3.0.24 on Intel macOS. This release is not Apple-notarized.

## Concurrent TVHeadend recordings

The macOS status bar has three independent areas:

- **LIVE:** the currently playing channel (persistent, including after fullscreen).
- **Notice:** temporary feedback (automatically expires).
- **REC N:** the number of *server-side* active TVHeadend DVR entries, refreshed every 15 seconds without blocking the playback UI. Click to open the DVR Status dialog. The tooltip shows the channels and programme titles. **REC ?** indicates that the server status could not be retrieved; it never means there are zero recordings.

The old **Stop Recording** button no longer stops all currently running DVR entries. Instead, it opens **DVR Status → Upcoming/Current**. Select one row displaying **Recording** and click **Stop Selected Recording...**. The confirmation names its channel and programme, and only that entry's UUID is sent to `/api/dvr/entry/stop`. Scheduled entries cannot be stopped using this action. Other concurrent recordings continue.

TVHplayer does not limit recordings to three or four; a DVB-C tuner can service multiple subscriptions on the same multiplex. The **LOCAL REC** indicator refers to FFmpeg local-file recording and is separate from server DVR count.

Test selective Stop only on a disposable recording. This UI change must be manually verified on macOS Ventura before the updated DMG is published.
