# hook_mixer.py
# Local hook finder (cheap) + prompt builder (tiny) + sentence-boundary refinement + ffmpeg command planner

from typing import List, Dict, Tuple
import math, re
from collections import Counter

# --------------------------- config / lexicons ---------------------------

STOPWORDS = set("""
a an the and or but if then so because as while of to in on for with at by from into during
about against between through before after above below up down off over under again further
is are was were be been being do does did have has had having i you he she it we they me him her them
my your his her its our their this that these those not no nor than too very just also like
""".split())

CURIOSITY = set("""
secret secrets reveal revealed surprising surprise shock shocked insane wild unexpected
what why how when where who watch look story truth hidden behind inside
""".split())

URGENCY = set("""
now today finally breaking urgent warning alert last chance deadline
""".split())

SUPERLATIVES = set("""
best worst first only biggest smallest fastest slowest cheapest craziest ultimate
""".split())

CONTROVERSY = set("""
hate love cancel exposed expose scam fraud vs versus debate controversial rumor drama illegal
""".split())

NUMERIC_RE = re.compile(r"\b([0-9]+|[0-9]+(\.[0-9]+)?)\b")

PUNCT_END = re.compile(r"[.!?…]+['”\"]?$")
CLIFFHANGER = re.compile(r"\b(because|so|and|but|then|which|that|when|if)\b", re.I)

# --------------------------- small utils ---------------------------

def tokenize(text: str) -> List[str]:
    return [w.lower() for w in re.findall(r"[a-zA-Z0-9']+", text)]

def has_question(text: str) -> bool:
    t = text.strip().lower()
    return "?" in text or t.startswith(("what", "why", "how", "when", "where", "who"))

def clip_len(start: float, end: float) -> float:
    return max(0.0, float(end) - float(start))

# --------------------------- sentenceizer ---------------------------

def build_sentences(transcript: List[Dict],
                    max_gap_s: float = 0.6,
                    max_sentence_s: float = 20.0) -> List[Dict]:
    """
    Accepts word- or sentence-level items: {start, end, text}
    Groups into 'sentence-like' spans using terminal punctuation OR time gaps.
    Returns list of {sid, start, end, text}
    """
    if not transcript:
        return []
    # If entries already look sentence-level, just adopt them
    looks_sentence_level = all(len(x.get("text","").split()) > 3 for x in transcript)
    if looks_sentence_level and len(transcript) < 400:
        sents = []
        for i, x in enumerate(transcript):
            sents.append({
                "sid": f"S{i+1}",
                "start": float(x["start"]),
                "end": float(x["end"]),
                "text": x["text"].strip()
            })
        return sents

    # Otherwise, accumulate by punctuation or inter-word gaps
    sents = []
    cur = {"start": float(transcript[0]["start"]), "text": [], "end": float(transcript[0]["end"])}
    for i, t in enumerate(transcript):
        w = t["text"]
        cur["text"].append(w)
        cur["end"] = float(t["end"])
        # split conditions
        gap = 0.0
        if i+1 < len(transcript):
            gap = float(transcript[i+1]["start"]) - float(t["end"])
        too_long = (cur["end"] - cur["start"]) >= max_sentence_s
        if PUNCT_END.search(w) or gap >= max_gap_s or too_long:
            sents.append({
                "sid": f"S{len(sents)+1}",
                "start": float(cur["start"]),
                "end": float(cur["end"]),
                "text": " ".join(cur["text"]).strip()
            })
            if i+1 < len(transcript):
                cur = {"start": float(transcript[i+1]["start"]), "text": [], "end": float(transcript[i+1]["end"])}
    if cur["text"]:
        sents.append({
            "sid": f"S{len(sents)+1}",
            "start": float(cur["start"]),
            "end": float(cur["end"]),
            "text": " ".join(cur["text"]).strip()
        })
    return sents

# --------------------------- segment builder (rolling) ---------------------------

def make_segments(transcript: List[Dict], window_s: float = 10.0, hop_s: float = 5.0) -> List[Dict]:
    """
    Build rolling windows over sentence text to preserve coherence while scoring.
    """
    sents = build_sentences(transcript)
    if not sents:
        return []
    t0 = sents[0]["start"]
    t_end = sents[-1]["end"]
    segments = []
    cur = t0
    idx = 0
    while cur < t_end:
        seg_text = []
        seg_start = cur
        seg_end = cur + window_s
        while idx < len(sents) and sents[idx]["end"] < seg_start:
            idx += 1
        j = idx
        while j < len(sents) and sents[j]["start"] <= seg_end:
            seg_text.append(sents[j]["text"])
            j += 1
        text = " ".join(seg_text).strip()
        if text:
            segments.append({"id": len(segments), "start": seg_start, "end": min(seg_end, t_end), "text": text})
        cur += hop_s
    return segments

# --------------------------- rarity / tf-idf-ish ---------------------------

def rarity_scores(segments: List[Dict]) -> Dict[int, float]:
    # document frequency over segments (unique tokens per seg)
    df = Counter()
    for s in segments:
        toks = set(w for w in tokenize(s["text"]) if w not in STOPWORDS and len(w) > 2)
        for w in toks:
            df[w] += 1
    N = len(segments) + 1e-9
    idf = {w: math.log(N / (c + 1.0)) for w, c in df.items()}
    scores = {}
    for s in segments:
        toks = [w for w in tokenize(s["text"]) if w not in STOPWORDS and len(w) > 2]
        if not toks:
            scores[s["id"]] = 0.0
            continue
        rar = sum(idf.get(w, 0.0) for w in toks) / len(toks)
        scores[s["id"]] = rar
    return scores

# --------------------------- hook scoring ---------------------------

def score_segment(s: Dict, idf_score: float) -> float:
    text = s["text"]
    toks = set(tokenize(text))
    length = clip_len(s["start"], s["end"])

    q_bonus = 0.6 if has_question(text) else 0.0
    exclam = 0.3 if "!" in text else 0.0

    num_bonus = 0.0
    if NUMERIC_RE.search(text):
        num_bonus += 0.25
        if re.search(r"\b(top|step|reason|lesson|rule|mistake)s?\b", text.lower()):
            num_bonus += 0.15

    curi = len(CURIOSITY & toks) * 0.25
    urg  = len(URGENCY   & toks) * 0.20
    sup  = len(SUPERLATIVES & toks) * 0.20
    ctr  = len(CONTROVERSY & toks) * 0.30

    # length preference: hooks ~6–12s
    if 6 <= length <= 12:
        length_pref = 0.5
    elif 3 <= length < 6 or 12 < length <= 18:
        length_pref = 0.2
    else:
        length_pref = -0.2

    char_len = len(text)
    density = -0.0004 * max(0, char_len - 350)

    score = (
        1.2 * idf_score
        + q_bonus + exclam + num_bonus
        + curi + urg + sup + ctr
        + length_pref + density
    )
    return round(score, 4)

# --------------------------- non-overlapping picker ---------------------------

def pick_top_nonoverlapping(segments: List[Dict], scores: Dict[int, float],
                            top_k: int = 5, iou_thresh: float = 0.3) -> List[Dict]:
    cand = sorted(segments, key=lambda s: scores.get(s["id"], 0), reverse=True)
    chosen = []
    def iou(a: Tuple[float,float], b: Tuple[float,float]) -> float:
        inter = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
        union = (a[1]-a[0]) + (b[1]-b[0]) - inter + 1e-9
        return inter / union
    for s in cand:
        if len(chosen) >= top_k:
            break
        if all(iou((s["start"], s["end"]), (c["start"], c["end"])) <= iou_thresh for c in chosen):
            s2 = dict(s)
            s2["score"] = scores.get(s["id"], 0.0)
            preview = s2["text"].strip().replace("\n", " ")
            s2["preview"] = (preview[:240] + "…") if len(preview) > 240 else preview
            chosen.append(s2)
    return chosen

# --------------------------- public: find hooks ---------------------------

def find_hooks(transcript: List[Dict],
               window_s: float = 10.0,
               hop_s: float = 5.0,
               top_k: int = 5) -> List[Dict]:
    segments = make_segments(transcript, window_s, hop_s)
    rar = rarity_scores(segments)
    scored = {s["id"]: score_segment(s, rar.get(s["id"], 0.0)) for s in segments}
    top = pick_top_nonoverlapping(segments, scored, top_k=top_k)
    for i, t in enumerate(top):
        t["hook_id"] = f"H{i+1}"
    return top

# --------------------------- refine to sentence boundaries ---------------------------

def _find_containing_sentence(hook: Dict, sentences: List[Dict]) -> int:
    hs, he = hook["start"], hook["end"]
    best = -1
    best_overlap = 0.0
    for i, s in enumerate(sentences):
        inter = max(0.0, min(he, s["end"]) - max(hs, s["start"]))
        if inter > best_overlap:
            best_overlap = inter
            best = i
    return best

def refine_hook_boundaries(hooks: List[Dict],
                           transcript: List[Dict],
                           lead_pad: float = 0.25,
                           tail_pad: float = 0.35,
                           merge_next_if_cliff: bool = True,
                           max_refined_len_s: float = 14.0) -> List[Dict]:
    sentences = build_sentences(transcript)
    if not sentences:
        return hooks
    refined = []
    for h in hooks:
        i = _find_containing_sentence(h, sentences)
        if i == -1:
            refined.append(h); continue
        s = sentences[i]
        new_start = max(0.0, s["start"] - lead_pad)
        new_end = s["end"] + tail_pad
        # merge if cliffhanger
        if merge_next_if_cliff and s["text"].split():
            last_word = s["text"].split()[-1].lower()
            if CLIFFHANGER.search(last_word) and i+1 < len(sentences):
                s2 = sentences[i+1]
                cand_end = min(s2["end"] + tail_pad, new_start + max_refined_len_s)
                if cand_end - new_start <= max_refined_len_s:
                    new_end = max(new_end, cand_end)
        if (new_end - new_start) > max_refined_len_s:
            new_end = new_start + max_refined_len_s
        h2 = dict(h)
        h2["start"], h2["end"] = new_start, new_end
        refined.append(h2)
    return refined

# --------------------------- prompt builder ---------------------------

def build_mix_prompt(video_title: str,
                     hooks: List[Dict],
                     target_len_s: int = 35,
                     max_clips: int = 4) -> str:
    """
    Send ONLY this prompt + the compact hook list (ids/times/previews).
    Ask the model to suggest the best combinations/order.
    """
    lines = [
        f"You are a short-form editor. Video: {video_title}",
        "Goal: choose and order the most compelling hooks to maximize 3s/5s/15s retention.",
        f"Target total length: <= {target_len_s}s. Use up to {max_clips} clips.",
        "Prefer questions, tension, numbers, and clear payoffs. Avoid redundancy.",
        "",
        "CANDIDATE_HOOKS:"
    ]
    for h in hooks:
        lines.append(
            f"- {h['hook_id']} [{round(h['start'],2)}–{round(h['end'],2)}s] score={h['score']}: {h['preview']}"
        )
    lines += [
        "",
        "Return strict JSON with fields:",
        '{ "sequence": ["H1","H3",...], "notes": "why this order works",',
        '  "clip_ranges": [{"hook_id":"H1","use":[[start_offset,end_offset]]}, ...] }',
        "Use 'clip_ranges' to trim within each hook if needed."
    ]
    return "\n".join(lines)

# --------------------------- ffmpeg command planner ---------------------------

def ffmpeg_commands_from_plan(src_path: str,
                              plan: Dict,
                              hooks_by_id: Dict[str, Dict],
                              out_path: str) -> List[str]:
    """
    plan = {"sequence":[...],
            "clip_ranges":[{"hook_id":"H1","use":[[0.0,6.2], ...]}, ...]}
    hooks_by_id: map hook_id -> hook dict
    Returns a list of shell commands: one per clip + final concat command.
    """
    cmds = []
    parts = []
    idx = 1
    for entry in plan.get("clip_ranges", []):
        hid = entry["hook_id"]
        if hid not in hooks_by_id:
            continue
        base = hooks_by_id[hid]
        for rng in entry.get("use", []):
            start = base["start"] + float(rng[0])
            dur = float(rng[1]) - float(rng[0])
            out = f"part_{idx:02d}.mp4"
            # Copy codecs for zero-reencode; switch to -c:v libx264 -c:a aac if you need re-encode
            cmd = f'ffmpeg -y -ss {start:.3f} -i "{src_path}" -t {dur:.3f} -c copy "{out}"'
            cmds.append(cmd)
            parts.append(out)
            idx += 1
    # concat list file
    concat_txt = "concat.txt"
    cmds.append(f'printf "" > {concat_txt}')  # ensure file exists (POSIX); on Windows, create manually
    # (write concat.txt in Python when you actually run)
    concat_cmd = 'ffmpeg -y -f concat -safe 0 -i concat.txt -c copy "{}"'.format(out_path)
    cmds.append(concat_cmd)
    return cmds

# --------------------------- demo scaffold ---------------------------

if __name__ == "__main__":
    # Minimal toy example — replace with your real transcript list:
    toy_transcript = [
        {"start": 0.0, "end": 2.2, "text": "Okay, here is the surprising part."},
        {"start": 2.2, "end": 5.8, "text": "Most people miss this because they start in the wrong place."},
        {"start": 5.8, "end": 9.0, "text": "What if I told you there is a simple rule anyone can apply?"},
        {"start": 9.0, "end": 14.0, "text": "Top 3 mistakes I made when learning fast."},
        {"start": 14.0, "end": 18.0, "text": "And then I realized the truth."},
        {"start": 18.0, "end": 23.0, "text": "So here is exactly what I did to fix it."},
    ]

    hooks = find_hooks(toy_transcript, window_s=10.0, hop_s=5.0, top_k=5)
    hooks = refine_hook_boundaries(hooks, toy_transcript,
                                   lead_pad=0.25, tail_pad=0.35,
                                   merge_next_if_cliff=True,
                                   max_refined_len_s=14.0)

    prompt = build_mix_prompt("Toy Video", hooks, target_len_s=30, max_clips=3)
    print("\n--- PROMPT TO SEND ---\n")
    print(prompt)

    hooks_by_id = {h["hook_id"]: h for h in hooks}
    # Example "plan" you would get back from ChatGPT:
    example_plan = {
        "sequence": ["H2", "H1", "H3"],
        "clip_ranges": [
            {"hook_id": "H2", "use": [[0.0, 6.0]]},
            {"hook_id": "H1", "use": [[0.5, 7.5]]},
            {"hook_id": "H3", "use": [[0.0, 8.0]]},
        ],
        "notes": "Start with a question, then the surprising reveal, then a concrete list."
    }
    cmds = ffmpeg_commands_from_plan("input.mp4", example_plan, hooks_by_id, "short_final.mp4")
    print("\n--- FFMPEG COMMANDS ---\n")
    for c in cmds:
        print(c)
