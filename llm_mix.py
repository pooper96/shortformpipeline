import os, json
from typing import List, Dict
from openai import OpenAI

def mix_and_order_clips(candidates: List[Dict], transcript: List[Dict], top_k: int = 5):
    """
    candidates: [{start, end, score, preview?}]
    returns: [{start, end}] ordered for engagement
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️ No OPENAI_API_KEY; returning top-k by score.")
        return candidates[:top_k]

    client = OpenAI(api_key=api_key)

    # Build ultra-compact prompt
    lines = []
    for c in candidates:
        lines.append(f"[{c['start']:.2f}-{c['end']:.2f}] s={round(c.get('score',0.0),2)}")
    user_prompt = (
        "You are a ruthless short-form editor. "
        "From these candidate clip windows, pick and order up to {k} that maximize 3s/5s/15s retention. "
        "Return strict JSON array: [{\"start\":sec, \"end\":sec}, ...]\n\nCANDIDATES:\n{cands}"
    ).format(k=top_k, cands="\n".join(lines))

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role":"system","content":"Return only JSON, no commentary."},
                {"role":"user","content":user_prompt}
            ],
            temperature=0.2,
            max_tokens=300
        )
        txt = resp.choices[0].message.content.strip()
        if txt.startswith("```"):
            txt = txt.strip("`")
            nl = txt.find("\n")
            if nl != -1 and txt[:nl].lower().startswith("json"):
                txt = txt[nl+1:]
        arr = json.loads(txt)
        # sanitize
        out = []
        for it in arr:
            s = float(it.get("start", 0.0))
            e = float(it.get("end", 0.0))
            if e > s:
                out.append({"start": s, "end": e})
            if len(out) >= top_k:
                break
        if out:
            return out
    except Exception as e:
        print(f"⚠️ OpenAI error: {e}")

    return candidates[:top_k]
