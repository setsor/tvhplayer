# Ventura Intel MPV LAB DMG smoke build

This temporary branch triggers a macOS 13 Intel portable DMG build for testing the fixes for the MPV shutdown callback crash, radio artwork/first-frame display, and unavailable EPG text. The build is isolated from normal application settings.

The workflow must run regression tests, rebuild pinned MPV 0.40 from e48ac7ce08462f5e33af6ef9deeac6fa87eef01e, check Mach-O compatibility, and upload the DMG with its SHA-256 file.

Build attempt 2: enable Swift bridge/header generation required by MPV 0.40 Cocoa clipboard.
