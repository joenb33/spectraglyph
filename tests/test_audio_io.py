import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from spectraglyph.core.audio_io import load_audio, probe_audio_file


def test_probe_and_partial_load_wav():
    sr = 48_000
    sec = 5.0
    n = int(sr * sec)
    samples = (np.sin(np.linspace(0, 440 * 2 * np.pi, n, dtype=np.float32)) * 0.1).astype(
        np.float32
    )
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "clip.wav"
        sf.write(str(path), samples, sr, subtype="PCM_16")
        info = probe_audio_file(path)
        assert abs(info.duration_s - sec) < 0.05
        assert info.sample_rate == sr
        part = load_audio(path, start_s=1.0, duration_s=2.0)
        assert abs(part.duration_s - 2.0) < 0.05
        assert part.sample_rate == sr
