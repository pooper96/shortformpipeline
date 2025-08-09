# llm_mix.py
import os, json
from openai import OpenAI

def mix_and_order_clips(candidates, transcript, top_k=5):
    """Use GPT (or fallback) to order and pick the best subset of candidates."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️ No OpenAI API key found — returning first top_k candidates.")
        return candidates[:top_k]

    client = OpenAI(api_key=api_key)

    # Make a compact transcript for GPT
    preview_texts = []
    for c in candidates:
        segs = [seg["text"] for seg in transcript if seg["start"] >= c["start"] and seg["end"] <= c["end"]]
        preview_texts.append(f"[{c['start']}-{c['end']}s] {' '.join(segs).strip()}")

    system_prompt = (
        "You are a short-form content editor. From the provided candidate clips, "
        "choose the most compelling sequence for viral potential. "
        "Output a JSON list with start/end times, ordered for maximum engagement."
    )

    user_prompt = "Candidates:\n" + "\n".join(preview_texts) + f"\n\nPick top {top_k} clips."

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3
        )

        raw_text = resp.choices[0].message.content.strip()
        plan = json.loads(raw_text)
        return plan

    except Exception as e:
        print(f"⚠️ GPT call failed: {e}")
        return candidates[:top_k]
