import os, subprocess, shlex, glob

def style_clips(work_dir, config_path):
    print("\n💬 Styling clips (captions)…")
    clips_dir = os.path.join(work_dir, "clips")
    srt_path = os.path.join(work_dir, "transcript.srt")
    if not os.path.isfile(srt_path):
        # fallback to rename if no subtitles exist
        for f in os.listdir(clips_dir):
            if f.endswith(".mp4") and not f.endswith("_final.mp4"):
                src = os.path.join(clips_dir, f)
                os.rename(src, os.path.join(clips_dir, f.replace(".mp4", "_final.mp4")))
        return

    for f in sorted(os.listdir(clips_dir)):
        if f.endswith(".mp4") and not f.endswith("_final.mp4"):
            src = os.path.join(clips_dir, f)
            dst = os.path.join(clips_dir, f.replace(".mp4", "_final.mp4"))

            # ffmpeg subtitles style (needs libass; most ffmpeg builds have it)
            style = "Fontname=Arial,Fontsize=28,Outline=2,BorderStyle=3,PrimaryColour=&H00FFFFFF&,BackColour=&H7F000000&,Alignment=2,MarginV=90"
            cmd = [
                "ffmpeg","-y","-i",src,
                "-vf", f"subtitles={shlex.quote(srt_path)}:force_style='{style}'",
                "-c:v","libx264","-crf","19","-preset","veryfast",
                "-c:a","aac","-b:a","128k",
                dst
            ]
            subprocess.run(cmd, check=True)
