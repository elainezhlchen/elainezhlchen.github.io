#!/usr/bin/env python3
"""
Lecture Video Editor
====================
Removes filler words (um, uh) and long pauses from each lecture video.

How it works:
  1. Runs Whisper with --word_timestamps True on the audio → gets exact
     start/end time of every spoken word.
  2. Marks filler words and excess pause time for removal.
  3. Builds a "keep" list of time ranges that contain real speech.
  4. Uses ffmpeg to trim + stitch those ranges into a clean output video.

Requirements (already on your Mac from the transcription step):
  - Python 3 with openai-whisper  (pip3 install openai-whisper)
  - ffmpeg                        (brew install ffmpeg)

Usage:
  python3 edit_lectures.py

Output:
  /Users/elainesaiserver/dev/lecture-site-edited/
    lecture1_edited.mp4
    lecture2_edited.mp4
    ...
    whisper_json/   ← cached word-timestamp JSON (re-used on reruns)
"""

import json, os, re, subprocess, sys, tempfile
from pathlib import Path

# ── Settings ──────────────────────────────────────────────────────────────────
SITE_DIR    = Path("/Users/elainesaiserver/dev/lecture-site")
OUTPUT_DIR  = Path("/Users/elainesaiserver/dev/lecture-site-edited")

# Words that are always removed (case-insensitive, punctuation stripped)
FILLER_WORDS = {"um", "uh", "hmm", "mhm"}

# Pauses longer than this (seconds) will be shortened
MAX_PAUSE   = 1.0

# How much silence to keep at each natural pause (sounds more natural than hard cuts)
KEEP_PAUSE  = 0.35

# Small buffer added around each filler-word cut (avoids clipping adjacent sounds)
FILLER_PAD  = 0.06

# Minimum segment length to bother keeping (avoids tiny slivers)
MIN_SEG     = 0.15

# ── Helpers ───────────────────────────────────────────────────────────────────

def run(cmd, **kwargs):
    print("    $", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True, **kwargs)


def get_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def whisper_words(audio_path, json_cache_dir):
    """
    Run Whisper with word_timestamps=True and return list of dicts:
      [{"word": "hello", "start": 0.52, "end": 0.88}, ...]
    Results are cached in json_cache_dir so re-runs are instant.
    """
    stem      = audio_path.stem
    json_path = json_cache_dir / f"{stem}.json"

    if not json_path.exists():
        print(f"  ▸ Running Whisper on {audio_path.name} (this takes a few minutes)...")
        run([
            "whisper", str(audio_path),
            "--word_timestamps", "True",
            "--output_format",   "json",
            "--output_dir",      str(json_cache_dir),
            "--model",           "small",
            "--language",        "en",
            "--fp16",            "False",
        ])
    else:
        print(f"  ▸ Using cached Whisper JSON: {json_path.name}")

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    words = []
    for seg in data.get("segments", []):
        for w in seg.get("words", []):
            clean = re.sub(r"[^a-z]", "", w["word"].lower())
            words.append({
                "word":  clean,
                "start": float(w["start"]),
                "end":   float(w["end"]),
            })
    return words


def build_keep_list(words, video_dur):
    """
    Returns a list of (start, end) float pairs that should be KEPT.
    Everything not in this list is cut.
    """
    remove = []  # list of [start, end] to remove

    # 1. Mark filler words
    for w in words:
        if w["word"] in FILLER_WORDS:
            s = max(0.0, w["start"] - FILLER_PAD)
            e = w["end"] + FILLER_PAD
            remove.append([s, e])

    # 2. Mark excess pause time
    prev_end = 0.0
    for w in words:
        gap = w["start"] - prev_end
        if gap > MAX_PAUSE:
            # Keep the first KEEP_PAUSE seconds; cut the rest
            remove.append([prev_end + KEEP_PAUSE, w["start"]])
        prev_end = w["end"]
    # Also check gap at the end of the video
    if video_dur - prev_end > MAX_PAUSE:
        remove.append([prev_end + KEEP_PAUSE, video_dur])

    # 3. Sort and merge overlapping remove ranges
    remove.sort(key=lambda x: x[0])
    merged = []
    for seg in remove:
        seg[0] = max(0.0, seg[0])
        seg[1] = min(video_dur, seg[1])
        if seg[1] <= seg[0]:
            continue
        if merged and seg[0] <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], seg[1])
        else:
            merged.append(seg)

    # 4. Invert: remove-list → keep-list
    keep = []
    cursor = 0.0
    for rs, re_ in merged:
        if rs - cursor >= MIN_SEG:
            keep.append((cursor, rs))
        cursor = re_
    if video_dur - cursor >= MIN_SEG:
        keep.append((cursor, video_dur))

    return keep


def build_filter_complex(segments):
    """
    Build an ffmpeg filter_complex string that trims and concatenates
    the given (start, end) segments from the input video.
    """
    n     = len(segments)
    parts = []
    refs  = []

    for i, (s, e) in enumerate(segments):
        # Trim video stream
        parts.append(
            f"[0:v]trim=start={s:.4f}:end={e:.4f},setpts=PTS-STARTPTS[v{i}]"
        )
        # Trim audio stream
        parts.append(
            f"[0:a]atrim=start={s:.4f}:end={e:.4f},asetpts=PTS-STARTPTS[a{i}]"
        )
        refs.append(f"[v{i}][a{i}]")

    # Concatenate all trimmed streams
    parts.append(f"{''.join(refs)}concat=n={n}:v=1:a=1[outv][outa]")
    return ";\n".join(parts)


def edit_video(video_path, segments, output_path):
    """
    Cut `video_path` according to `segments` and save to `output_path`.
    The filter_complex is written to a temp file to avoid shell arg-length limits.
    """
    filter_str = build_filter_complex(segments)

    # Write filter to a temp file (-filter_complex_script avoids ARG_MAX issues)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tf:
        tf.write(filter_str)
        filter_file = tf.name

    try:
        run([
            "ffmpeg", "-y",
            "-i",  str(video_path),
            "-filter_complex_script", filter_file,
            "-map",  "[outv]",
            "-map",  "[outa]",
            "-c:v",  "libx264",
            "-preset", "fast",   # balance of speed vs file size
            "-crf",  "23",       # quality (lower = better; 23 is visually lossless)
            "-c:a",  "aac",
            "-b:a",  "128k",
            str(output_path),
        ])
    finally:
        os.unlink(filter_file)


# ── Per-lecture processing ────────────────────────────────────────────────────

def process(folder, label):
    print(f"\n{'─'*60}")
    print(f"[{label}]  {folder.name}")
    print(f"{'─'*60}")

    # Find video file (.mp4)
    mp4s = sorted(folder.glob("*.mp4"))
    if not mp4s:
        print("  ✗ No .mp4 file found — skipping")
        return
    video = mp4s[0]

    output_path = OUTPUT_DIR / f"{label}_edited.mp4"
    if output_path.exists():
        print(f"  ✓ Already done: {output_path.name} — skipping")
        return

    # Prefer .m4a audio (smaller, faster for Whisper)
    m4as  = sorted(folder.glob("*.m4a"))
    audio = m4as[0] if m4as else video
    print(f"  Video : {video.name}")
    print(f"  Audio : {audio.name}")

    # Get video duration
    vid_dur = get_duration(video)
    print(f"  Length: {vid_dur/60:.1f} min  ({vid_dur:.1f} s)")

    # Whisper word timestamps
    json_dir = OUTPUT_DIR / "whisper_json"
    json_dir.mkdir(exist_ok=True)
    words = whisper_words(audio, json_dir)
    print(f"  Words detected: {len(words)}")

    # Build keep-segments list
    segs = build_keep_list(words, vid_dur)
    kept    = sum(e - s for s, e in segs)
    removed = vid_dur - kept
    pct     = 100 * kept / vid_dur if vid_dur else 100

    filler_count = sum(1 for w in words if w["word"] in FILLER_WORDS)
    print(f"  Filler words removed : {filler_count}")
    print(f"  Original length : {vid_dur/60:.1f} min")
    print(f"  Edited  length  : {kept/60:.1f} min  ({pct:.0f}% of original)")
    print(f"  Time saved      : {removed/60:.1f} min")
    print(f"  Segments to keep: {len(segs)}")

    print(f"\n  ▸ Encoding edited video (may take 15–40 min per lecture)...")
    edit_video(video, segs, output_path)
    print(f"\n  ✓ Saved → {output_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Sanity checks
    for tool in ("ffmpeg", "ffprobe", "whisper"):
        if subprocess.run(["which", tool], capture_output=True).returncode != 0:
            print(f"ERROR: '{tool}' not found on PATH.")
            print("  Install with:  brew install ffmpeg  /  pip3 install openai-whisper")
            sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Auto-discover lecture folders (sorted by date in folder name)
    all_dirs = sorted([d for d in SITE_DIR.iterdir() if d.is_dir()])
    lecture_dirs = [d for d in all_dirs if any(d.glob("*.mp4"))]

    if not lecture_dirs:
        print(f"ERROR: No lecture folders with .mp4 files found in:\n  {SITE_DIR}")
        sys.exit(1)

    print(f"Found {len(lecture_dirs)} lecture folder(s) with video files")
    print(f"Output: {OUTPUT_DIR}\n")

    total_orig  = 0.0
    total_kept  = 0.0

    for i, folder in enumerate(lecture_dirs, 1):
        label = f"lecture{i}"
        try:
            process(folder, label)
        except Exception as ex:
            print(f"\n  ✗ ERROR processing {label}: {ex}")
            import traceback; traceback.print_exc()

    print(f"\n{'═'*60}")
    print("All lectures processed.")
    print(f"Edited videos saved to:  {OUTPUT_DIR}")
    print(f"{'═'*60}")


if __name__ == "__main__":
    main()
