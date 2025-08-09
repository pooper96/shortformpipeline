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
