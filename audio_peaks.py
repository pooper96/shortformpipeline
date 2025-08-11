import numpy as np, librosa, os, subprocess

def ensure_wav(src_video: str, wav_path: str, sr=16000):
    if os.path.exists(wav_path):
        return wav_path
    # extract mono wav
    subprocess.run([
        "ffmpeg","-y","-i",src_video,
        "-ac","1","-ar",str(sr),
        wav_path
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return wav_path

def energy_peaks(audio_path, sr_target=16000, frame_ms=250, hop_ms=125, zscore=1.2):
    y, sr = librosa.load(audio_path, sr=sr_target, mono=True)
    frame = int(sr*frame_ms/1000)
    hop = int(sr*hop_ms/1000)
    rms = librosa.feature.rms(y=y, frame_length=frame, hop_length=hop).flatten()
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop, n_fft=frame)
    mu, sd = rms.mean(), rms.std() + 1e-9
    peaks = [(float(t), float(r)) for t, r in zip(times, rms) if (r-mu)/sd >= zscore]
    return peaks
