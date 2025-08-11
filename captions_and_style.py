import os, re, subprocess

def _fmt_time(s):
    h = int(s//3600); m = int((s%3600)//60); sec = int(s%60); ms = int(round((s-int(s))*1000))
    return f"{h:02}:{m:02}:{sec:02},{ms:03}"

def _parse_srt(path):
    if not os.path.isfile(path): return []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        raw = f.read().split("\n\n")
    out = []
    for block in raw:
        lines = [l.strip() for l in block.splitlines() if l.strip()!=""]
        if not lines: continue
        time_line = None
        for ln in lines[:2]:
            if "-->" in ln:
                time_line = ln; break
        if not time_line: continue
        m = re.match(r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})", time_line)
        if not m: continue
        def to_sec(ts):
            hh,mm,ssms = ts.split(":")
            ss,ms = ssms.split(",")
            return int(hh)*3600 + int(mm)*60 + int(ss) + int(ms)/1000.0
        start = to_sec(m.group(1)); end = to_sec(m.group(2))
        text = " ".join(lines[lines.index(time_line)+1:])
        out.append({"start":start,"end":end,"text":text})
    return out

def _write_clip_srt(lines, clip_start, clip_end, out_path):
    keep = []
    for ln in lines:
        s = max(ln["start"], clip_start)
        e = min(ln["end"], clip_end)
        if e > s:
            keep.append({"start": s-clip_start, "end": e-clip_start, "text": ln["text"]})
    if not keep:
        return False
    with open(out_path, "w", encoding="utf-8") as f:
        for i, ln in enumerate(keep, start=1):
            f.write(f"{i}\n{_fmt_time(ln['start'])} --> {_fmt_time(ln['end'])}\n{ln['text']}\n\n")
    return True

def _ffmpeg_escape_filter_path(p: str) -> str:
    p = p.replace("\\", "/").replace("'", r"\'").replace(",", r"\,")
    return p

def style_clips(work_dir, config_path):
    print("\n💬 Styling clips (captions)…")
    clips_dir = os.path.join(work_dir, "clips")
    if not os.path.isdir(clips_dir): return

    master_srt = os.path.join(work_dir, "transcript.srt")
    subs = _parse_srt(master_srt)
    hi_path = os.path.join(work_dir, "highlights.json")
    highlights = []
    if os.path.isfile(hi_path):
        import json
        with open(hi_path,"r",encoding="utf-8") as f:
            highlights = json.load(f)

    style = "Fontname=Arial,Fontsize=38,Outline=3,BorderStyle=3,PrimaryColour=&H00FFFFFF&,BackColour=&H7F000000&,Alignment=2,MarginV=110"

    for f in sorted(os.listdir(clips_dir)):
        if not (f.endswith(".mp4") and not f.endswith("_final.mp4")):
            continue
        src = os.path.join(clips_dir, f)
        dst = os.path.join(clips_dir, f.replace(".mp4", "_final.mp4"))

        try:
            idx = int(re.search(r"clip_(\d+)\.mp4$", f).group(1)) - 1
        except Exception:
            idx = None

        clip_srt = None
        if idx is not None and idx < len(highlights) and subs:
            h = highlights[idx]
            clip_srt = os.path.join(clips_dir, f"clip_{idx+1:03}.srt")
            ok = _write_clip_srt(subs, float(h["start"]), float(h["end"]), clip_srt)
            if not ok:
                clip_srt = None

        if clip_srt and os.path.isfile(clip_srt):
            vf = f"subtitles='{_ffmpeg_escape_filter_path(clip_srt)}':force_style='{style}'"
            cmd = [
                "ffmpeg","-y","-i",src,
                "-vf", vf,
                "-c:v","copy",                 # video already encoded well in cut step
                "-c:a","aac","-b:a","192k",
                "-movflags","+faststart",
                dst
            ]
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                continue
            except subprocess.CalledProcessError:
                pass

        # fallback: just rename to *_final
        base, ext = os.path.splitext(f)
        out = dst
        if os.path.exists(out):
            n = 1
            while True:
                cand = os.path.join(clips_dir, f"{base}_final_{n}{ext}")
                if not os.path.exists(cand):
                    out = cand; break
                n += 1
        os.rename(src, out)
