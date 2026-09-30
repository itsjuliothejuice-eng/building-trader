"""Stem roles, per-role processing chains, and genre balance targets.

Everything here is a starting point meant to be tuned by ear. Change a number,
re-run, A/B the result. The QC report shows what each change did.
"""

# Filename keywords -> role. Checked in order; first match wins, so vocals are
# matched before "lead" (synth) and "808" before "kick".
ROLE_KEYWORDS = [
    ("vocal_bg", ["bgv", "backing", "harmony", "harm", "adlib", "ad-lib", "double", "dbl", "choir vox", "bg vox"]),
    ("vocal_lead", ["lead vox", "leadvox", "lead vocal", "vocal", "vox", "voice", "rap", "verse", "hook"]),
    ("bass", ["808", "bass", "sub"]),
    ("kick", ["kick", "kik", "bd"]),
    ("snare", ["snare", "clap", "rim", "snr"]),
    ("tops", ["hat", "hh", "hihat", "cymbal", "ride", "crash", "shaker", "tamb", "perc", "conga", "bongo", "guiro", "timbal"]),
    ("drums", ["drum", "beat", "loop", "break", "kit"]),
    ("keys", ["piano", "keys", "rhodes", "organ", "epiano", "wurli"]),
    ("guitar", ["guitar", "gtr", "requinto", "bajo sexto", "acoustic"]),
    ("pad", ["pad", "string", "strings", "choir", "atmos", "texture"]),
    ("synth", ["synth", "lead", "pluck", "arp", "bell", "brass", "horn", "sax", "trumpet", "accordion", "acordeon"]),
    ("fx", ["fx", "riser", "sweep", "impact", "noise", "transition", "vinyl"]),
]

# Per-role processing. EQ entries: (type, freq_hz, gain_db, q).
# comp: threshold is relative to the stem's level after it is normalized to
# -20 LUFS, so the same preset works no matter how hot the stem was exported.
ROLE_CHAINS = {
    "vocal_lead": dict(hpf=90, eq=[("peak", 300, -2.0, 1.0), ("peak", 3000, 2.0, 0.8), ("high_shelf", 10000, 2.0, 0.7)],
                       comp=dict(threshold_db=-24, ratio=3.0, attack_ms=5, release_ms=80), deess=True,
                       pan=0.0, reverb=0.14),
    "vocal_bg": dict(hpf=150, eq=[("peak", 300, -3.0, 1.0), ("high_shelf", 9000, 1.0, 0.7)],
                     comp=dict(threshold_db=-26, ratio=4.0, attack_ms=5, release_ms=100), deess=True,
                     pan="spread", reverb=0.25),
    "kick": dict(hpf=30, eq=[("peak", 60, 1.5, 1.0), ("peak", 350, -3.0, 1.2), ("peak", 4000, 1.5, 1.0)],
                 comp=dict(threshold_db=-18, ratio=4.0, attack_ms=10, release_ms=60), pan=0.0, reverb=0.0),
    "snare": dict(hpf=80, eq=[("peak", 200, 1.0, 1.0), ("peak", 500, -2.0, 1.2), ("peak", 5000, 2.0, 1.0)],
                  comp=dict(threshold_db=-20, ratio=4.0, attack_ms=8, release_ms=80), pan=0.0, reverb=0.10),
    "tops": dict(hpf=300, eq=[("high_shelf", 10000, 1.0, 0.7)],
                 comp=dict(threshold_db=-22, ratio=2.0, attack_ms=5, release_ms=60), pan=0.25, reverb=0.05),
    "drums": dict(hpf=30, eq=[("peak", 400, -2.0, 1.0)],
                  comp=dict(threshold_db=-20, ratio=2.0, attack_ms=20, release_ms=100), pan=None, reverb=0.04),
    "bass": dict(hpf=30, lpf=9000, eq=[("peak", 250, -2.0, 1.0), ("peak", 800, 1.0, 1.0)],
                 comp=dict(threshold_db=-24, ratio=4.0, attack_ms=15, release_ms=120), pan=0.0, reverb=0.0),
    "keys": dict(hpf=100, eq=[("peak", 300, -2.0, 1.0)],
                 comp=dict(threshold_db=-24, ratio=2.0, attack_ms=15, release_ms=150), pan=None, reverb=0.12),
    "guitar": dict(hpf=100, lpf=12000, eq=[("peak", 250, -2.0, 1.0), ("peak", 3000, 1.0, 1.0)],
                   comp=dict(threshold_db=-24, ratio=2.5, attack_ms=10, release_ms=120), pan="spread", reverb=0.10),
    "pad": dict(hpf=150, lpf=14000, eq=[("peak", 400, -2.0, 1.0)],
                comp=dict(threshold_db=-26, ratio=2.0, attack_ms=30, release_ms=200), pan=None, reverb=0.15),
    "synth": dict(hpf=120, eq=[("peak", 350, -1.5, 1.0)],
                  comp=dict(threshold_db=-24, ratio=2.0, attack_ms=10, release_ms=120), pan="spread", reverb=0.12),
    "fx": dict(hpf=150, eq=[], comp=None, pan=None, reverb=0.20),
    "other": dict(hpf=40, eq=[], comp=dict(threshold_db=-24, ratio=2.0, attack_ms=15, release_ms=150),
                  pan=None, reverb=0.08),
}

# Loudness of each role relative to the lead vocal (LU). 0 = as loud as the vocal.
_BASE_BALANCE = {
    "vocal_lead": 0.0, "vocal_bg": -8.0, "kick": -2.0, "snare": -4.0, "tops": -10.0, "drums": -3.0,
    "bass": -3.0, "keys": -8.0, "guitar": -7.0, "pad": -12.0, "synth": -8.0, "fx": -14.0, "other": -9.0,
}

GENRES = {
    # balance overrides, sidechain settings, master loudness target and tonal tilt target (dB/oct)
    "pop":       dict(balance={}, kick_duck_db=2.0, vocal_pocket_db=2.0, lufs=-14.0, tilt=-4.0),
    "hiphop":    dict(balance={"kick": -1.0, "bass": -1.5, "keys": -9.0}, kick_duck_db=3.0,
                      vocal_pocket_db=2.5, lufs=-12.0, tilt=-4.5),
    "rnb":       dict(balance={"bass": -2.0, "keys": -7.0, "pad": -10.0}, kick_duck_db=2.0,
                      vocal_pocket_db=2.0, lufs=-13.0, tilt=-4.5),
    "reggaeton": dict(balance={"kick": -1.0, "snare": -3.0, "tops": -8.0, "bass": -2.0}, kick_duck_db=3.0,
                      vocal_pocket_db=2.0, lufs=-11.0, tilt=-4.0),
    "regional":  dict(balance={"bass": -4.0, "guitar": -5.0, "synth": -6.0, "drums": -4.0}, kick_duck_db=1.0,
                      vocal_pocket_db=2.0, lufs=-12.0, tilt=-3.5),
    "rock":      dict(balance={"guitar": -4.0, "drums": -2.0, "snare": -2.5}, kick_duck_db=1.5,
                      vocal_pocket_db=1.5, lufs=-11.0, tilt=-3.5),
    "edm":       dict(balance={"kick": 0.0, "bass": -2.0, "synth": -4.0, "vocal_lead": 0.0}, kick_duck_db=6.0,
                      vocal_pocket_db=2.0, lufs=-9.0, tilt=-4.0),
}


def balance_for(genre):
    table = dict(_BASE_BALANCE)
    table.update(GENRES[genre]["balance"])
    return table
