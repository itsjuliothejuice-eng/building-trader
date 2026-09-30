"""Objective measurements used for decisions and for the QC report."""

import numpy as np
import pyloudnorm as pyln
from scipy.signal import resample_poly, welch

from .audio import db

# Octave-ish bands used for tonal balance, named the way engineers talk.
BANDS = [
    ("Sub", 20, 60), ("Bass", 60, 250), ("Low-mid", 250, 500), ("Mid", 500, 2000),
    ("Upper-mid", 2000, 4000), ("Presence", 4000, 8000), ("Air", 8000, 20000),
]


def lufs(audio, sr):
    """Integrated loudness (ITU-R BS.1770-4, gated). -inf for silence."""
    meter = pyln.Meter(sr)
    if audio.shape[1] < sr // 2:
        audio = np.pad(audio, ((0, 0), (0, sr // 2 - audio.shape[1])))
    with np.errstate(divide="ignore"):
        return float(meter.integrated_loudness(audio.T))


def true_peak(audio):
    """dBTP via 4x oversampling (BS.1770 method)."""
    return float(db(np.abs(resample_poly(audio, 4, 1, axis=1)).max()))


def short_term_lufs(audio, sr, window_s=3.0, hop_s=1.0):
    meter = pyln.Meter(sr, block_size=0.4)
    win, hop = int(window_s * sr), int(hop_s * sr)
    vals = []
    for start in range(0, max(1, audio.shape[1] - win + 1), hop):
        seg = audio[:, start:start + win]
        with np.errstate(divide="ignore"):
            vals.append(meter.integrated_loudness(seg.T))
    return np.array(vals)


def band_levels(audio, sr):
    """Relative energy per band in dB (normalized so the loudest band is 0)."""
    mono = audio.mean(axis=0)
    f, pxx = welch(mono, sr, nperseg=8192)
    levels = {}
    for name, lo, hi in BANDS:
        m = (f >= lo) & (f < min(hi, sr / 2))
        levels[name] = float(10 * np.log10(np.sum(pxx[m]) + 1e-20))
    top = max(levels.values())
    return {k: v - top for k, v in levels.items()}


def spectrum_curve(audio, sr, points=64):
    """Log-spaced smoothed spectrum (dB) for charts."""
    mono = audio.mean(axis=0)
    f, pxx = welch(mono, sr, nperseg=8192)
    edges = np.geomspace(25, min(20000, sr / 2 - 1), points + 1)
    centers, vals = [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (f >= lo) & (f < hi)
        if m.any():
            centers.append(float(np.sqrt(lo * hi)))
            vals.append(float(10 * np.log10(np.mean(pxx[m]) + 1e-20)))
    return centers, vals


def analyze(audio, sr):
    """Full metric set for a stereo buffer."""
    peak = float(db(np.abs(audio).max()))
    rms = float(db(np.sqrt(np.mean(audio ** 2))))
    mid = (audio[0] + audio[1]) / 2
    side = (audio[0] - audio[1]) / 2
    denom = np.sqrt(np.sum(audio[0] ** 2) * np.sum(audio[1] ** 2))
    corr = float(np.sum(audio[0] * audio[1]) / denom) if denom > 0 else 1.0
    stereo_mono = np.stack([mid, mid])
    st = short_term_lufs(audio, sr)
    st = st[np.isfinite(st)]
    integrated = lufs(audio, sr)
    return {
        "lufs": integrated,
        "true_peak": true_peak(audio),
        "sample_peak": peak,
        "rms": rms,
        "crest": peak - rms,
        # Loudness range proxy: spread of short-term loudness (10th-95th pct).
        "lra": float(np.percentile(st, 95) - np.percentile(st, 10)) if len(st) > 2 else 0.0,
        "correlation": corr,
        "side_ratio_db": float(db(np.sqrt(np.mean(side ** 2))) - db(np.sqrt(np.mean(mid ** 2)) + 1e-12)),
        "mono_loss_lu": float(integrated - lufs(stereo_mono, sr)),
        "clipped_samples": int(np.sum(np.abs(audio) >= 0.9999)),
        "bands": band_levels(audio, sr),
        "duration_s": audio.shape[1] / sr,
    }
