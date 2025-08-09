import os
import subprocess
from transcriber import transcribe_audio
from highlight_picker import pick_highlights
from clipper import cut_clips
from captions_and_style import style_clips
from titles_tags import generate_titles

INPUT_FOLDER = "input"
OUTPUT_FOLDER = "output"
CONFIG_PATH = "config.yaml"


def run_pipeline(video_path):
    basename = os.path.splitext(os.path.basename(video_path))[0]
    work_dir = os.path.join("work", basename)
    os.makedirs(work_dir, exist_ok=True)

    transcript = transcribe_audio(video_path, work_dir, CONFIG_PATH)
    highlights = pick_highlights(transcript, work_dir, CONFIG_PATH)
    cut_clips(video_path, highlights, work_dir, CONFIG_PATH)
    style_clips(work_dir, CONFIG_PATH)
    generate_titles(work_dir, CONFIG_PATH)

    # Move final clips to output
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    final_clips = os.path.join(work_dir, "clips")
    for file in os.listdir(final_clips):
        if file.endswith(".mp4"):
            src = os.path.join(final_clips, file)
            dst = os.path.join(OUTPUT_FOLDER, file)
            os.rename(src, dst)
    print("\n✅ Done! Check the output folder.")


if __name__ == "__main__":
    # Find first file in input/
    for file in os.listdir(INPUT_FOLDER):
        if file.endswith(".mp4"):
            path = os.path.join(INPUT_FOLDER, file)
            run_pipeline(path)
            break
    else:
        print("No .mp4 file found in input/")

# === transcribe.py ===
from faster_whisper import WhisperModel
import os
import json
import yaml


def transcribe_audio(video_path, work_dir, config_path):
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    use_gpu = config.get("use_gpu", True)
    model = WhisperModel("medium", device="cuda" if use_gpu else "cpu", compute_type="float16")

    print("\n🔍 Transcribing...")
    segments, info = model.transcribe(video_path, beam_size=5)

    transcript = []
    srt_lines = []
    for i, seg in enumerate(segments):
        transcript.append({"start": seg.start, "end": seg.end, "text": seg.text})
        srt_lines.append(f"{i + 1}\n{format_time(seg.start)} --> {format_time(seg.end)}\n{seg.text.strip()}\n")

    with open(os.path.join(work_dir, "transcript.json"), "w") as f:
        json.dump(transcript, f, indent=2)
    with open(os.path.join(work_dir, "transcript.srt"), "w") as f:
        f.write("\n".join(srt_lines))

    return transcript


def format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


# === highlight_picker.py ===
# Placeholder: loads transcript and selects dummy 2 highlight clips for now
import json


def pick_highlights(transcript, work_dir, config_path):
    print("\n✨ Picking highlights...")
    highlights = []
    for i, seg in enumerate(transcript[:2]):
        highlights.append({"start": seg['start'], "end": seg['end']})
    with open(os.path.join(work_dir, "highlights.json"), "w") as f:
        json.dump(highlights, f, indent=2)
    return highlights


# === clipper.py ===
import os
import subprocess
import json


def cut_clips(video_path, highlights, work_dir, config_path):
    print("\n✂️ Cutting clips...")
    clips_dir = os.path.join(work_dir, "clips")
    os.makedirs(clips_dir, exist_ok=True)

    for i, hl in enumerate(highlights):
        outpath = os.path.join(clips_dir, f"clip_{i + 1:03}.mp4")
        cmd = [
            "ffmpeg",
            "-ss", str(hl['start']),
            "-to", str(hl['end']),
            "-i", video_path,
            "-c:v", "libx264", "-crf", "23",
            "-c:a", "aac", "-strict", "experimental",
            outpath
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# === captions_and_style.py ===
# Placeholder: renames clips with _final to simulate captioned output
import os


def style_clips(work_dir, config_path):
    print("\n💬 Styling clips...")
    clips_dir = os.path.join(work_dir, "clips")
    for file in os.listdir(clips_dir):
        if file.endswith(".mp4") and not file.endswith("_final.mp4"):
            src = os.path.join(clips_dir, file)
            dst = os.path.join(clips_dir, file.replace(".mp4", "_final.mp4"))
            os.rename(src, dst)


# === titles_tags.py ===
# Placeholder: creates text titles for each final clip
import os


def generate_titles(work_dir, config_path):
    print("\n📝 Generating titles...")
    clips_dir = os.path.join(work_dir, "clips")
    for file in os.listdir(clips_dir):
        if file.endswith("_final.mp4"):
            name = file.replace("_final.mp4", "")
            with open(os.path.join(clips_dir, f"{name}_title.txt"), "w") as f:
                f.write(f"🔥 Epic Clip: {name.replace('_', ' ').title()} #viral #shorts")
