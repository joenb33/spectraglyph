from __future__ import annotations

import io
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

LOSSLESS_EXTS = {".wav", ".flac", ".aiff", ".aif"}
LOSSY_EXTS = {".mp3", ".m4a", ".aac", ".ogg", ".opus"}


@dataclass
class AudioData:
    samples: np.ndarray
    sample_rate: int

    @property
    def duration_s(self) -> float:
        return len(self.samples) / self.sample_rate if self.sample_rate else 0.0

    @property
    def channels(self) -> int:
        return 1 if self.samples.ndim == 1 else self.samples.shape[1]


def _ffmpeg_exe() -> str:
    from imageio_ffmpeg import get_ffmpeg_exe

    return get_ffmpeg_exe()


def load_audio(path: str | os.PathLike) -> AudioData:
    path = Path(path)
    ext = path.suffix.lower()

    if ext in LOSSLESS_EXTS:
        data, sr = sf.read(str(path), always_2d=False, dtype="float32")
        return AudioData(samples=data.astype(np.float32, copy=False), sample_rate=int(sr))

    # Lossy / compressed formats — decode via ffmpeg to float32 PCM.
    return _decode_with_ffmpeg(path)


def _decode_with_ffmpeg(path: Path) -> AudioData:
    import subprocess

    ffmpeg = _ffmpeg_exe()
    # Probe sample rate & channel count by asking ffmpeg to output a wav header.
    # Simpler: decode straight to 32-bit float PCM, stereo preserved, native sample rate.
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-f",
        "wav",
        "-acodec",
        "pcm_f32le",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=True)
    buf = io.BytesIO(proc.stdout)
    data, sr = sf.read(buf, always_2d=False, dtype="float32")
    return AudioData(samples=data.astype(np.float32, copy=False), sample_rate=int(sr))


def save_audio(
    path: str | os.PathLike,
    audio: AudioData,
    *,
    mp3_bitrate_kbps: int = 320,
) -> None:
    path = Path(path)
    ext = path.suffix.lower()
    path.parent.mkdir(parents=True, exist_ok=True)

    samples = _prep_for_save(audio.samples)

    if ext == ".wav":
        sf.write(str(path), samples, audio.sample_rate, subtype="PCM_16")
        return
    if ext == ".flac":
        sf.write(str(path), samples, audio.sample_rate, subtype="PCM_16")
        return
    if ext in LOSSY_EXTS:
        _encode_with_ffmpeg(path, samples, audio.sample_rate, mp3_bitrate_kbps)
        return
    raise ValueError(f"Unsupported output extension: {ext}")


def _prep_for_save(samples: np.ndarray) -> np.ndarray:
    # Clamp to [-1, 1] to avoid clipping when writing integer PCM.
    return np.clip(samples, -1.0, 1.0).astype(np.float32, copy=False)


def _encode_with_ffmpeg(
    path: Path, samples: np.ndarray, sr: int, bitrate_kbps: int
) -> None:
    import subprocess

    ffmpeg = _ffmpeg_exe()
    buf = io.BytesIO()
    sf.write(buf, samples, sr, format="WAV", subtype="FLOAT")
    buf.seek(0)

    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "wav",
        "-i",
        "pipe:0",
        "-b:a",
        f"{bitrate_kbps}k",
        str(path),
    ]
    subprocess.run(cmd, input=buf.read(), check=True)


def is_lossy(path: str | os.PathLike) -> bool:
    return Path(path).suffix.lower() in LOSSY_EXTS


def to_mono(samples: np.ndarray) -> np.ndarray:
    if samples.ndim == 1:
        return samples
    return samples.mean(axis=1).astype(samples.dtype, copy=False)
