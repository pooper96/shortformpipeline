# clipper.py
import os, subprocess, json, yaml, time

def _sec(x):
    return max(0.0, float(x))

def cut_clips(video_path, highlights, work_dir, config_path):
    print("\n✂️ Cutting clips...")
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    enc = cfg.get("encode", {}) or {}

    mode      = (enc.get("mode") or "nvenc").lower()
    W         = int(enc.get("width", 1080))
    H         = int(enc.get("height", 1920))
    FPS       = int(enc.get("fps", 60))

    # NVENC tuning
    rc        = str(enc.get("rc", "vbr_hq"))
    cq        = str(enc.get("cq", 19))
    b_v       = str(enc.get("b_v", "8M"))
    maxrate   = str(enc.get("maxrate", "12M"))
    bufsize   = str(enc.get("bufsize", "24M"))
    preset    = str(enc.get("preset", "p5"))
    profile   = str(enc.get("profile", "high"))
    gop       = str(enc.get("gop", 120))
    aq        = str(enc.get("aq", 1))
    aq_str    = str(enc.get("aq_strength", 8))
    bf        = str(enc.get("bf", 3))

    # audio
    a_bitrate = str(enc.get("audio_bitrate", "192k"))
    a_rate    = str(enc.get("audio_rate", 48000))

    pad_in    = float(enc.get("pad_in", 0.15))
    pad_out   = float(enc.get("pad_out", 0.20))

    clips_dir = os.path.join(work_dir, "clips")
    os.makedirs(clips_dir, exist_ok=True)

    # Scale+pad to 1080x1920 portrait, keep aspect using zscale+lanczos
    # If your source is landscape, this will letterbox with black bars;
    # you can add smart reframing later to crop to faces instead.
    vf_base = (
        f"fps={FPS},scale=w={W}:h={H}:force_original_aspect_ratio=decrease:"
        "flags=lanczos,format=yuv420p,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black"
    ).replace("{W}", str(W)).replace("{H}", str(H))

    for i, hl in enumerate(highlights, start=1):
        s = _sec(hl["start"]) - pad_in
        s = max(0.0, s)
        e = _sec(hl["end"]) + pad_out
        dur = max(0.01, e - s)

        outpath = os.path.join(clips_dir, f"clip_{i:03}.mp4")
        t0 = time.time()

        if mode == "copy":
            # fastest; no re-encode, but no scaling either
            cmd = [
                "ffmpeg","-y",
                "-ss", f"{s:.3f}", "-i", video_path,
                "-t",  f"{dur:.3f}",
                "-c","copy","-movflags","+faststart",
                outpath
            ]
        else:
            # GPU encode with NVENC, tuned for platforms
            cmd = [
                "ffmpeg","-y",
                "-ss", f"{s:.3f}", "-i", video_path,
                "-t",  f"{dur:.3f}",
                "-vf", vf_base,
                "-c:v","h264_nvenc",
                "-rc:v", rc,
                "-cq", cq,
                "-b:v", b_v,
                "-maxrate", maxrate,
                "-bufsize", bufsize,
                "-preset", preset,
                "-profile:v", profile,
                "-g", gop,
                "-bf", bf,
                "-spatial_aq", aq,
                "-aq-strength", aq_str,
                "-pix_fmt","yuv420p",
                "-c:a","aac","-b:a", a_bitrate, "-ar", str(a_rate),
                # Loudness normalization to EBU R128-ish
                "-af","loudnorm=I=-16:TP=-1.5:LRA=11",
                "-movflags","+faststart",
                outpath
            ]

        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            # CPU fallback if NVENC missing
            cmd_fallback = [
                "ffmpeg","-y",
                "-ss", f"{s:.3f}", "-i", video_path,
                "-t",  f"{dur:.3f}",
                "-vf", vf_base,
                "-c:v","libx264","-crf","19","-preset","faster",
                "-pix_fmt","yuv420p",
                "-c:a","aac","-b:a", a_bitrate, "-ar", str(a_rate),
                "-af","loudnorm=I=-16:TP=-1.5:LRA=11",
                "-movflags","+faststart",
                outpath
            ]
            subprocess.run(cmd_fallback, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        dt = time.time() - t0
        print(f"  • clip_{i:03}.mp4  ({dur:.1f}s)  done in {dt:.1f}s [{mode}]")
