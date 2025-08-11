import os
import re
import argparse
import gc
import json

from transcriber_torch import transcribe_audio   # using PyTorch Whisper backend
from highlight_picker import pick_highlights
from clipper import cut_clips
from captions_and_style import style_clips
from titles_tags import generate_titles

INPUT_FOLDER = "input"
OUTPUT_FOLDER = "output"
CONFIG_PATH = "config.yaml"

def _safe_move(src_path: str, out_dir: str, base_prefix: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    name = os.path.basename(src_path)
    base, ext = os.path.splitext(name)
    target_base = f"{base_prefix}__{base}"
    dst = os.path.join(out_dir, f"{target_base}{ext}")
    if not os.path.exists(dst):
        os.rename(src_path, dst)
        return dst
    n = 1
    while True:
        cand = os.path.join(out_dir, f"{target_base}_{n}{ext}")
        if not os.path.exists(cand):
            os.rename(src_path, cand)
            return cand
        n += 1

def concatenate_clips(out_dir: str, combined_filename: str):
    # combine all *_final.mp4 for this source into one
    clips = [f for f in os.listdir(out_dir) if f.endswith("_final.mp4")]
    if not clips:
        print("⚠️ No final clips to concat.")
        return None
    clips.sort()
    list_path = os.path.join(out_dir, "clip_list.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for c in clips:
            f.write(f"file '{os.path.join(out_dir, c)}'\n")
    combined_path = os.path.join(out_dir, combined_filename)
    import subprocess
    try:
        subprocess.run([
            "ffmpeg","-y",
            "-f","concat","-safe","0",
            "-i", list_path,
            "-c","copy",
            combined_path
        ], check=True)
        print(f"🎬 Combined: {combined_path}")
        return combined_path
    except Exception as e:
        print(f"⚠️ Concat failed: {e}")
        return None
    finally:
        try:
            os.remove(list_path)
        except Exception:
            pass

def run_pipeline(video_path: str):
    basename = os.path.splitext(os.path.basename(video_path))[0]
    work_dir = os.path.join("work", basename)
    os.makedirs(work_dir, exist_ok=True)

    # 1) Transcribe
    transcript = transcribe_audio(video_path, work_dir, CONFIG_PATH)

    # 2) Pick highlights (local hooks + audio peaks; optional GPT mixing)
    highlights = pick_highlights(transcript, work_dir, CONFIG_PATH, video_path=video_path)

    # free big objects to keep RAM low
    del transcript
    gc.collect()

    # 3) Cut + 4) Style
    cut_clips(video_path, highlights, work_dir, CONFIG_PATH)
    style_clips(work_dir, CONFIG_PATH)

    # 5) Titles
    generate_titles(work_dir, CONFIG_PATH)

    # 6) Move finals to output (collision-safe names)
    final_clips_dir = os.path.join(work_dir, "clips")
    moved = []
    if os.path.isdir(final_clips_dir):
        for file in os.listdir(final_clips_dir):
            if file.endswith("_final.mp4"):
                src = os.path.join(final_clips_dir, file)
                moved_path = _safe_move(src, OUTPUT_FOLDER, basename)
                moved.append(moved_path)

    # 7) Concat (optional; creates <VideoName>_combined.mp4)
    if moved:
        combined_name = f"{basename}_combined.mp4"
        concatenate_clips(OUTPUT_FOLDER, combined_name)

    print("\n✅ Done! Check the output folder.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", help="Path to a single video to process")
    args = parser.parse_args()

    if args.input and os.path.exists(args.input):
        run_pipeline(args.input)
    else:
        if not os.path.isdir(INPUT_FOLDER):
            os.makedirs(INPUT_FOLDER, exist_ok=True)
        for file in os.listdir(INPUT_FOLDER):
            if file.lower().endswith(".mp4"):
                path = os.path.join(INPUT_FOLDER, file)
                run_pipeline(path)
                break
        else:
            print("No .mp4 file found in input/")
