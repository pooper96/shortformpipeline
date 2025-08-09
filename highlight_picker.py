# highlight_picker.py — GPT windowing + solid local fallback
import os, json, time, yaml
from typing import List, Dict
from openai import OpenAI

def pick_highlights(transcript: List[Dict], work_dir: str, config_path: str):
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    scoring = cfg.get("scoring", {}) or {}
    mode = scoring.get("mode", "local").lower()
    max_clips = int(scoring.get("max_clips", 5))
    window = int(scoring.get("window_sec", 120))
    stride = int(scoring.get("stride_sec", 30))

    if mode != "gpt":
        print("\n✨ Picking highlights (local fallback)…")
        return _local_fallback(transcript, work_dir, max_clips)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️ No OPENAI_API_KEY found. Falling back to local.")
        return _local_fallback(transcript, work_dir, max_clips)

    client = OpenAI(api_key=api_key)
    model = scoring.get("gpt_model", "gpt-4o-mini")

    print("\n✨ Picking highlights with GPT…")
    total_end = transcript[-1]["end"] if transcript else 0.0

    # ---- build rolling windows over transcript
    windows = []
    t = 0.0
    while t < total_end:
        w_start, w_end = t, min(t + window, total_end)
        segs = [s for s in transcript if not (s["end"] <= w_start or s["start"] >= w_end)]
        text = " ".join(s["text"].strip() for s in segs)
        if text.strip():
            windows.append({"start": w_start, "end": w_end, "text": text})
        t += stride
        if w_end >= total_end:
            break

    system_prompt = (
        "You are a ruthless short-form editor. "
        "Find 15–45s self-contained viral moments: strong hook in first 3s, clarity, payoff. "
        "Output strict JSON only."
    )

    # IMPORTANT: double braces to escape .format so JSON braces survive
    user_tpl = (
        "Window {start:.2f}-{end:.2f}s.\n"
        "Transcript:\n{snippet}\n\n"
        "Return JSON ONLY:\n"
        "{{\"candidates\":[{{\"start\": <sec>, \"end\": <sec>, \"reason\": \"<why>\", \"score\": <0-100>}}]}}\n"
        "Rules: 15<=duration<=45; bounds within window; up to 2 candidates; if none, empty list."
    )

    candidates: List[Dict] = []
    for w in windows:
        prompt = user_tpl.format(start=w["start"], end=w["end"], snippet=w["text"])
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role":"system","content":system_prompt},
                    {"role":"user","content":prompt},
                ],
                temperature=0.2,
                max_tokens=300,
            )
            content = resp.choices[0].message.content.strip()
            data = _safe_json(content)
            for c in (data.get("candidates") or []):
                try:
                    s = float(c.get("start", 0.0))
                    e = float(c.get("end", 0.0))
                except Exception:
                    continue
                if 15 <= (e - s) <= 45:
                    # clamp to window
                    s = max(s, w["start"]); e = min(e, w["end"])
                    if e > s:
                        candidates.append({
                            "start": s, "end": e,
                            "score": float(c.get("score", 0)),
                            "reason": str(c.get("reason",""))[:200]
                        })
        except Exception as ex:
            print(f"⚠️ GPT window error: {ex}")
        time.sleep(0.2)

    if not candidates:
        print("⚠️ No GPT candidates. Using local fallback.")
        return _local_fallback(transcript, work_dir, max_clips)

    # merge overlaps and keep top-N by score
    candidates = _merge_overlaps(candidates, pad=2.0)
    candidates.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    highlights = [{"start": round(c["start"],2), "end": round(c["end"],2)} for c in candidates[:max_clips]]

    out_path = os.path.join(work_dir, "highlights.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(highlights, f, indent=2)
    print(f"✅ Selected {len(highlights)} highlights.")
    return highlights

def _safe_json(txt: str):
    try:
        t = txt.strip()
        if t.startswith("```"):
            t = t.strip("`")
            nl = t.find("\n")
            if nl != -1 and t[:nl].lower().startswith("json"):
                t = t[nl+1:]
        return json.loads(t)
    except Exception:
        return {"candidates":[]}

def _merge_overlaps(cands: List[Dict], pad: float = 2.0):
    cands = sorted(cands, key=lambda x: x["start"])
    merged = []
    for c in cands:
        if not merged:
            merged.append(c); continue
        last = merged[-1]
        if c["start"] <= last["end"] + pad:
            best = c if c.get("score", 0.0) > last.get("score", 0.0) else last
            merged[-1] = {
                "start": min(last["start"], c["start"]),
                "end":   max(last["end"],   c["end"]),
                "score": max(last.get("score",0.0), c.get("score",0.0)),
                "reason": best.get("reason",""),
            }
        else:
            merged.append(c)
    return merged

def _local_fallback(transcript: List[Dict], work_dir: str, max_clips: int):
    """Simple backup: pick dense 30s spans by word count."""
    span = 30.0
    out: List[Dict] = []
    if transcript:
        end_t = float(transcript[-1]["end"])
        totals = []
        t = 0.0
        while t < end_t:
            words = 0
            for s in transcript:
                if s["start"] >= t and s["end"] <= t + span:
                    words += len((s.get("text") or "").split())
            totals.append((words, t, min(t + span, end_t)))
            t += 10.0
        totals.sort(reverse=True, key=lambda x: x[0])
        for words, s, e in totals[:max_clips]:
            if e > s:
                out.append({"start": round(s,2), "end": round(e,2)})
    out_path = os.path.join(work_dir, "highlights.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    return out
