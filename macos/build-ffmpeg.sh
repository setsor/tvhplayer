#!/bin/bash
# Rebuild the exact pinned FFmpeg release with the tested VideoToolbox patch.
set -euo pipefail

: "${CONDA_PREFIX:?Activate the native conda environment first}"
: "${RUNNER_TEMP:?RUNNER_TEMP is required}"
export MACOSX_DEPLOYMENT_TARGET=13.0
export SDKROOT="$(xcrun --sdk macosx --show-sdk-path)"
export PKG_CONFIG_PATH="$CONDA_PREFIX/lib/pkgconfig:$CONDA_PREFIX/share/pkgconfig"
export PKG_CONFIG_LIBDIR="$PKG_CONFIG_PATH"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PATCH="$ROOT/macos/patches/ffmpeg-9.1-videotoolbox-p4-rc1.patch"
WORK="$RUNNER_TEMP/ffmpeg-p4-rc1"
RESULTS="$RUNNER_TEMP/ventura-results"
mkdir -p "$WORK" "$RESULTS"

test "$(uname -m)" = x86_64
echo "1d15e432c2522808ac6a1942c2594db6abc44ca4ad789bd28f4fb94e407a5553  $PATCH" | shasum -a 256 -c -
"$CONDA_PREFIX/bin/ffmpeg" -version > "$RESULTS/ffmpeg-original-version.txt"
micromamba list --explicit > "$RESULTS/native-conda-before-rebuild.txt"

# Recover the actual rendered recipe of the binary being replaced, rather
# than assuming the current feedstock main branch matches that binary.
URL="$(python - "$RESULTS/native-conda-before-rebuild.txt" <<'PY'
import re, sys
from pathlib import Path
lines = Path(sys.argv[1]).read_text().splitlines()
matches = [x.split("#", 1)[0] for x in lines if re.search(
    r"/osx-64/ffmpeg-9\.1\.0-gpl_h5b0e0b6_100\.conda(?:#.*)?$", x)]
assert len(matches) == 1, matches
print(matches[0])
PY
)"
curl --fail --location --retry 3 "$URL" -o "$WORK/original.conda"
python - "$WORK" <<'PY'
import sys, zipfile
from pathlib import Path
work = Path(sys.argv[1])
with zipfile.ZipFile(work / "original.conda") as z:
    members = [n for n in z.namelist() if n.startswith("info-") and n.endswith(".tar.zst")]
    assert len(members) == 1, members
    (work / "info.tar.zst").write_bytes(z.read(members[0]))
PY
mkdir -p "$WORK/package-info"
zstd -dc "$WORK/info.tar.zst" | tar -xf - -C "$WORK/package-info"
RECIPE="$WORK/package-info/info/recipe"
test -f "$RECIPE/meta.yaml"
cp "$RECIPE/meta.yaml" "$RESULTS/ffmpeg-rendered-recipe.yaml"

curl --fail --location --retry 3 https://ffmpeg.org/releases/ffmpeg-9.1.tar.gz -o "$WORK/ffmpeg-9.1.tar.gz"
echo "a7a5c7219a9232e2017f7584922b50e96c1d6d7b55737184f94e394a229d13c7  $WORK/ffmpeg-9.1.tar.gz" | shasum -a 256 -c -
tar -xzf "$WORK/ffmpeg-9.1.tar.gz" -C "$WORK"
SRC="$WORK/ffmpeg-9.1"

python - "$RECIPE" "$SRC" "$PATCH" "$RESULTS" <<'PY'
import sys, subprocess
from pathlib import Path
import yaml
recipe, src, patch, results = map(Path, sys.argv[1:])
meta = yaml.safe_load((recipe / "meta.yaml").read_text())
source = meta["source"]
if isinstance(source, list):
    assert len(source) == 1, source
    source = source[0]
assert source["sha256"] == "a7a5c7219a9232e2017f7584922b50e96c1d6d7b55737184f94e394a229d13c7"
patches = source.get("patches")
assert isinstance(patches, list) and patches, "Missing rendered conda-forge patch list"
applied = []
for name in patches:
    path = recipe / name
    assert path.is_file(), path
    subprocess.run(["git", "apply", "--check", str(path)], cwd=src, check=True)
    subprocess.run(["git", "apply", str(path)], cwd=src, check=True)
    applied.append(name)
subprocess.run(["git", "apply", "--check", str(patch)], cwd=src, check=True)
subprocess.run(["git", "apply", str(patch)], cwd=src, check=True)
applied.append(patch.name)
(results / "ffmpeg-applied-patches.txt").write_text("\n".join(applied) + "\n")
# Match the macOS workaround in the conda-forge build script.
configure = src / "configure"
configure.write_text(configure.read_text().replace("-Wl,-single_module", ""))
PY

# Preserve the original feature flags and use the active prefix's headers/libs.
# The original compiler paths are from another build host and cannot be reused.
python - "$SRC" "$RESULTS" <<'PY'
import os, sys, shlex, subprocess
from pathlib import Path
src, results = map(Path, sys.argv[1:])
prefix = os.environ["CONDA_PREFIX"]
sdk = os.environ["SDKROOT"]
text = (results / "ffmpeg-original-version.txt").read_text()
line = next(x for x in text.splitlines() if x.startswith("configuration:"))
flags = shlex.split(line.split(":", 1)[1])
replace = {"--prefix", "--cc", "--cxx", "--nm", "--ar", "--pkg-config",
           "--extra-cflags", "--extra-cxxflags", "--extra-ldflags",
           "--sysroot", "--arch", "--target-os", "--install-name-dir", "--extra-version"}
flags = [f for f in flags if f.split("=",1)[0] not in replace]
assert "--enable-shared" in flags and "--disable-static" in flags
assert "--enable-videotoolbox" in flags and "--enable-gpl" in flags
def xcrun(name):
    return subprocess.check_output(["xcrun","--find",name], text=True).strip()
common = f"-isysroot {sdk} -mmacosx-version-min=13.0"
cmd = ["./configure", *flags,
       f"--prefix={prefix}", f"--cc={xcrun('clang')}", f"--cxx={xcrun('clang++')}",
       f"--nm={xcrun('nm')}", f"--ar={xcrun('ar')}",
       f"--pkg-config={prefix}/bin/pkg-config",
       "--arch=x86_64", "--target-os=darwin", f"--sysroot={sdk}",
       f"--extra-cflags={common} -I{prefix}/include",
       f"--extra-cxxflags={common} -I{prefix}/include",
       f"--extra-ldflags={common} -L{prefix}/lib -Wl,-rpath,{prefix}/lib",
       "--install-name-dir=@rpath", "--enable-rpath",
       "--extra-version=tvhplayer-p4-rc1"]
(results / "ffmpeg-configure-command.txt").write_text(shlex.join(cmd) + "\n")
subprocess.run(cmd, cwd=src, check=True)
PY

cd "$SRC"
make -j4 2>&1 | tee "$RESULTS/ffmpeg-build.log"
STAGE="$WORK/stage"
make install DESTDIR="$STAGE" 2>&1 | tee "$RESULTS/ffmpeg-install.log"

# Replace files atomically, without editing any hard-linked conda cache file.
python - "$STAGE$CONDA_PREFIX" "$CONDA_PREFIX" <<'PY'
import os, sys, shutil, tempfile
from pathlib import Path
stage, prefix = map(Path, sys.argv[1:])
assert (stage / "bin/ffmpeg").is_file()
for src in sorted(stage.rglob("*")):
    if src.is_dir() and not src.is_symlink():
        continue
    dst = prefix / src.relative_to(stage)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dst.parent) as temp:
        tmp = Path(temp) / dst.name
        if src.is_symlink():
            tmp.symlink_to(os.readlink(src))
        else:
            shutil.copy2(src, tmp)
        os.replace(tmp, dst)
PY
export DYLD_FALLBACK_LIBRARY_PATH="$CONDA_PREFIX/lib"
"$CONDA_PREFIX/bin/ffmpeg" -version | tee "$RESULTS/ffmpeg-p4-version.txt"
grep -q 'tvhplayer-p4-rc1' "$RESULTS/ffmpeg-p4-version.txt"
"$CONDA_PREFIX/bin/ffmpeg" -hide_banner -hwaccels | tee "$RESULTS/ffmpeg-p4-hwaccels.txt"
grep -qx videotoolbox "$RESULTS/ffmpeg-p4-hwaccels.txt"
test "$(pkg-config --modversion libavcodec)" = 63.24.100
test "$(pkg-config --modversion libavformat)" = 63.16.100
strings "$CONDA_PREFIX/lib/libavcodec.63.dylib" > "$WORK/libavcodec-strings.txt"
grep -q 'VT_P4_RC1: controlled H264 recovery' "$WORK/libavcodec-strings.txt"
otool -L "$CONDA_PREFIX/bin/ffmpeg" "$CONDA_PREFIX/lib/libavcodec.63.dylib" | tee "$RESULTS/ffmpeg-p4-linkage.txt"
