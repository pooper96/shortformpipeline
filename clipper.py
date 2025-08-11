import os, subprocess, json, yaml, time

def _sec(x):
    return max(0.0, float(x))

def cut_clips(video_path, highlights, work_dir, config_path):
    print("\n✂️ Cutting clips...")
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    enc = cfg.get("encode", {}) or {}
    mode = (enc.get("mode") or "nvenc").lower()     # "nvenc" or "copy"
    crf = str(enc.get("crf", 23))
    preset = str(enc.get("preset", "p5"))
    ab = str(enc.get("audio_bitrate", "128k"))
    pad_in = float(enc.get("pad_in", 0.15))
    pad_out = float(enc.get("pad_out", 0.20))

    clips_dir = os.path.join(work_dir, "clips")
    os.makedirs(clips_dir, exist_ok=True)

    for i, hl in enumerate(highlights, start=1):
        # timing with soft pads
        s = _sec(hl["start"]) - pad_in
        s = max(0.0, s)
        e = _sec(hl["end"]) + pad_out
        dur = max(0.01, e - s)

        outpath = os.path.join(clips_dir, f"clip_{i:03}.mp4")
        t0 = time.time()

        if mode == "copy":
            # ⚡ Fastest (no re-encode) BUT cuts snap to keyframes; captions still fine
            # Use -ss before -i for speed, -t for duration
            cmd = [
                "ffmpeg", "-y",
                "-ss", f"{s:.3f}", "-i", video_path,
                "-t", f"{dur:.3f}",
                "-c", "copy",
                "-movflags", "+faststart",
                outpath
            ]
        else:
            # 🚀 GPU encode with NVENC (uses your 4060)
            cmd = [
                "ffmpeg", "-y",
                "-ss", f"{s:.3f}", "-i", video_path,
                "-t", f"{dur:.3f}",
                "-c:v", "h264_nvenc",
                "-preset", preset,          # p1 slow ↔ p7 fastest
                "-cq", crf,                 # constant quality (like CRF)
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", ab,
                "-movflags", "+faststart",
                outpath
            ]

        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as e:
            print(f"⚠️ ffmpeg failed on clip {i}: {e}. Retrying with CPU libx264…")
            # CPU fallback if NVENC not available
            cmd_fallback = [
                "ffmpeg", "-y",
                "-ss", f"{s:.3f}", "-i", video_path,
                "-t", f"{dur:.3f}",
                "-c:v", "libx264", "-crf", crf,
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", ab,
                "-movflags", "+faststart",
                outpath
            ]
            subprocess.run(cmd_fallback, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        dt = time.time() - t0
        print(f"  • clip_{i:03}.mp4  ({dur:.1f}s)  done in {dt:.1f}s [{mode}]")
