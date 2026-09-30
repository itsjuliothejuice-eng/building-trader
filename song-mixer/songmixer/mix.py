"""Stem mixing: gain staging -> per-role chain -> balance -> space -> bus."""

import numpy as np
import pedalboard as pb

from .analysis import lufs
from .audio import load, pad_to, is_mono, pan, band, duck, envelope_db, blocks_to_samples, undb, db
from .presets import ROLE_CHAINS, GENRES, balance_for

STAGE_LUFS = -20.0      # every stem is normalized here before processing
BUS_TARGET_LUFS = -18.0  # mix level handed to mastering (leaves headroom)
BUS_MAX_PEAK_DB = -6.0


def _eq_plugins(eq):
    out = []
    for kind, freq, gain, q in eq:
        if kind == "peak":
            out.append(pb.PeakFilter(cutoff_frequency_hz=freq, gain_db=gain, q=q))
        elif kind == "high_shelf":
            out.append(pb.HighShelfFilter(cutoff_frequency_hz=freq, gain_db=gain, q=q))
        elif kind == "low_shelf":
            out.append(pb.LowShelfFilter(cutoff_frequency_hz=freq, gain_db=gain, q=q))
    return out


def deess(audio, sr, max_cut_db=6.0):
    """Split-band de-esser: turns down only the 5-10 kHz band when sibilance spikes
    above the vocal's own typical level in that band."""
    sib = band(audio, 5000, 10000, sr)
    env, block = envelope_db(sib, sr, attack_ms=1, release_ms=60)
    active = env[env > -70]
    if len(active) == 0:
        return audio
    threshold = np.percentile(active, 80)
    gain_db = -np.clip((env - threshold) * 0.6, 0, max_cut_db)
    return (audio - sib) + sib * blocks_to_samples(gain_db, block, audio.shape[1])


def process_stem(audio, sr, role):
    chain = ROLE_CHAINS[role]
    plugins = [pb.HighpassFilter(cutoff_frequency_hz=chain["hpf"])]
    if chain.get("lpf"):
        plugins.append(pb.LowpassFilter(cutoff_frequency_hz=chain["lpf"]))
    plugins += _eq_plugins(chain["eq"])
    if chain.get("comp"):
        plugins.append(pb.Compressor(**chain["comp"]))
    out = pb.Pedalboard(plugins)(audio, sr)
    if chain.get("deess"):
        out = deess(out, sr)
    return out


def _gain_to(audio, sr, target):
    level = lufs(audio, sr)
    if not np.isfinite(level):
        return audio, None
    return audio * undb(target - level), level


def mix(stem_list, genre="pop", sr=48000, log=print):
    """stem_list: [(path, role)]. Returns (stereo_mix, stems_out, stem_info, notes)."""
    if genre not in GENRES:
        raise ValueError(f"Unknown genre '{genre}'. Options: {sorted(GENRES)}")
    settings = GENRES[genre]
    balance = balance_for(genre)

    loaded = []
    for path, role in stem_list:
        audio, _ = load(path, sr)
        loaded.append((path, role, audio))
    length = max(a.shape[1] for _, _, a in loaded)

    processed, notes = [], []
    spread_counter = {}
    for path, role, audio in loaded:
        audio = pad_to(audio, length)
        staged, original_lufs = _gain_to(audio, sr, STAGE_LUFS)
        if original_lufs is None:
            notes.append(f"Skipped silent stem: {path.name}")
            continue
        out = process_stem(staged, sr, role)
        out, _ = _gain_to(out, sr, STAGE_LUFS + balance[role])

        chain = ROLE_CHAINS[role]
        position = chain["pan"]
        if position is not None and is_mono(audio):
            if position == "spread":
                i = spread_counter.get(role, 0)
                spread_counter[role] = i + 1
                position = [-0.5, 0.5, -0.3, 0.3, -0.7, 0.7][i % 6]
            out = pan(out, position)
        processed.append(dict(name=path.name, role=role, audio=out, input_lufs=original_lufs,
                              target=balance[role],
                              pan=f"{position:+.2f}" if isinstance(position, float) else "as recorded"))
        log(f"  {path.name:<32} {role:<11} in {original_lufs:6.1f} LUFS -> {balance[role]:+.1f} LU vs vocal")

    by_role = lambda *roles: [p for p in processed if p["role"] in roles]
    total = lambda items: sum((p["audio"] for p in items), np.zeros((2, length), np.float32))

    # Kick/bass sidechain: bass dips a few dB on each kick so the low end doesn't pile up.
    kicks = total(by_role("kick"))
    if np.any(kicks) and settings["kick_duck_db"] > 0:
        for p in by_role("bass"):
            p["audio"] = duck(p["audio"], kicks, sr, settings["kick_duck_db"],
                              threshold_db=float(db(np.sqrt(np.mean(kicks ** 2)))) - 6,
                              attack_ms=2, release_ms=90)
        notes.append(f"Bass ducks up to {settings['kick_duck_db']} dB under the kick.")

    # Vocal pocket: carve 1-5 kHz out of the music only while the lead vocal sings.
    vocal = total(by_role("vocal_lead"))
    music = [p for p in processed if not p["role"].startswith("vocal")]
    if np.any(vocal) and music and settings["vocal_pocket_db"] > 0:
        v_env, _ = envelope_db(vocal, sr)
        v_thresh = float(np.percentile(v_env[v_env > -70], 30)) if np.any(v_env > -70) else -40
        for p in music:
            p["audio"] = duck(p["audio"], vocal, sr, settings["vocal_pocket_db"], v_thresh,
                              band_hz=(1000, 5000), attack_ms=20, release_ms=250)
        notes.append(f"Music dips up to {settings['vocal_pocket_db']} dB in 1-5 kHz under the lead vocal.")

    # Shared reverb bus fed by per-role sends, cleaned with HPF/LPF like a console return.
    send = sum((p["audio"] * ROLE_CHAINS[p["role"]]["reverb"] for p in processed),
               np.zeros((2, length), np.float32))
    reverb = pb.Pedalboard([
        pb.Reverb(room_size=0.55, damping=0.5, wet_level=1.0, dry_level=0.0, width=1.0),
        pb.HighpassFilter(cutoff_frequency_hz=300), pb.LowpassFilter(cutoff_frequency_hz=8000),
    ])(send, sr) if np.any(send) else send

    bus = total(processed) + reverb
    bus, _ = _gain_to(bus, sr, BUS_TARGET_LUFS)
    bus = pb.Pedalboard([pb.Compressor(threshold_db=-16, ratio=2.0, attack_ms=30, release_ms=200)])(bus, sr)
    bus, _ = _gain_to(bus, sr, BUS_TARGET_LUFS)
    peak = float(db(np.abs(bus).max()))
    if peak > BUS_MAX_PEAK_DB:
        bus = bus * undb(BUS_MAX_PEAK_DB - peak)
        notes.append(f"Mix bus trimmed {peak - BUS_MAX_PEAK_DB:.1f} dB to keep {BUS_MAX_PEAK_DB} dBFS headroom.")
    stems_out = [(p["name"], p["role"], p["audio"]) for p in processed] + [("Reverb Return.wav", "fx", reverb)]
    info = [{k: p[k] for k in ("name", "role", "input_lufs", "target", "pan")} for p in processed]
    return bus.astype(np.float32), stems_out, info, notes
