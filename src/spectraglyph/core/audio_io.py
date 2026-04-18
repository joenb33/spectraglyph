from __future__ import annotations

import io
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

LOSSLESS_EXTS = {".wav", ".flac", ".aiff", ".aif"}
LOSSY_EXTS = {".mp3", ".m4a", ".aac", ".ogg", ".opus"}

# If duration or file size exceeds these, the UI may offer loading only a segment first.
LARGE_FILE_DURATION_S = 120.0
LARGE_FILE_SIZE_BYTES = 40 * 1024 * 1024


@dataclass(frozen=True)
class AudioFileInfo:
    """Cheap metadata without decoding all PCM samples."""

    duration_s: float
    sample_rate: int
    size_bytes: int


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


def probe_audio_file(path: str | os.PathLike) -> AudioFileInfo:
    """Read duration and sample rate without loading all samples (fast)."""
    path = Path(path)
    size = path.stat().st_size
    ext = path.suffix.lower()
    if ext in LOSSLESS_EXTS:
        info = sf.info(str(path))
        return AudioFileInfo(
            duration_s=float(info.duration),
            sample_rate=int(info.samplerate),
            size_bytes=size,
        )
    duration_s, sr = _probe_compressed_duration_sr(path)
    return AudioFileInfo(duration_s=duration_s, sample_rate=sr, size_bytes=size)


def _probe_compressed_duration_sr(path: Path) -> tuple[float, int]:
    """Parse ffmpeg -i stderr for Duration and audio sample rate."""
    ffmpeg = _ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-i",
        str(path),
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    err = (proc.stderr or "") + (proc.stdout or "")
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", err)
    if not m:
        raise RuntimeError("Could not read audio duration (ffmpeg).")
    h, mi, s = m.groups()
    duration_s = int(h) * 3600 + int(mi) * 60 + float(s)
    sr_m = re.search(r"(\d{3,6})\s*Hz", err)
    sr = int(sr_m.group(1)) if sr_m else 48_000
    return duration_s, sr


def load_audio(
    path: str | os.PathLike,
    *,
    start_s: float = 0.0,
    duration_s: float | None = None,
) -> AudioData:
    """Load PCM. If ``duration_s`` is None, load from ``start_s`` to end of file.

    Partial loads avoid decoding gigabytes when you only need the first minutes.
    """
    path = Path(path)
    ext = path.suffix.lower()
    start_s = max(0.0, float(start_s))

    if ext in LOSSLESS_EXTS:
        data = _load_soundfile_segment(path, start_s, duration_s)
    else:
        data = _decode_ffmpeg_segment(path, start_s, duration_s)
    if data.samples.size == 0:
        raise ValueError("No audio in the selected range.")
    return data


def _load_soundfile_segment(
    path: Path, start_s: float, duration_s: float | None
) -> AudioData:
    info = sf.info(str(path))
    sr = int(info.samplerate)
    total_frames = int(info.frames)
    start_f = min(int(start_s * sr), total_frames)
    if start_f >= total_frames:
        raise ValueError("Start time is past the end of the file.")
    if duration_s is None:
        stop_f = total_frames
    else:
        stop_f = min(total_frames, start_f + max(1, int(float(duration_s) * sr)))
    data, _sr = sf.read(
        str(path),
        start=start_f,
        stop=stop_f,
        always_2d=False,
        dtype="float32",
    )
    return AudioData(samples=data.astype(np.float32, copy=False), sample_rate=sr)


def _decode_ffmpeg_segment(
    path: Path, start_s: float, duration_s: float | None
) -> AudioData:
    ffmpeg = _ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{start_s:.6f}",
        "-i",
        str(path),
    ]
    if duration_s is not None:
        cmd += ["-t", f"{float(duration_s):.6f}"]
    cmd += ["-f", "wav", "-acodec", "pcm_f32le", "-"]
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
