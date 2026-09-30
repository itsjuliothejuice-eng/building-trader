"""Loading, saving and small signal helpers shared by every stage."""

from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly, butter, sosfiltfilt

AUDIO_EXTS = {".wav", ".aif", ".aiff", ".flac"}


def load(path, sr=None):
    """Load audio as float32 array shaped (2, n). Mono is duplicated to stereo."""
    data, file_sr = sf.read(str(path), dtype="float32", always_2d=True)
    data = data.T
    if data.shape[0] == 1:
        data = np.repeat(data, 2, axis=0)
    elif data.shape[0] > 2:
        data = data[:2]
    if sr and file_sr != sr:
        g = np.gcd(int(sr), int(file_sr))
        data = resample_poly(data, sr // g, file_sr // g, axis=1).astype(np.float32)
        file_sr = sr
    return data, file_sr


def save(path, audio, sr, subtype="PCM_24"):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio.T, sr, subtype=subtype)


def db(x):
    return 20 * np.log10(np.maximum(x, 1e-12))


def undb(d):
    return 10 ** (d / 20)


def pad_to(audio, n):
    if audio.shape[1] >= n:
        return audio[:, :n]
    return np.pad(audio, ((0, 0), (0, n - audio.shape[1])))


def is_mono(audio, tol=1e-4):
    """True when left and right are effectively the same signal."""
    diff = np.abs(audio[0] - audio[1]).max()
    return diff <= tol * max(np.abs(audio).max(), 1e-9)


def pan(audio, position):
    """Constant-power pan of a mono-ish stem. position: -1 (L) .. +1 (R)."""
    mono = audio.mean(axis=0)
    angle = (position + 1) * np.pi / 4
    return np.stack([mono * np.cos(angle), mono * np.sin(angle)]) * np.sqrt(2)


def band(audio, lo, hi, sr):
    """Zero-phase band split, so `audio - band(...)` reconstructs the rest exactly."""
    nyq = sr / 2
    if lo and hi:
        sos = butter(4, [lo / nyq, min(hi / nyq, 0.99)], btype="band", output="sos")
    elif lo:
        sos = butter(4, lo / nyq, btype="high", output="sos")
    else:
        sos = butter(4, hi / nyq, btype="low", output="sos")
    return sosfiltfilt(sos, audio, axis=-1).astype(np.float32)


def envelope_db(signal, sr, block_ms=10, attack_ms=5, release_ms=120):
    """Block RMS envelope in dB with attack/release smoothing, one value per block."""
    mono = signal.mean(axis=0) if signal.ndim == 2 else signal
    block = max(1, int(sr * block_ms / 1000))
    n_blocks = int(np.ceil(len(mono) / block))
    padded = np.pad(mono, (0, n_blocks * block - len(mono)))
    rms = np.sqrt(np.mean(padded.reshape(n_blocks, block) ** 2, axis=1))
    env = db(rms)
    a = np.exp(-block_ms / max(attack_ms, 1e-3))
    r = np.exp(-block_ms / max(release_ms, 1e-3))
    out = np.empty_like(env)
    prev = env[0]
    for i, v in enumerate(env):
        coef = a if v > prev else r
        prev = coef * prev + (1 - coef) * v
        out[i] = prev
    return out, block


def blocks_to_samples(gain_db_blocks, block, n):
    """Interpolate a per-block gain curve (dB) to a per-sample linear gain."""
    centers = np.arange(len(gain_db_blocks)) * block + block / 2
    return undb(np.interp(np.arange(n), centers, gain_db_blocks)).astype(np.float32)


def duck(target, sidechain, sr, depth_db, threshold_db, band_hz=None,
         attack_ms=5, release_ms=150):
    """Sidechain ducking. Reduces `target` (optionally only a frequency band of it)
    by up to `depth_db` whenever `sidechain` rises above `threshold_db`."""
    env, block = envelope_db(sidechain, sr, attack_ms=attack_ms, release_ms=release_ms)
    over = np.clip((env - threshold_db) / 12.0, 0, 1)  # full depth 12 dB over threshold
    gain = blocks_to_samples(-depth_db * over, block, target.shape[1])
    if band_hz is None:
        return target * gain
    part = band(target, band_hz[0], band_hz[1], sr)
    return (target - part) + part * gain
