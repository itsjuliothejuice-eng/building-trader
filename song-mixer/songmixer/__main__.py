"""Command line: python -m songmixer {mix,master,analyze,watch} ..."""

import argparse
import json
import sys
import time
from pathlib import Path

from pedalboard.io import AudioFile

from . import __version__
from .analysis import analyze, true_peak
from .audio import load, save, undb, AUDIO_EXTS
from .master import master, reference_lufs
from .mix import mix
from .presets import GENRES
from .report import write_report
from .stems import find_stems

SR = 48000


def _write_mp3(path, audio, sr, ceiling_db):
    """MP3 encoding adds overshoot, so decode, measure and re-encode with a trim
    until the delivered file itself meets the true-peak ceiling."""
    trim = 0.0
    for _ in range(4):
        with AudioFile(str(path), "w", sr, 2, quality="320k") as f:
            f.write(audio * undb(trim))
        decoded, _ = load(path, sr)
        over = true_peak(decoded) - ceiling_db
        if over <= 0:
            return trim
        trim -= over + 0.05
    return trim


def _finish(before, out_dir, name, args, notes, stems=None):
    """Master `before`, write deliverables and the QC report."""
    target = args.lufs
    ref = None
    if args.reference:
        ref_audio, _ = load(args.reference, SR)
        ref = (Path(args.reference).name, ref_audio)
        if args.lufs is None:
            target = max(reference_lufs(args.reference, SR), -9.0)
            notes.append(f"Loudness target taken from reference: {target:.1f} LUFS.")
    if target is None:
        target = GENRES[args.genre]["lufs"]

    print("Mastering...")
    after, steps = master(before, SR, target_lufs=target, ceiling_db=args.ceiling,
                          tilt=GENRES[args.genre]["tilt"], reference=args.reference, width=args.width)
    notes.append("Low end below 120 Hz collapsed to mono.")
    if "tonal" in steps:
        t = steps["tonal"]
        notes.append(f"Tonal tilt {t['measured_tilt']:.2f} → target {t['target_tilt']:.2f} dB/oct "
                     f"(low shelf {t['low_shelf_db']:+.1f} dB, high shelf {t['high_shelf_db']:+.1f} dB).")
    notes.append(f"Limiter drove {steps['loudness']['gain_db']:+.1f} dB into a true-peak ceiling of {args.ceiling} dBTP.")

    out_dir.mkdir(parents=True, exist_ok=True)
    save(out_dir / f"{name} - MASTER.wav", after, SR)
    mp3_trim = _write_mp3(out_dir / f"{name} - MASTER.mp3", after, SR, args.ceiling)
    if mp3_trim:
        notes.append(f"MP3 trimmed {mp3_trim:.2f} dB to keep encoder overshoot under {args.ceiling} dBTP.")

    b, a = analyze(before, SR), analyze(after, SR)
    verdict, rows = write_report(out_dir / f"{name} - QC Report.html", name, b, a, before, after, SR,
                                 target, args.ceiling, steps, notes, stems=stems, reference=ref)
    (out_dir / "settings.json").write_text(json.dumps(dict(
        version=__version__, genre=args.genre, target_lufs=target, ceiling_db=args.ceiling,
        reference=args.reference, width=args.width, steps=steps, stems=stems,
        before={k: v for k, v in b.items()}, after={k: v for k, v in a.items()},
        checks=[dict(check=r[0], result=r[1], status=r[2]) for r in rows]), indent=2, default=float))
    print(f"\nQC verdict: {verdict}")
    for n, v, s, _ in rows:
        print(f"  [{s.upper():4}] {n}: {v}")
    print(f"\nOutput: {out_dir}")
    return verdict


def cmd_mix(args):
    folder = Path(args.stems)
    stems = find_stems(folder)
    if not stems:
        sys.exit(f"No audio files found in {folder}")
    print(f"Mixing {len(stems)} stems as '{args.genre}':")
    bus, stems_out, info, notes = mix(stems, genre=args.genre, sr=SR)
    name = args.name or folder.name
    out_dir = Path(args.out or folder.parent / f"{name} - SongMixer")
    for stem_name, role, audio in stems_out:
        save(out_dir / "Processed Stems" / f"{Path(stem_name).stem} [{role}].wav", audio, SR)
    save(out_dir / f"{name} - MIX (unmastered).wav", bus, SR)
    return _finish(bus, out_dir, name, args, notes, stems=info)


def cmd_master(args):
    path = Path(args.file)
    audio, sr = load(path, SR)
    name = args.name or path.stem
    out_dir = Path(args.out or path.parent / f"{name} - SongMixer")
    return _finish(audio, out_dir, name, args, notes=[f"Mastered from stereo bounce {path.name}."])


def cmd_analyze(args):
    audio, sr = load(args.file)
    m = analyze(audio, sr)
    bands = m.pop("bands")
    for k, v in m.items():
        print(f"{k:>16}: {v:.2f}" if isinstance(v, float) else f"{k:>16}: {v}")
    for k, v in bands.items():
        print(f"{'band ' + k:>16}: {v:.1f} dB")


def cmd_watch(args):
    """Drop a stems folder or a bounce into the inbox; results appear in the outbox."""
    inbox, outbox = Path(args.inbox), Path(args.outbox or Path(args.inbox).parent / "outbox")
    inbox.mkdir(parents=True, exist_ok=True)
    done_dir = inbox / "_done"
    done_dir.mkdir(exist_ok=True)
    print(f"Watching {inbox} (Ctrl+C to stop). Results go to {outbox}")
    sizes = {}
    while True:
        for item in sorted(inbox.iterdir()):
            if item.name.startswith(("_", ".")):
                continue
            files = [item] if item.is_file() else [p for p in item.rglob("*") if p.is_file()]
            if item.is_file() and item.suffix.lower() not in AUDIO_EXTS:
                continue
            # Wait until Ableton has finished writing (size stable across two polls).
            size = sum(p.stat().st_size for p in files)
            if sizes.get(item) != size or size == 0:
                sizes[item] = size
                continue
            print(f"\n=== {item.name} ===")
            run = argparse.Namespace(**{**vars(args), "out": str(outbox / item.stem), "name": item.stem})
            try:
                if item.is_dir():
                    run.stems = str(item)
                    cmd_mix(run)
                else:
                    run.file = str(item)
                    cmd_master(run)
                item.rename(done_dir / item.name)
            except Exception as exc:  # keep watching even if one song fails
                print(f"FAILED {item.name}: {exc}")
                item.rename(done_dir / f"FAILED - {item.name}")
            sizes.pop(item, None)
        time.sleep(args.interval)


def main(argv=None):
    p = argparse.ArgumentParser(prog="songmixer", description="Automated mixing and mastering.")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--genre", default="pop", choices=sorted(GENRES))
        sp.add_argument("--reference", help="Commercial track to match (WAV/FLAC/AIFF)")
        sp.add_argument("--lufs", type=float, help="Loudness target (default: genre preset or reference)")
        sp.add_argument("--ceiling", type=float, default=-1.0, help="True-peak ceiling dBTP (default -1.0)")
        sp.add_argument("--width", type=float, default=1.0, help="Stereo width, 1.0 = unchanged")
        sp.add_argument("--out", help="Output folder")
        sp.add_argument("--name", help="Song name for output files")

    sp = sub.add_parser("mix", help="Mix a folder of stems, then master")
    sp.add_argument("stems")
    common(sp)
    sp.set_defaults(fn=cmd_mix)

    sp = sub.add_parser("master", help="Master a stereo bounce")
    sp.add_argument("file")
    common(sp)
    sp.set_defaults(fn=cmd_master)

    sp = sub.add_parser("analyze", help="Print loudness/peak/tonal metrics for a file")
    sp.add_argument("file")
    sp.set_defaults(fn=cmd_analyze)

    sp = sub.add_parser("watch", help="Auto-process anything dropped into an inbox folder")
    sp.add_argument("inbox")
    sp.add_argument("--outbox")
    sp.add_argument("--interval", type=float, default=5.0)
    common(sp)
    sp.set_defaults(fn=cmd_watch)

    args = p.parse_args(argv)
    sys.stdout.reconfigure(line_buffering=True)  # live progress in watch mode / logs
    args.fn(args)


if __name__ == "__main__":
    main()
