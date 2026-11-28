# Experimental Ventura Intel VideoToolbox recovery — P4-RC1

This branch is isolated from main and the existing Ventura integration. The patch is the exact locally tested file (SHA256 1d15e432c2522808ac6a1942c2594db6abc44ca4ad789bd28f4fb94e407a5553).

## Local hardware evidence
macOS 13.7.8 x86_64; FFmpeg 9.1 static standalone; Apple clang 14.0.3. P4-RC1 per-frame PSNR statistics identical to P3-R2 in four captures.

| Capture | Frames | HW errors | Restarts | Global PSNR |
| --- | ---: | ---: | ---: | ---: |
| Kanal D HD original | 1090 | 0 | 1 | 47.502420 |
| Kanal D HD rawcut | 846 | 4 | 1 | 43.635854 |
| PRO TV HD TVHeadend | 2688 | 4 | 0 | 68.493391 |
| PRO TV HD HDHomeRun | 2208 | 0 | 0 | 88.006016 |

Kanal D original baseline had 1347 decode errors, 543 restart attempts and 687 output frames. P2 without controlled restart produced green images (9.817046 dB). RC1 original minimum PSNR 41.825021 dB. PRO TV per-frame PSNR statistics also matched the unmodified baseline.

## Build
The dedicated workflow resolves the pinned conda-forge package, extracts its rendered recipe, verifies upstream and RC1 hashes, applies the package patches and RC1, rebuilds shared libraries with the original feature flags, and builds the same libmpv commit as the base integration. It retains the complete correctness, responsiveness, packaging and minimum OS checks. The package metadata still describes the original conda package; the archived rebuild logs, version suffix and compiled marker identify the replacement. CI on a VM does not validate physical VideoToolbox hardware.

## Limitations
Experimental only: one controlled restart per VT context, possible unnecessary restart after a harmless dropped field, incomplete-field handling and repeated recovery not yet validated, other codecs and progressive H.264 require regression tests. The patch does not establish the root cause of every TVHeadend or PRO TV artifact. Hardware testing of the resulting DMG is required before merge or upstream submission. No capture content is committed.
