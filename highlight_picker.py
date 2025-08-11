import os, json, yaml, time
from typing import List, Dict
from hook_mixer import find_hooks, refine_hook_boundaries
from audio_peaks import ensure_wav, energy_peaks
from llm_mix import mix_and_order_clips  # optional GPT mixing

def pick_highlights(transcript: List[Dict], work_dir: str, config_path: str, video_path: str = None):
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    clip_cfg = cfg.get("clip", {}) or {}
    scoring  = cfg.get("scoring", {}) or {}

    min_s   = float(clip_cfg.get("min_seconds", 15))
    max_s   = float(clip_cfg.get("max_seconds", 45))
    top_k   = int(scoring.get("max_clips", 5))
    window  = float(scoring.get("window_sec", 10.0))
    stride  = float(scoring.get("stride_sec", 5.0))
    mode    = (scoring.get("mode", "hybrid") or "hybrid").lower()  # local | gpt | hybrid

    print("\n✨ Picking highlights (hooks + audio)…")

    # 1) Local hook candidates
    local_hooks = find_hooks(transcript, window_s=window, hop_s=stride, top_k=max(top_k*3, top_k))
    refined = refine_hook_boundaries(
        local_hooks, transcript,
        lead_pad=float(clip_cfg.get("buffer_in", 0.25)),
        tail_pad=float(clip_cfg.get("buffer_out", 0.35)),
        merge_next_if_cliff=True,
        max_refined_len_s=max_s
    )

    # 2) Filter by length
    candidates = []
    for h in refined:
        s = round(max(0.0, float(h["start"])), 2)
        e = round(float(h["end"]), 2)
        dur = e - s
        if min_s <= dur <= max_s:
            candidates.append({"start": s, "end": e, "score": float(h.get("score", 0.0)), "preview": h.get("preview","")})

    # 3) Audio peaks boost
    if video_path:
        wav_path = os.path.join(work_dir, "audio16k.wav")
        try:
            ensure_wav(video_path, wav_path, sr=16000)
            peaks = energy_peaks(wav_path)
            pts = [p[0] for p in peaks]
            def near_peak(t, ts, r=2.0): return any(abs(t - x) <= r for x in ts)
            for c in candidates:
                mid = 0.5*(c["start"]+c["end"])
                if near_peak(c["start"], pts) or near_peak(mid, pts):
                    c["score"] = c.get("score", 0.0) + 0.5
        except Exception as e:
            print(f"⚠️ audio peak step skipped: {e}")

    # 4) Sort by score
    candidates.sort(key=lambda x: x.get("score", 0.0), reverse=True)

    # 5) Optional GPT mixing/ordering
    if mode in ("gpt","hybrid"):
        try:
            plan = mix_and_order_clips(candidates[:max(top_k*2, top_k)], transcript, top_k=top_k)
            if isinstance(plan, list) and plan:
                highlights = [{"start": round(p["start"],2), "end": round(p["end"],2)} for p in plan[:top_k]]
            else:
                highlights = [{"start": round(c["start"],2), "end": round(c["end"],2)} for c in candidates[:top_k]]
        except Exception as e:
            print(f"⚠️ GPT mix failed: {e}")
            highlights = [{"start": round(c["start"],2), "end": round(c["end"],2)} for c in candidates[:top_k]]
    else:
        highlights = [{"start": round(c["start"],2), "end": round(c["end"],2)} for c in candidates[:top_k]]

    out_path = os.path.join(work_dir, "highlights.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(highlights, f, indent=2)
    print(f"✅ Selected {len(highlights)} highlights.")
    return highlights
