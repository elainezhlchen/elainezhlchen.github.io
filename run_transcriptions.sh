#!/bin/bash
# ============================================================
# Lecture Transcription Script
# This script installs whisper and transcribes all 7 lectures.
# Run this once from Terminal — it may take 30-60 minutes total.
# ============================================================

set -e

LECTURE_SITE="/Users/elainesaiserver/dev/lecture-site"
SLIDES_DIR="/Users/elainesaiserver/dev/my-personal-website/assets/class_slides"
OUTPUT_DIR="/Users/elainesaiserver/dev/my-personal-website/lecture-materials"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "============================================================"
echo "  Lecture Transcription Setup"
echo "============================================================"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Please install Python first."
    exit 1
fi

# Check & install ffmpeg (required by whisper)
echo "Step 1: Checking for ffmpeg..."
if ! command -v ffmpeg &>/dev/null; then
    echo "  ffmpeg not found. Installing via Homebrew..."
    if ! command -v brew &>/dev/null; then
        echo "ERROR: Homebrew not found. Please install Homebrew first:"
        echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi
    brew install ffmpeg
    echo "  ffmpeg installed."
else
    echo "  ffmpeg found: $(which ffmpeg)"
fi

# Install required Python packages
echo "Step 2: Installing Python packages..."
pip3 install openai-whisper pymupdf --quiet
echo "  Packages installed."
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Write the Python processing script inline
PYTHON_SCRIPT=$(cat <<'PYEOF'
import sys
import os
import re
import fitz  # pymupdf
import whisper

LECTURE_SITE = os.environ["LECTURE_SITE"]
SLIDES_DIR   = os.environ["SLIDES_DIR"]
OUTPUT_DIR   = os.environ["OUTPUT_DIR"]

LECTURES = [
    {"num": 1, "folder": "2025-01-06 09.02.53 Intro to RNA-based Therapeutics", "pdf": "EN580133_lecture1.pdf"},
    {"num": 2, "folder": "2025-01-07 09.02.29 Intro to RNA-based Therapeutics", "pdf": "EN580133_lecture2.pdf"},
    {"num": 3, "folder": "2025-01-08 09.03.20 Intro to RNA-based Therapeutics", "pdf": "EN580133_lecture3.pdf"},
    {"num": 4, "folder": "2025-01-09 09.03.39 Intro to RNA-based Therapeutics", "pdf": "EN580133_lecture4.pdf"},
    {"num": 5, "folder": "2025-01-13 09.03.10 Intro to RNA-based Therapeutics", "pdf": "EN580133_lecture5.pdf"},
    {"num": 6, "folder": "2025-01-14 09.03.08 Intro to RNA-based Therapeutics", "pdf": "EN580133_lecture6.pdf"},
    {"num": 7, "folder": "2025-01-16 09.03.31 Intro to RNA-based Therapeutics", "pdf": "EN580133_lecture7.pdf"},
]

def find_audio_file(folder_path):
    for f in os.listdir(folder_path):
        if f.endswith('.m4a'):
            return os.path.join(folder_path, f)
    for f in os.listdir(folder_path):
        if f.endswith('.mp4'):
            return os.path.join(folder_path, f)
    return None

def extract_slide_texts(pdf_path):
    doc = fitz.open(pdf_path)
    slides = []
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        slides.append((i + 1, text))
    doc.close()
    return slides

def get_keywords(text, min_len=5, top_n=8):
    stopwords = {"the","and","for","that","this","with","from","are","have","will",
                 "been","they","their","which","when","also","into","more","than",
                 "can","not","all","but","cell","cells","these","based","through"}
    words = re.findall(r'[a-zA-Z]{%d,}' % min_len, text.lower())
    words = [w for w in words if w not in stopwords]
    seen = set()
    unique = []
    for w in words:
        if w not in seen:
            seen.add(w)
            unique.append(w)
    return unique[:top_n]

def find_slide_transitions(segments, slides):
    seg_texts = [(s['start'], s['text'].lower()) for s in segments]
    transitions = [(0.0, 1)]
    last_assigned_time = 0.0

    for slide_num, slide_text in slides[1:]:
        keywords = get_keywords(slide_text)
        if not keywords:
            continue
        hits = 0
        earliest = None
        for kw in keywords[:5]:
            for seg_start, seg_text in seg_texts:
                if kw in seg_text and seg_start > last_assigned_time:
                    hits += 1
                    if earliest is None or seg_start < earliest:
                        earliest = seg_start
                    break
        if hits >= 2 and earliest is not None:
            transitions.append((earliest, slide_num))
            last_assigned_time = earliest

    return sorted(transitions, key=lambda x: x[0])

def build_transcript_md(segments, transitions, lecture_num):
    lines = [f"# Lecture {lecture_num} — Transcript\n\n---\n## [Slide 1]\n"]
    transition_index = 0
    current_slide = 1
    first = True

    for seg in segments:
        t = seg['start']
        text = seg['text'].strip()
        if not text:
            continue

        while (transition_index + 1 < len(transitions) and
               t >= transitions[transition_index + 1][0]):
            transition_index += 1
            current_slide = transitions[transition_index][1]
            lines.append(f"\n---\n## [Slide {current_slide}]\n")

        mm = int(t) // 60
        ss = int(t) % 60
        lines.append(f"**[{mm:02d}:{ss:02d}]** {text}  ")

    return "\n".join(lines)

def main():
    lecture_num = int(sys.argv[1]) if len(sys.argv) > 1 else None
    lectures = [l for l in LECTURES if lecture_num is None or l['num'] == lecture_num]

    print(f"Loading Whisper model (small)...")
    model = whisper.load_model("small")
    print("Model loaded.\n")

    for lec in lectures:
        num = lec['num']
        folder_path = os.path.join(LECTURE_SITE, lec['folder'])
        audio_path = find_audio_file(folder_path)
        pdf_path = os.path.join(SLIDES_DIR, lec['pdf'])

        print(f"{'='*55}")
        print(f"  Lecture {num}: Transcribing {os.path.basename(audio_path)}...")
        print(f"{'='*55}")

        result = model.transcribe(audio_path, verbose=False, language="en", fp16=False)
        segments = result['segments']
        print(f"  Transcription done. {len(segments)} segments.")

        slides = extract_slide_texts(pdf_path)
        print(f"  PDF: {len(slides)} slides.")

        transitions = find_slide_transitions(segments, slides)
        print(f"  Found {len(transitions)} slide transitions.")

        md = build_transcript_md(segments, transitions, num)

        out_path = os.path.join(OUTPUT_DIR, f"lecture{num}_transcript.md")
        with open(out_path, "w") as f:
            f.write(md)
        print(f"  Saved: {out_path}\n")

if __name__ == "__main__":
    main()
PYEOF
)

echo "Step 3: Running transcriptions (this will take ~5-8 min per lecture)..."
echo "  Total: ~7 lectures. Please keep Terminal open."
echo ""

export LECTURE_SITE SLIDES_DIR OUTPUT_DIR

python3 -c "$PYTHON_SCRIPT"

echo ""
echo "============================================================"
echo "  All transcripts saved to:"
echo "  $OUTPUT_DIR"
echo "============================================================"
echo ""
echo "Transcription complete! You can close this Terminal window."
