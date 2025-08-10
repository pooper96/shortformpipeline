# transcriber.py
from faster_whisper import WhisperModel
import os
import json
import yaml
import gc

def transcribe_audio(video_path, work_dir, config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    # Config knobs (override in config.yaml if you want)
    use_gpu = bool(cfg.get("use_gpu", True))
    whisper_cfg = cfg.get("whisper", {}) or {}
    model_size = whisper_cfg.get("model_size", "medium")        # "small", "medium", "large-v3", etc.
    beam_size = int(whisper_cfg.get("beam_size", 1))            # 1 = fastest, 5 = higher quality
    vad_filter = bool(whisper_cfg.get("vad_filter", True))      # skip silence
    vad_params = whisper_cfg.get("vad_parameters", {"min_silence_duration_ms": 500})
    compute_gpu = whisper_cfg.get("compute_type_gpu", "float16")
    compute_cpu = whisper_cfg.get("compute_type_cpu", "int8")

    # Try GPU first (CUDA), then fall back to CPU automatically
    model = None
    if use_gpu:
        try:
            model = WhisperModel("medium", device="cuda", compute_type="float16")
            print("✅ Using GPU (CUDA) for transcription")
        except Exception as e:
            print(f"⚠️ GPU init failed ({e}). Falling back to CPU.")
    if model is None:
        model = WhisperModel(model_size, device="cpu", compute_type=compute_cpu)
        print("🖥️ Using CPU for transcription")

    print("\n🔍 Transcribing...")
    segments, info = model.transcribe(
        video_path,
        beam_size=1,  # 1–2 is fastest; 5 = higher quality
        vad_filter=True,  # skip silence
        vad_parameters={"min_silence_duration_ms": 500},
        condition_on_previous_text=False,  # less context = less memory, faster
        temperature=0.0  # deterministic

    )

    transcript = []
    srt_lines = []
    for i, seg in enumerate(segments):
        start = float(seg.start)
        end = float(seg.end)
        text = (seg.text or "").strip()
        transcript.append({"start": start, "end": end, "text": text})
        srt_lines.append(f"{i+1}\n{_fmt_time(start)} --> {_fmt_time(end)}\n{text}\n")

    os.makedirs(work_dir, exist_ok=True)
    with open(os.path.join(work_dir, "transcript.json"), "w", encoding="utf-8") as f:
        json.dump(transcript, f, indent=2, ensure_ascii=False)
    with open(os.path.join(work_dir, "transcript.srt"), "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))

    # Free model memory between runs
    del model
    gc.collect()

    return transcript

def _fmt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02}:{m:02}:{s:02},{ms:03}"
