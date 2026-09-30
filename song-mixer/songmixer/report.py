"""QC scorecard: every master gets pass/warn/fail checks and before/after charts."""

import html
from datetime import datetime

import numpy as np

from .analysis import BANDS, spectrum_curve, short_term_lufs


def checks(after, target_lufs, ceiling_db, steps):
    lim = steps.get("loudness", {}).get("limiting_db", 0.0)
    plr = after["true_peak"] - after["lufs"]
    rows = [
        ("Integrated loudness", f"{after['lufs']:.1f} LUFS (target {target_lufs:.1f})",
         "pass" if abs(after["lufs"] - target_lufs) <= 0.5 else "fail",
         "Streaming services turn loud masters down; -14 is Spotify/YouTube reference."),
        ("True peak", f"{after['true_peak']:.2f} dBTP (ceiling {ceiling_db:.1f})",
         "pass" if after["true_peak"] <= ceiling_db + 0.05 else "fail",
         "Above -1 dBTP can distort when converted to MP3/AAC."),
        ("Clipped samples", str(after["clipped_samples"]),
         "pass" if after["clipped_samples"] == 0 else "fail", "Any full-scale samples mean digital clipping."),
        ("Clipper + limiter reduction", f"~{lim:.1f} dB",
         "pass" if lim <= 4 else ("warn" if lim <= 7 else "fail"),
         "Over ~4 dB the mix is being squashed to hit the target. Lower the LUFS target or fix the mix."),
        ("Peak-to-loudness ratio", f"{plr:.1f} dB",
         "pass" if plr >= 8 else ("warn" if plr >= 6 else "fail"),
         "Punch/dynamics. Under 8 dB starts sounding flat and fatiguing."),
        ("Mono compatibility", f"{after['mono_loss_lu']:.1f} LU lost in mono",
         "pass" if after["mono_loss_lu"] <= 1.5 else ("warn" if after["mono_loss_lu"] <= 3 else "fail"),
         "How much quieter it gets on a phone speaker or club mono system."),
        ("Stereo correlation", f"{after['correlation']:.2f}",
         "pass" if after["correlation"] >= 0.3 else ("warn" if after["correlation"] >= 0 else "fail"),
         "Below 0 means phase problems; parts will cancel in mono."),
        ("Low end vs. mids", f"{after['bands']['Bass'] - after['bands']['Mid']:+.1f} dB",
         "pass" if -2 <= after["bands"]["Bass"] - after["bands"]["Mid"] <= 12 else "warn",
         "Bass band (60-250 Hz) relative to mids. Outside this range usually sounds muddy or thin."),
    ]
    return rows


def _polyline(xs, ys, x_of, y_of):
    return " ".join(f"{x_of(x):.1f},{y_of(y):.1f}" for x, y in zip(xs, ys))


def _spectrum_svg(series, w=720, h=260):
    pad = 36
    all_y = [v for _, (_, ys), _ in series for v in ys]
    top, bottom = max(all_y) + 3, max(all_y) - 60
    x_of = lambda f: pad + (np.log10(f) - np.log10(25)) / (np.log10(20000) - np.log10(25)) * (w - 2 * pad)
    y_of = lambda v: pad / 2 + (top - np.clip(v, bottom, top)) / (top - bottom) * (h - pad * 1.5)
    grid = "".join(
        f'<line x1="{x_of(f):.1f}" y1="{pad/2}" x2="{x_of(f):.1f}" y2="{h-pad}" class="grid"/>'
        f'<text x="{x_of(f):.1f}" y="{h-pad+16}" class="tick">{lbl}</text>'
        for f, lbl in [(50, "50"), (100, "100"), (250, "250"), (1000, "1k"), (4000, "4k"), (10000, "10k")])
    lines = "".join(f'<polyline points="{_polyline(xs, ys, x_of, y_of)}" class="{cls}"/>'
                    for _, (xs, ys), cls in series)
    legend = "".join(f'<span class="key {cls}">{html.escape(name)}</span>' for name, _, cls in series)
    return f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Spectrum">{grid}{lines}</svg><div class="legend">{legend}</div>'


def _loudness_svg(series, w=720, h=200):
    pad = 36
    xs_max = max(len(ys) for _, ys, _ in series)
    finite = [v for _, ys, _ in series for v in ys if np.isfinite(v)]
    top, bottom = max(finite) + 2, max(min(finite), max(finite) - 30) - 2
    x_of = lambda i: pad + i / max(xs_max - 1, 1) * (w - 2 * pad)
    y_of = lambda v: pad / 2 + (top - np.clip(v, bottom, top)) / (top - bottom) * (h - pad * 1.5)
    lines = "".join(
        f'<polyline points="{_polyline(range(len(ys)), [v if np.isfinite(v) else bottom for v in ys], x_of, y_of)}" class="{cls}"/>'
        for _, ys, cls in series)
    ticks = "".join(f'<text x="{pad-6}" y="{y_of(v)+4:.1f}" class="tick" text-anchor="end">{v:.0f}</text>'
                    f'<line x1="{pad}" y1="{y_of(v):.1f}" x2="{w-pad}" y2="{y_of(v):.1f}" class="grid"/>'
                    for v in np.linspace(bottom + 2, top - 2, 4))
    legend = "".join(f'<span class="key {cls}">{html.escape(n)}</span>' for n, _, cls in series)
    return f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Loudness over time">{ticks}{lines}</svg><div class="legend">{legend}</div>'


def write_report(path, title, before, after, before_audio, after_audio, sr, target_lufs, ceiling_db,
                 steps, notes, stems=None, reference=None):
    rows = checks(after, target_lufs, ceiling_db, steps)
    fails = sum(r[2] == "fail" for r in rows)
    warns = sum(r[2] == "warn" for r in rows)
    verdict = "READY TO RELEASE" if fails == 0 and warns == 0 else ("REVIEW" if fails == 0 else "NEEDS WORK")
    verdict_cls = "pass" if verdict.startswith("READY") else ("warn" if fails == 0 else "fail")

    spec = [("Before (mix)", spectrum_curve(before_audio, sr), "s1"), ("After (master)", spectrum_curve(after_audio, sr), "s2")]
    if reference is not None:
        spec.append(("Reference", spectrum_curve(reference[1], sr), "s3"))
    # Align curves at 1 kHz so we compare shape, not loudness.
    aligned = []
    for name, (xs, ys), cls in spec:
        i = int(np.argmin(np.abs(np.array(xs) - 1000)))
        aligned.append((name, (xs, [y - ys[i] for y in ys]), cls))
    loud = [("Before", short_term_lufs(before_audio, sr), "s1"), ("After", short_term_lufs(after_audio, sr), "s2")]

    metric_rows = "".join(
        f"<tr><td>{k}</td><td>{before[key]:.2f}</td><td>{after[key]:.2f}</td></tr>"
        for k, key in [("Integrated LUFS", "lufs"), ("True peak dBTP", "true_peak"), ("Crest factor dB", "crest"),
                       ("Loudness range LU", "lra"), ("Stereo correlation", "correlation"),
                       ("Mono loss LU", "mono_loss_lu")])
    band_rows = "".join(f"<tr><td>{n} ({lo}-{hi} Hz)</td><td>{before['bands'][n]:.1f}</td><td>{after['bands'][n]:.1f}</td></tr>"
                        for n, lo, hi in BANDS)
    check_rows = "".join(f'<tr><td>{html.escape(n)}</td><td>{html.escape(v)}</td>'
                         f'<td><span class="badge {s}">{s.upper()}</span></td><td class="why">{html.escape(w)}</td></tr>'
                         for n, v, s, w in rows)
    stem_rows = "".join(f"<tr><td>{html.escape(s['name'])}</td><td>{s['role']}</td><td>{s['input_lufs']:.1f}</td>"
                        f"<td>{s['target']:+.1f}</td><td>{s['pan']}</td></tr>" for s in (stems or []))
    note_items = "".join(f"<li>{html.escape(n)}</li>" for n in notes)

    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>QC Report</title>
<style>
:root {{ --bg:#f7f7f5; --card:#fff; --text:#1b1b1b; --muted:#666; --line:#e2e2de;
  --pass:#1f7a3f; --warn:#a36200; --fail:#b3261e; --s1:#8a8a8a; --s2:#2563eb; --s3:#c2410c; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#121212; --card:#1c1c1c; --text:#eee; --muted:#9a9a9a;
  --line:#2e2e2e; --pass:#4ade80; --warn:#fbbf24; --fail:#f87171; --s1:#777; --s2:#60a5fa; --s3:#fb923c; }} }}
body {{ margin:0; background:var(--bg); color:var(--text); font:15px/1.5 system-ui, sans-serif; }}
main {{ max-width:900px; margin:0 auto; padding:24px 16px 64px; }}
h1 {{ font-size:22px; margin:0 0 4px; }} h2 {{ font-size:16px; margin:28px 0 8px; }}
.sub {{ color:var(--muted); font-size:13px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px; overflow-x:auto; }}
.verdict {{ font-size:20px; font-weight:700; color:var(--{verdict_cls}); }}
table {{ width:100%; border-collapse:collapse; font-size:14px; }}
td, th {{ text-align:left; padding:6px 8px; border-bottom:1px solid var(--line); vertical-align:top; }}
th {{ color:var(--muted); font-weight:600; font-size:12px; text-transform:uppercase; }}
.why {{ color:var(--muted); font-size:13px; }}
.badge {{ font-size:11px; font-weight:700; padding:2px 8px; border-radius:99px; border:1px solid currentColor; }}
.badge.pass {{ color:var(--pass); }} .badge.warn {{ color:var(--warn); }} .badge.fail {{ color:var(--fail); }}
svg {{ width:100%; height:auto; }} polyline {{ fill:none; stroke-width:2; }}
polyline.s1 {{ stroke:var(--s1); }} polyline.s2 {{ stroke:var(--s2); }} polyline.s3 {{ stroke:var(--s3); stroke-dasharray:5 4; }}
.grid {{ stroke:var(--line); }} .tick {{ fill:var(--muted); font-size:11px; text-anchor:middle; }}
.legend {{ display:flex; gap:16px; font-size:13px; color:var(--muted); margin-top:6px; }}
.key::before {{ content:""; display:inline-block; width:14px; height:3px; margin-right:6px; vertical-align:middle; }}
.key.s1::before {{ background:var(--s1); }} .key.s2::before {{ background:var(--s2); }} .key.s3::before {{ background:var(--s3); }}
</style></head><body><main>
<h1>{html.escape(title)}</h1>
<div class="sub">Generated {datetime.now():%Y-%m-%d %H:%M} · target {target_lufs:.1f} LUFS / {ceiling_db:.1f} dBTP</div>
<h2>Verdict</h2>
<div class="card"><div class="verdict">{verdict}</div><div class="sub">{fails} fail · {warns} warn · {len(rows)-fails-warns} pass</div></div>
<h2>Quality checks</h2>
<div class="card"><table><tr><th>Check</th><th>Result</th><th>Status</th><th>Why it matters</th></tr>{check_rows}</table></div>
<h2>Tonal balance (aligned at 1 kHz)</h2>
<div class="card">{_spectrum_svg(aligned)}</div>
<h2>Short-term loudness over time (LUFS)</h2>
<div class="card">{_loudness_svg(loud)}</div>
<h2>Before / after</h2>
<div class="card"><table><tr><th>Metric</th><th>Before</th><th>After</th></tr>{metric_rows}</table></div>
<h2>Band energy (dB relative to loudest band)</h2>
<div class="card"><table><tr><th>Band</th><th>Before</th><th>After</th></tr>{band_rows}</table></div>
{"<h2>Stems</h2><div class='card'><table><tr><th>File</th><th>Role</th><th>Input LUFS</th><th>Level vs vocal</th><th>Pan</th></tr>" + stem_rows + "</table></div>" if stems else ""}
<h2>What the engine did</h2>
<div class="card"><ul>{note_items}</ul></div>
</main></body></html>"""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    return verdict, rows
