Edit file to change to your path

ROOT_DIR = Path(r"F:\Folder\With\videos") 


Python script for Windows.

Script Quick Description
Purpose: Automatically fixes HEVC 10-bit video files that won't play on Android TV due to problematic color metadata.
What It Does:

Scans all .mkv files in your library (recursively through subfolders)
Identifies files with the problematic pattern:

HEVC codec
10-bit color depth (yuv420p10le)
bt709 color metadata (triggers Android TV MediaCodec bug)
SDR content (not HDR)


Fixes affected files by:

Stripping problematic color metadata (-color_primaries unspecified)
Adding a marker tag so it won't reprocess the same file twice
No re-encoding — just remuxing (fast, no quality loss)


Reports progress and shows final statistics

Key Features:

✅ Fast: No re-encoding, just metadata cleanup (seconds per file)
✅ Safe: Atomic file replacement (creates backup, verifies success, then replaces)
✅ Idempotent: Won't reprocess files it's already fixed
✅ Smart: Skips HDR content and already-working files
✅ Parallel: Can process multiple files simultaneously (configurable)

Result: Videos that showed black screen at 0:00 on Android TV will now play correctly, while web players continue working as before.
