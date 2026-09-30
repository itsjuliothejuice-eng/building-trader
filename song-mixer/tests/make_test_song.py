"""Build a synthetic multitrack (like an Ableton 'All Individual Tracks' export)
so the pipeline can be tested without real music. Levels are deliberately messy."""

import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

SR, BPM, BARS = 44100, 95, 16
beat = 60 / BPM
n = int(SR * beat * 4 * BARS)
t = np.arange(n) / SR
rng = np.random.default_rng(7)


def env(length_s, decay):
    tt = np.arange(int(length_s * SR)) / SR
    return np.exp(-tt / decay)


def place(buf, sound, time_s):
    i = int(time_s * SR)
    j = min(n, i + len(sound))
    buf[i:j] += sound[: j - i]


def bp(x, lo, hi):
    return sosfilt(butter(2, [lo / (SR / 2), hi / (SR / 2)], "band", output="sos"), x)


def write(folder, name, x, gain):
    sf.write(folder / name, (x / np.abs(x).max() * gain).astype(np.float32), SR, subtype="PCM_24")


def build(folder):
    folder.mkdir(parents=True, exist_ok=True)
    kick, snare, hats, bass, keys, vox, bgv = (np.zeros(n) for _ in range(7))
    kt = np.arange(int(0.4 * SR)) / SR
    kick_snd = np.sin(2 * np.pi * (50 + 120 * np.exp(-kt / 0.03)) * kt) * env(0.4, 0.12)
    snare_snd = bp(rng.standard_normal(int(0.25 * SR)), 180, 9000) * env(0.25, 0.06)
    hat_snd = bp(rng.standard_normal(int(0.08 * SR)), 7000, 16000) * env(0.08, 0.015)
    roots = [55.0, 55.0, 43.65, 49.0]  # A, A, F, G
    for bar in range(BARS):
        b0 = bar * 4 * beat
        for k in (0, 1.5, 2.5):
            place(kick, kick_snd, b0 + k * beat)
        for s in (1, 3):
            place(snare, snare_snd, b0 + s * beat)
        for h in range(8):
            place(hats, hat_snd * (1 if h % 2 else 0.6), b0 + h * beat / 2)
        f = roots[bar % 4]
        nt = np.arange(int(4 * beat * SR)) / SR
        place(bass, np.sin(2 * np.pi * f * nt) * np.minimum(1, nt * 50) * np.exp(-nt / 3), b0)
        chord = sum(np.sin(2 * np.pi * f * 4 * r * nt) + 0.3 * np.sin(2 * np.pi * f * 8 * r * nt)
                    for r in (1, 1.26, 1.5))
        place(keys, chord * np.exp(-nt / 1.5), b0)
    # "Vocal": vibrato sawtooth through formant bands, phrased, with sibilant bursts.
    f0 = 220 * (1 + 0.01 * np.sin(2 * np.pi * 5.5 * t))
    saw = 2 * ((np.cumsum(f0) / SR) % 1) - 1
    formants = bp(saw, 600, 1100) + 0.7 * bp(saw, 1800, 2600) + 0.3 * bp(saw, 2800, 3600) + 0.4 * saw
    phrase = ((t % (beat * 8)) < beat * 6).astype(float)
    phrase = np.convolve(phrase, np.ones(2000) / 2000, mode="same")
    sib = np.zeros(n)
    for s_time in np.arange(beat * 2, t[-1], beat * 3):
        place(sib, bp(rng.standard_normal(int(0.09 * SR)), 5500, 10000) * 3, s_time)
    vox = formants * phrase + sib * phrase
    bgv = bp(2 * ((np.cumsum(f0 * 1.5) / SR) % 1) - 1, 500, 3000) * phrase * (t > t[-1] / 2)

    write(folder, "1-Kick.wav", kick, 0.9)
    write(folder, "2-Snare.wav", snare, 0.3)
    write(folder, "3-Hi Hat.wav", hats, 0.8)
    write(folder, "4-808.wav", bass, 0.95)
    write(folder, "5-Keys.wav", keys, 0.7)
    write(folder, "6-Lead Vox.wav", vox, 0.2)
    write(folder, "7-BGV Harmony.wav", bgv, 0.6)


if __name__ == "__main__":
    build(Path(sys.argv[1]))
