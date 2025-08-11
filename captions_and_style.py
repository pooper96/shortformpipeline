import os, subprocess, yaml, shutil

def _ffmpeg_escape_filter_path(p: str) -> str:
    """
    Make a Windows path safe for ffmpeg filter args.
    - use forward slashes
    - escape commas and single quotes
    """
    p = p.replace("\\", "/")
    p = p.replace("'", r"\'")
    p = p.replace(",", r"\,")
    return p

def style_clips(work_dir, config_path):
    print("\n💬 Styling clips (captions)…")
    clips_dir = os.path.join(work_dir, "clips")
    if not os.path.isdir(clips_dir):
        return

    srt_path = os.path.join(work_dir, "transcript.srt")
    have_srt = os.path.isfile(srt_path)

    # optional style tweaks via config later if you want
    style = "Fontname=Arial,Fontsize=28,Outline=2,BorderStyle=3,PrimaryColour=&H00FFFFFF&,BackColour=&H7F000000&,Alignment=2,MarginV=90"

    for f in sorted(os.listdir(clips_dir)):
        if not (f.endswith(".mp4") and not f.endswith("_final.mp4")):
            continue

        src = os.path.join(clips_dir, f)
        dst = os.path.join(clips_dir, f.replace(".mp4", "_final.mp4"))

        if have_srt:
            # Build filter arg with safe path
            srt_safe = _ffmpeg_escape_filter_path(srt_path)
            vf = f"subtitles='{srt_safe}':force_style='{style}'"
            cmd = [
                "ffmpeg", "-y",
                "-i", src,
                "-vf", vf,
                "-c:v", "libx264", "-crf", "19", "-preset", "veryfast",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                dst
            ]
            try:
                subprocess.run(cmd, check=True)
                continue
            except subprocess.CalledProcessError as e:
                print(f"⚠️ Caption burn-in failed ({e}). Falling back to simple rename for: {f}")

        # Fallback: no SRT or burn-in failed — just mark as final
        # Ensure we don't collide on repeated runs
        base, ext = os.path.splitext(f)
        out = dst
        if os.path.exists(out):
            n = 1
            while True:
                cand = os.path.join(clips_dir, f"{base}_final_{n}{ext}")
                if not os.path.exists(cand):
                    out = cand
                    break
                n += 1
        os.rename(src, out)
