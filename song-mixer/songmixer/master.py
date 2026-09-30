"""Mastering: low-end mono -> tonal balance -> glue -> width -> loudness + true-peak limiting."""

import tempfile
from pathlib import Path

import numpy as np
import pedalboard as pb
from scipy.signal import welch, resample_poly

from .analysis import lufs, true_peak
from .audio import load, save, band, undb

TILT_LO, TILT_HI = 100, 10000
MAX_SHELF_DB = 2.0  # never move either end of the spectrum more than this automatically


def spectral_tilt(audio, sr):
    """Slope of the spectrum in dB/octave between 100 Hz and 10 kHz (pink noise = -3)."""
    f, pxx = welch(audio.mean(axis=0), sr, nperseg=8192)
    edges = np.geomspace(TILT_LO, TILT_HI, 21)
    xs, ys = [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (f >= lo) & (f < hi)
        if m.any():
            xs.append(np.log2(np.sqrt(lo * hi)))
            ys.append(10 * np.log10(np.mean(pxx[m]) + 1e-20))
    return float(np.polyfit(xs, ys, 1)[0])


def mono_bass(audio, sr, below_hz=120):
    """Collapse stereo information below `below_hz` so the low end is solid on
    club systems, phone speakers and vinyl."""
    mid = (audio[0] + audio[1]) / 2
    side = (audio[0] - audio[1]) / 2
    side = side - band(side[None, :], None, below_hz, sr)[0]
    return np.stack([mid + side, mid - side]).astype(np.float32)


def stereo_width(audio, amount):
    if amount == 1.0:
        return audio
    mid = (audio[0] + audio[1]) / 2
    side = (audio[0] - audio[1]) / 2 * amount
    return np.stack([mid + side, mid - side]).astype(np.float32)


def tonal_balance(audio, sr, target_tilt):
    measured = spectral_tilt(audio, sr)
    octaves = np.log2(TILT_HI / TILT_LO)
    total_db = np.clip((target_tilt - measured) * octaves, -2 * MAX_SHELF_DB, 2 * MAX_SHELF_DB)
    # Split the correction around ~1 kHz: raise one end, lower the other.
    low, high = -total_db / 2, total_db / 2
    out = pb.Pedalboard([
        pb.LowShelfFilter(cutoff_frequency_hz=200, gain_db=float(low), q=0.7),
        pb.HighShelfFilter(cutoff_frequency_hz=5000, gain_db=float(high), q=0.7),
    ])(audio, sr)
    return out, dict(measured_tilt=measured, target_tilt=target_tilt, low_shelf_db=float(low),
                     high_shelf_db=float(high))


def soft_clip(audio, ceiling_db, knee_db=6.0):
    """4x-oversampled soft-knee clipper. Untouched below (ceiling - knee); above that,
    peaks are rounded off smoothly. Shaving the fastest transients here lets the
    limiter work less, which avoids the pumping a limiter alone produces on
    spiky kicks and 808s."""
    c, k = undb(ceiling_db), undb(ceiling_db - knee_db)
    up = resample_poly(audio, 4, 1, axis=1)
    mag = np.abs(up)
    over = mag > k
    up[over] = np.sign(up[over]) * (k + (c - k) * np.tanh((mag[over] - k) / (c - k)))
    return resample_poly(up, 1, 4, axis=1).astype(np.float32)


def loudness_and_limit(audio, sr, target_lufs, ceiling_db, *, max_push_db=15.0, log=print):
    """Push to the loudness target: soft clipper -> true-peak lookahead limiter.

    Solves for input gain with damped secant steps. If the limiter saturates
    (more gain no longer buys loudness) it stops and keeps the closest result
    instead of crushing the song; the QC report then flags the missed target."""
    limiter_ceiling = ceiling_db - 0.3  # margin for inter-sample overshoot

    def render(g):
        clipped = soft_clip(audio * undb(g), limiter_ceiling + 1.5)
        y = pb.BrickwallLimiter(ceiling_db=limiter_ceiling, release_ms=80, lookahead_ms=5,
                                true_peak=True)(clipped, sr)
        tp = true_peak(y)
        if tp > ceiling_db:
            y = y * undb(ceiling_db - tp - 0.05)
        return y, lufs(y, sr)

    gain0 = target_lufs - lufs(audio, sr)
    gain, prev = gain0, None
    best = None
    for _ in range(10):
        y, level = render(gain)
        err = target_lufs - level
        if best is None or abs(err) < abs(best[2]):
            best = (gain, y, err)
        if abs(err) < 0.1:
            break
        slope = 1.0
        if prev is not None and gain != prev[0]:
            slope = (level - prev[1]) / (gain - prev[0])
        if err > 0 and slope < 0.25 and prev is not None:
            break  # saturated: more gain no longer buys loudness
        prev = (gain, level)
        gain = float(np.clip(gain + np.clip(err / max(slope, 0.25), -6, 6), gain0 - 12, gain0 + max_push_db))
    gain, y, err = best
    # How hard the limiter worked: loudness it had to give back vs. the raw gain.
    limiting_db = float(lufs(audio * undb(gain), sr) - lufs(y, sr))
    if abs(err) >= 0.5:
        log(f"  WARNING: stopped {err:.1f} LU short of target; the limiter is saturated. "
            f"Lower --lufs or tame the peaks in the mix.")
    return y.astype(np.float32), dict(gain_db=float(gain), limiting_db=limiting_db,
                                      reached_target=bool(abs(err) < 0.5))


def _matchering(audio, sr, reference_path, log=print):
    """Reference mastering: match EQ curve, loudness and width to a commercial track.
    Matchering's own limiter brings it to the reference level; our true-peak stage
    then does the final, standards-compliant trim."""
    import matchering as mg
    mg.log(info_handler=lambda m: None, warning_handler=lambda m: log(f"  matchering: {m}"))
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "target.wav"
        dst = Path(tmp) / "matched.wav"
        save(src, audio, sr, subtype="FLOAT")
        mg.process(target=str(src), reference=str(reference_path),
                   results=[mg.Result(str(dst), "FLOAT", use_limiter=True, normalize=True)])
        matched, _ = load(dst, sr)
    n = audio.shape[1]
    matched = matched[:, :n] if matched.shape[1] >= n else np.pad(matched, ((0, 0), (0, n - matched.shape[1])))
    return matched


def master(audio, sr, target_lufs=-14.0, ceiling_db=-1.0, tilt=-4.0, reference=None,
           width=1.0, log=print):
    steps = {}
    x = mono_bass(audio, sr)
    if not reference:
        x, steps["tonal"] = tonal_balance(x, sr, tilt)
        t = steps["tonal"]
        log(f"  tilt {t['measured_tilt']:.2f} dB/oct -> target {tilt:.2f}: "
            f"low shelf {t['low_shelf_db']:+.1f} dB, high shelf {t['high_shelf_db']:+.1f} dB")
    # Glue: gentle, slow bus compression at a known level.
    x = x * undb(-18.0 - lufs(x, sr))
    x = pb.Pedalboard([pb.Compressor(threshold_db=-14, ratio=1.5, attack_ms=30, release_ms=150)])(x, sr)
    x = stereo_width(x, width)
    if reference:
        log(f"  matching to reference: {Path(reference).name}")
        x = _matchering(x, sr, reference, log)
        steps["reference"] = str(reference)
    x, steps["loudness"] = loudness_and_limit(x, sr, target_lufs, ceiling_db, log=log)
    log(f"  loudness: {lufs(x, sr):.1f} LUFS, true peak {true_peak(x):.2f} dBTP, "
        f"limiter working ~{steps['loudness']['limiting_db']:.1f} dB")
    return x, steps


def reference_lufs(path, sr):
    ref, _ = load(path, sr)
    return lufs(ref, sr)
