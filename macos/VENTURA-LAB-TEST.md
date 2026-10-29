# Ventura Intel MPV LAB DMG smoke build

This temporary branch triggers a macOS 13 Intel portable DMG build for testing the fixes for the MPV shutdown callback crash, radio artwork/first-frame display, and unavailable EPG text. The build is isolated from normal application settings.

The workflow must run regression tests, rebuild pinned MPV 0.40 from e48ac7ce08462f5e33af6ef9deeac6fa87eef01e, check Mach-O compatibility, and upload the DMG with its SHA-256 file.

Build attempt 2: enable Swift bridge/header generation required by MPV 0.40 Cocoa clipboard.

Build attempt 3: remove the unused Swift-dependent native clipboard bridge, preserve Cocoa/CoreFoundation in libmpv.

Build attempt 4: supply Swift-free Cocoa hook stubs for embedded Qt libmpv; compiled library must pass ctypes dlopen.

Build attempt 5: DMG creation and hdiutil verify passed (239 MB); fix SHA-256 verification working directory so artifact uploads.
