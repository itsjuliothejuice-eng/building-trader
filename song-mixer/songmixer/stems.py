"""Find stems in a folder and decide what each one is."""

import json
import re
from pathlib import Path

from .audio import AUDIO_EXTS
from .presets import ROLE_KEYWORDS, ROLE_CHAINS

OVERRIDE_FILE = "roles.json"


def classify(name):
    """Guess a role from a filename such as '3-Lead Vox.wav' or 'Song 808.wav'."""
    text = re.sub(r"[_\-\.]+", " ", Path(name).stem.lower())
    # Ableton's "All Individual Tracks" export also renders the Master track;
    # mixing it back in would double everything.
    if re.search(r"(^|\s)master$", text.strip()):
        return "skip"
    padded = f" {text} "
    for role, words in ROLE_KEYWORDS:
        for w in words:
            # Short keywords must match a whole word ("bd" shouldn't hit "abdul").
            if (len(w) <= 3 and re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", padded)) or \
               (len(w) > 3 and w in text):
                return role
    return "other"


def find_stems(folder):
    """Return [(path, role)]. A roles.json in the folder overrides guesses:
    {"Track 7.wav": "guitar", "Chant.wav": "vocal_bg", "Drums Group.wav": "skip"}
    Use "skip" for group/bus tracks whose children were also exported."""
    folder = Path(folder)
    overrides = {}
    if (folder / OVERRIDE_FILE).exists():
        overrides = json.loads((folder / OVERRIDE_FILE).read_text())
        bad = {k: v for k, v in overrides.items() if v not in ROLE_CHAINS and v != "skip"}
        if bad:
            raise ValueError(f"Unknown roles in {OVERRIDE_FILE}: {bad}. Valid: {sorted(ROLE_CHAINS)}")
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in AUDIO_EXTS)
    found = [(p, overrides.get(p.name, classify(p.name))) for p in files]
    for p, role in found:
        if role == "skip":
            print(f"  skipping {p.name}")
    return [(p, role) for p, role in found if role != "skip"]
