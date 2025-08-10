import os
import re
import argparse
import gc

from transcriber_torch import transcribe_audio  # switch to the torch backend
from highlight_picker import pick_highlights
from clipper import cut_clips
from captions_and_style import style_clips
from titles_tags import generate_titles


INPUT_FOLDER = "input"
OUTPUT_FOLDER = "output"
CONFIG_PATH = "config.yaml"


def _safe_move(src_path: str, out_dir: str, base_prefix: str) -> str:
    """
    Moves a file to out_dir with a name that never collides.
    Output pattern: <base_prefix>__<original_name>.ext  (with _1, _2… if needed)
    """
    os.makedirs(out_dir, exist_ok=True)
    name = os.path.basename(src_path)
    base, ext = os.path.splitext(name)

    # start with <videoName>__<clipname>.ext
    target_base = f"{base_prefix}__{base}"
    dst = os.path.join(out_dir, f"{target_base}{ext}")

    if not os.path.exists(dst):
        os.rename(src_path, dst)
        return dst

    # n+1 increment
    n = 1
    while True:
        cand = os.path.join(out_dir, f"{target_base}_{n}{ext}")
        if not os.path.exists(cand):
            os.rename(src_path, cand)
            return cand
        n += 1


def run_pipeline(video_path: str):
    basename = os.path.splitext(os.path.basename(video_path))[0]
    work_dir = os.path.join("work", basename)
    os.makedirs(work_dir, exist_ok=True)

    # 1) Transcribe
    transcript = transcribe_audio(video_path, work_dir, CONFIG_PATH)

    # 2) Pick highlights (GPT/local depending on your config)
    highlights = pick_highlights(transcript, work_dir, CONFIG_PATH)

    # Free heavy objects as we go to keep RAM/heap low
    del transcript
    gc.collect()

    # 3) Cut + 4) Style
    cut_clips(video_path, highlights, work_dir, CONFIG_PATH)
    style_clips(work_dir, CONFIG_PATH)

    # 5) Titles
    generate_titles(work_dir, CONFIG_PATH)

    # 6) Move _final clips to output using collision-safe names
    final_clips_dir = os.path.join(work_dir, "clips")
    if os.path.isdir(final_clips_dir):
        for file in os.listdir(final_clips_dir):
            if file.endswith("_final.mp4"):
                src = os.path.join(final_clips_dir, file)
                _safe_move(src, OUTPUT_FOLDER, basename)

    # Optional: clean up /work for this job to keep disk/RAM low
    # (comment out if you want to keep intermediates)
    # import shutil
    # shutil.rmtree(work_dir, ignore_errors=True)

    print("\n✅ Done! Check the output folder.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", help="Path to a single video to process")
    args = parser.parse_args()

    if args.input and os.path.exists(args.input):
        run_pipeline(args.input)
    else:
        # Fallback: process the first .mp4 in input/
        if not os.path.isdir(INPUT_FOLDER):
            os.makedirs(INPUT_FOLDER, exist_ok=True)
        for file in os.listdir(INPUT_FOLDER):
            if file.lower().endswith(".mp4"):
                path = os.path.join(INPUT_FOLDER, file)
                run_pipeline(path)
                break
        else:
            print("No .mp4 file found in input/")
