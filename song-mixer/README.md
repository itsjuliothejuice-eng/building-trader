# SongMixer: automated mixing and mastering for Ableton Live 12

Drop in stems exported from Ableton and get back:

- **MASTER.wav** (24-bit, 48 kHz) and **MASTER.mp3** (320 kbps)
- **MIX (unmastered).wav**, the balanced mix before mastering
- **Processed Stems/**, each stem after EQ/compression/balance, ready to drag back into Ableton and tweak
- **QC Report.html**, a pass/warn/fail scorecard: loudness, true peak, clipping, squashing, mono compatibility, phase, tonal balance, before/after charts
- **settings.json**, every number the engine used, so you can compare versions

---

## 1. One-time setup (about 10 minutes)

1. Install **Python 3.10 or newer** from python.org. On Windows, check **"Add Python to PATH"** during install.
2. Unzip this folder somewhere permanent, e.g. `Documents/SongMixer`.
3. Open a terminal in that folder (Windows: in File Explorer, click the address bar, type `cmd`, press Enter. Mac: right-click the folder → *New Terminal at Folder*) and run:

   ```
   pip install -r requirements.txt
   ```

## 2. Export stems from Ableton Live 12

`File → Export Audio/Video` (Ctrl+Shift+R / Cmd+Shift+R):

| Setting | Value | Why |
|---|---|---|
| Rendered Track | **All Individual Tracks** | One WAV per track, all the same length |
| Render Start / Length | Song start (1.1.1) to the end, including reverb tails | Keeps every stem aligned |
| Include Return and Master Effects | **Off** for dry stems (SongMixer adds its own reverb). Leave **On** if your reverbs/delays are part of the sound. | |
| Normalize | **Off** | SongMixer does its own gain staging |
| File type / bit depth / rate | WAV, **24-bit**, 48000 Hz | |
| Dither | None | |

Also:

- **Bypass anything on the Master track** (limiters, Ozone, etc.) before exporting.
- **Name tracks clearly.** Roles are guessed from track names: `Kick`, `Snare`, `Clap`, `Hat`, `Perc`, `808`, `Bass`, `Lead Vox`, `BGV`, `Adlib`, `Keys`, `Piano`, `Guitar`, `Requinto`, `Pad`, `Strings`, `Synth`, `Acordeon`, `Brass`, `FX`, `Riser`…
- **Group tracks:** Ableton exports the group *and* the tracks inside it. Delete the group's WAV from the export folder, or mark it `"skip"` in `roles.json` (below), or it will be mixed twice. The exported `Master` file is skipped automatically.
- **Only have a stereo bounce?** On Live 12.3 or later, Suite includes stem separation: right-click the clip and use *Separate Stems to New Audio Tracks*, then export as above. Or just use `master` mode on the bounce.

## 3. Run it

**Mix + master a folder of stems:**
```
python -m songmixer mix "C:\Music\Exports\My Song" --genre reggaeton
```

**Master a stereo bounce only:**
```
python -m songmixer master "My Song.wav" --genre hiphop
```

**Match a commercial song you love (best results):**
```
python -m songmixer mix "My Song" --genre hiphop --reference "Reference Song.wav"
```
Use a WAV/FLAC/AIFF reference, not a YouTube rip. SongMixer then matches its tonal curve, width and loudness.

**Hands-free automation (watch folder):**
```
python -m songmixer watch "C:\Music\SongMixer Inbox" --genre regional
```
Leave it running. Export your Ableton stems into a new folder inside the inbox, or drop a bounce WAV in. The results appear in `outbox/`, and processed inputs move to `inbox/_done`. Double-click **Start Watch Folder** (`.bat` on Windows, `.command` on Mac) to launch it without typing.

**Check any file (yours or a commercial track):**
```
python -m songmixer analyze "Some Song.wav"
```

### Options

| Option | Default | Meaning |
|---|---|---|
| `--genre` | pop | `pop`, `hiphop`, `rnb`, `reggaeton`, `regional`, `rock`, `edm`: sets balance, sidechain depth, loudness and tonal targets |
| `--lufs` | genre preset | Loudness target. Streaming: -14. Competitive: -11 to -9. |
| `--ceiling` | -1.0 | True-peak ceiling (dBTP) |
| `--width` | 1.0 | Stereo width of the master (1.1 = 10% wider) |
| `--reference` | none | Commercial track to match |
| `--out`, `--name` | next to input | Output folder and song name |

### Fixing a wrong guess: `roles.json`

Put a `roles.json` in the stems folder:
```json
{ "Audio 7.wav": "guitar", "Chant.wav": "vocal_bg", "Drums Group.wav": "skip" }
```
Roles: `vocal_lead, vocal_bg, kick, snare, tops, drums, bass, keys, guitar, pad, synth, fx, other, skip`.

---

## What the engine does

**Mix**
1. **Gain staging.** Every stem is normalized to -20 LUFS so the processing behaves the same however hot you exported.
2. **Per-role channel strip.** High-pass, corrective EQ (mud cut, presence/air), compression, and a split-band de-esser on vocals.
3. **Balance.** Each role is set to a loudness relative to the lead vocal, per genre (e.g. hip-hop: kick -1, 808 -1.5, keys -9 LU).
4. **Panning.** Mono stems are placed by role; doubles, guitars and synths are spread L/R. Stereo stems keep their image.
5. **Sidechain.** The bass ducks under the kick, and the music dips 1-5 kHz only while the lead vocal sings (the "vocal pocket").
6. **Space.** A shared reverb bus with per-role sends, filtered like a console return.
7. **Bus glue.** 2:1 compression, then the mix is left at -18 LUFS / -6 dBFS headroom for mastering.

**Master**
1. Low end below 120 Hz is summed to mono.
2. Tonal balance: gentle tilt correction toward the genre target (max ±2 dB per shelf), or full reference matching with `--reference`.
3. Glue compression (1.5:1).
4. An oversampled soft-knee clipper, then a true-peak lookahead limiter, solved iteratively to land within 0.1 LU of the target.
5. The QC report flags a target it can't hit without crushing the song, instead of hiding it.

## Getting to "professional"

The presets are starting points. They get good through testing, the same way you'd prove a fix in the field:

1. **Blind A/B.** Have someone play you the SongMixer master and a version from another source (your own mix, LANDR, an engineer) level-matched and in random order. Log which one wins and why.
2. **Change one number at a time** in `songmixer/presets.py`, re-run, and compare `settings.json` + the QC report between versions.
3. **Keep a scorecard** per song: genre, reference, QC verdict, A/B result. Patterns in that log tell you which preset values to change for good.

## Test without real music

`python tests/make_test_song.py "Test Song"` writes a synthetic 7-stem export with deliberately messy levels. Then `python -m songmixer mix "Test Song" --genre hiphop`.
