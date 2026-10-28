#!/usr/bin/env bash
# Rebuild only libmpv 0.40 for macOS Ventura with existing conda-forge deps.
# The conda-forge package disables cocoa, accidentally omitting utils-mac.c
# while CoreAudio still calls cfstr_from_cstr. Do not patch the application.
set -euo pipefail
PREFIX="$1"
[[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "x86_64" ]] || { echo "ERROR: Intel macOS required" >&2; exit 1; }
[[ -f "$PREFIX/lib/libmpv.2.dylib" ]] || { echo "ERROR: Missing conda libmpv" >&2; exit 1; }
WORK="${RUNNER_TEMP:?}/mpv-ventura-rebuild"
mkdir -p "$WORK"
ARCHIVE="$WORK/mpv-0.40.0.tar.gz"
curl --fail --location --retry 3 --retry-delay 2 --output "$ARCHIVE" \
  'https://github.com/mpv-player/mpv/archive/refs/tags/v0.40.0.tar.gz'
echo "10a0f4654f62140a6dd4d380dcf0bbdbdcf6e697556863dc499c296182f081a3  $ARCHIVE" | shasum -a 256 -c -
tar -xzf "$ARCHIVE" -C "$WORK"
SRC="$WORK/mpv-0.40.0"
python3 - "$SRC/meson.build" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
text = p.read_text(encoding="utf-8")
old = "                     'osdep/utils-mac.c',\n"
assert text.count(old) == 1, "Unexpected mpv Meson Cocoa source arrangement"
text = text.replace(old, "", 1)
anchor = "    timer_source = files('osdep/timer-darwin.c')\n"
assert text.count(anchor) == 1, "Unexpected Darwin source arrangement"
patched = (anchor +
           "    # Compile on Darwin even when the Cocoa UI is disabled: CoreAudio needs these symbols.\n"
           "    sources += files('osdep/utils-mac.c')\n"
           "    dependencies += dependency('appleframeworks', modules: 'CoreFoundation')\n")
text = text.replace(anchor, patched, 1)
p.write_text(text, encoding="utf-8")
print("Corrected mpv Meson sources: utils-mac.c and CoreFoundation")
PY
export MACOSX_DEPLOYMENT_TARGET=13.0
export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig"
export PKG_CONFIG_LIBDIR="$PREFIX/lib/pkgconfig"
export DYLD_FALLBACK_LIBRARY_PATH="$PREFIX/lib"
export CFLAGS="${CFLAGS:-} -mmacosx-version-min=13.0"
export OBJCFLAGS="${OBJCFLAGS:-} -mmacosx-version-min=13.0"
export LDFLAGS="${LDFLAGS:-} -mmacosx-version-min=13.0"
BUILD="$WORK/build"
echo "Configuring patched libmpv 0.40 with conda-forge FFmpeg 7.1..."
micromamba run -n mpv-native meson setup "$BUILD" "$SRC" \
  --prefix "$PREFIX" \
  -Dlibmpv=true -Dcplayer=false \
  -Dcocoa=disabled -Dswift-build=disabled -Dgl-cocoa=disabled \
  -Dmacos-11-3-features=disabled -Dmacos-11-features=disabled -Dmacos-12-features=disabled \
  -Dmanpage-build=disabled -Dhtml-build=disabled -Dzimg=disabled \
  -Dlibarchive=disabled -Dbuildtype=release
micromamba run -n mpv-native meson compile -C "$BUILD" -j 4
echo "Available freshly built mpv dylibs:"
find "$BUILD" -maxdepth 2 -name "libmpv*.dylib" -print
LIB="$BUILD/libmpv.2.dylib"
[[ -f "$LIB" ]] || { echo "ERROR: Expected patched libmpv.2.dylib not found" >&2; exit 1; }
cp "$LIB" "$PREFIX/lib/libmpv.2.dylib"
# The conda libmpv.dylib alias should refer to the corrected libmpv.2.dylib.
[[ ! -L "$PREFIX/lib/libmpv.dylib" ]] || readlink "$PREFIX/lib/libmpv.dylib"
echo "Checking that cfstr_from_cstr is no longer an undefined symbol..."
if nm -u "$PREFIX/lib/libmpv.2.dylib" | grep -E "(_cfstr_from_cstr|_cfstr_get_cstr)"; then
  echo "ERROR: Rebuilt library still has unresolved private mpv utility symbols" >&2
  exit 1
fi
PREFIX="$PREFIX" micromamba run -n mpv-native python -c \
  'import ctypes,os; ctypes.CDLL(os.environ["PREFIX"]+"/lib/libmpv.2.dylib"); print("Rebuilt libmpv native dlopen OK")'
echo "Patched libmpv rebuilt successfully for Ventura-targeted integration."
