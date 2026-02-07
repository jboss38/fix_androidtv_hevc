import subprocess
import json
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# ========= CONFIG =========
ROOT_DIR = Path(r"F:\Folder\With\videos")   # CHANGE THIS
FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"
MAX_WORKERS = 4  # Parallel processing (adjust based on CPU cores)
# ==========================


def get_file_info(path: Path):
    """
    Single ffprobe call to get all needed information:
    - Video stream details
    - Format tags (to check if already fixed)
    """
    cmd = [
        FFPROBE, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries",
        "stream=codec_name,pix_fmt,color_primaries,color_transfer,color_space:format_tags=FIXED_ANDROIDTV_HEVC",
        "-of", "json",
        str(path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        return None

    try:
        data = json.loads(result.stdout)
        stream = data.get("streams", [{}])[0]
        format_tags = data.get("format", {}).get("tags", {})
        
        return {
            "stream": stream,
            "already_fixed": format_tags.get("FIXED_ANDROIDTV_HEVC") == "1"
        }
    except (KeyError, json.JSONDecodeError, IndexError):
        return None


def is_hdr(stream):
    """Detect HDR content (must preserve color metadata)"""
    transfer = (stream.get("color_transfer") or "").lower()
    primaries = (stream.get("color_primaries") or "").lower()

    return (
        "smpte2084" in transfer or
        "arib-std-b67" in transfer or
        "bt2020" in primaries
    )


def needs_fix(info):
    """
    Determine if file needs fixing:
    - Must be HEVC 10-bit SDR with bt709
    - Must not already be fixed
    """
    if info["already_fixed"]:
        return False
    
    stream = info["stream"]
    
    return (
        stream.get("codec_name") == "hevc" and
        stream.get("pix_fmt") == "yuv420p10le" and
        stream.get("color_primaries") == "bt709" and
        not is_hdr(stream)
    )


def fix_file(path: Path):
    """
    Apply metadata fix:
    - Strip problematic color metadata
    - Add marker to prevent reprocessing
    - Atomic replacement (backup → temp → replace)
    """
    temp_file = path.with_suffix(".fixed.mkv")

    cmd = [
        FFMPEG, "-y", "-loglevel", "error",
        "-i", str(path),
        "-map", "0",
        "-c:v", "copy",
        "-color_primaries", "unspecified",
        "-color_trc", "unspecified",
        "-colorspace", "unspecified",
        "-c:a", "copy",
        "-c:s", "copy",
        "-metadata", "FIXED_ANDROIDTV_HEVC=1",
        str(temp_file)
    ]

    result = subprocess.run(cmd)

    if result.returncode == 0 and temp_file.exists():
        backup = path.with_suffix(".bak")
        path.rename(backup)
        temp_file.rename(path)
        backup.unlink()
        return True
    else:
        if temp_file.exists():
            temp_file.unlink()
        return False


def process_file(mkv: Path):
    """Process a single file (for parallel execution)"""
    info = get_file_info(mkv)
    
    if not info:
        return (mkv, "ffprobe_failed")
    
    if needs_fix(info):
        success = fix_file(mkv)
        return (mkv, "fixed" if success else "fix_failed")
    elif info["already_fixed"]:
        return (mkv, "already_fixed")
    else:
        return (mkv, "safe")


def main():
    if not ROOT_DIR.exists():
        print(f"❌ Root directory does not exist: {ROOT_DIR}")
        sys.exit(1)

    # Collect all MKV files
    mkv_files = list(ROOT_DIR.rglob("*.mkv"))
    total = len(mkv_files)
    
    if total == 0:
        print("No MKV files found.")
        return

    print(f"Found {total} MKV files. Starting analysis...\n")

    # Statistics
    stats = {
        "fixed": 0,
        "already_fixed": 0,
        "safe": 0,
        "fix_failed": 0,
        "ffprobe_failed": 0
    }

    # Process files (with optional parallel processing)
    if MAX_WORKERS > 1:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process_file, mkv): mkv for mkv in mkv_files}
            
            for i, future in enumerate(as_completed(futures), 1):
                mkv, status = future.result()
                stats[status] += 1
                
                # Status symbols
                symbols = {
                    "fixed": "✅ FIXED",
                    "already_fixed": "⏭️  SKIP (already fixed)",
                    "safe": "✅ SAFE",
                    "fix_failed": "❌ FIX FAILED",
                    "ffprobe_failed": "❌ PROBE FAILED"
                }
                
                print(f"[{i}/{total}] {symbols[status]}: {mkv.name}")
    else:
        # Sequential processing
        for i, mkv in enumerate(mkv_files, 1):
            mkv, status = process_file(mkv)
            stats[status] += 1
            
            symbols = {
                "fixed": "✅ FIXED",
                "already_fixed": "⏭️  SKIP (already fixed)",
                "safe": "✅ SAFE",
                "fix_failed": "❌ FIX FAILED",
                "ffprobe_failed": "❌ PROBE FAILED"
            }
            
            print(f"[{i}/{total}] {symbols[status]}: {mkv.name}")

    # Final summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total files:      {total}")
    print(f"Fixed:            {stats['fixed']}")
    print(f"Already fixed:    {stats['already_fixed']}")
    print(f"Safe (no action): {stats['safe']}")
    print(f"Fix failed:       {stats['fix_failed']}")
    print(f"Probe failed:     {stats['ffprobe_failed']}")
    print("="*60)


if __name__ == "__main__":
    main()
