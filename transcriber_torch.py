# transcriber_torch.py
import os, json, yaml, gc
import torch
import whisper  # from openai-whisper

def transcribe_audio(video_path, work_dir, config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    wcfg = cfg.get("whisper", {}) or {}
    model_size = wcfg.get("model_size", "small")  # small = fast; try medium later

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"✅ Using {device.upper()} via PyTorch for transcription")

    model = whisper.load_model(model_size, device=device)
    # deterministic + a bit faster
    result = model.transcribe(
        video_path,
        verbose=False,
        temperature=0.0,
        condition_on_previous_text=False,
        no_speech_threshold=0.6,   # skip low-energy
        logprob_threshold=-1.0
    )

    segments = result.get("segments", [])
    os.makedirs(work_dir, exist_ok=True)

    transcript, srt_lines = [], []
    for i, seg in enumerate(segments):
        s, e = float(seg["start"]), float(seg["end"])
        text = (seg.get("text") or "").strip()
        transcript.append({"start": s, "end": e, "text": text})
        srt_lines.append(f"{i+1}\n{_fmt(s)} --> {_fmt(e)}\n{text}\n")

    with open(os.path.join(work_dir, "transcript.json"), "w", encoding="utf-8") as f:
        json.dump(transcript, f, indent=2, ensure_ascii=False)
    with open(os.path.join(work_dir, "transcript.srt"), "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))

    del model; gc.collect()
    return transcript

def _fmt(t):
    h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    return f"{h:02}:{m:02}:{s:02},{ms:03}"
