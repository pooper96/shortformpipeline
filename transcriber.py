from faster_whisper import WhisperModel
import os
import json
import yaml

def transcribe_audio(video_path, work_dir, config_path):
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    use_gpu = config.get("use_gpu", True)
    model = WhisperModel("medium", device="cpu", compute_type="int8")

    print("\n🔍 Transcribing...")
    segments, info = model.transcribe(video_path, beam_size=5)

    transcript = []
    srt_lines = []
    for i, seg in enumerate(segments):
        transcript.append({"start": seg.start, "end": seg.end, "text": seg.text})
        srt_lines.append(f"{i + 1}\n{format_time(seg.start)} --> {format_time(seg.end)}\n{seg.text.strip()}\n")

    with open(os.path.join(work_dir, "transcript.json"), "w") as f:
        json.dump(transcript, f, indent=2)
    with open(os.path.join(work_dir, "transcript.srt"), "w") as f:
        f.write("\n".join(srt_lines))

    return transcript

def format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"
