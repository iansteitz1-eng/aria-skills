---
name: ffmpeg-audio
description: The prod audio convention made declarative — coerce any container (.m4a/.mp3/.webm/.wav) to mono 16 kHz signed-16-bit PCM WAV (`-ac 1 -ar 16000 -c:a pcm_s16le`), the input shape voiceprint, diarization, whisper, and training pipelines expect. Four ops (normalize · trim · concat · probe) plus a YAML reconcile mode. Idempotent, dry-run by default (nothing runs without --apply). Use when the user says "normalize this audio", "make a 16k wav", "extract an enroll clip", "convert to mono 16k", "prep audio for whisper/diarization", or "batch-convert these recordings".
---

# ffmpeg-audio

One ffmpeg shape recurs across the voiceprint, diarization, whisper, and
training lanes: **mono · 16 kHz · signed-16-bit PCM WAV** —
`ffmpeg -ac 1 -ar 16000 -c:a pcm_s16le`. This skill is that convention as a
single idempotent CLI, so the same bytes come out every time regardless of who
runs it or what container went in.

**Defaults are the convention** (`SR=16000`, `CH=1`, `CODEC=pcm_s16le`). Change
them in one place at the top of `ffmpeg_audio.py` if a lane ever needs a
different target.

## Safety model

- **Dry-run by default.** Every op prints the exact `ffmpeg` command it *would*
  run and changes nothing until `--apply`.
- **Idempotent.** An output that already exists and is newer than its input(s)
  is **skipped** — re-running a batch is a no-op. `--force` rebuilds anyway.
- **Read-only `probe`** never writes.

## The four ops

1. **normalize** — any audio → mono 16k PCM WAV (the canonical convention).
   ```sh
   python3 ~/.claude/skills/ffmpeg-audio/ffmpeg_audio.py normalize output.m4a -o alice.wav --apply
   ```
   Batch a roster with globs + `--suffix` (no `-o`):
   ```sh
   python3 .../ffmpeg_audio.py normalize alice.* bob.* carol.* --suffix .16k.wav --apply
   ```

2. **trim** — slice `--start`/`--duration` then normalize (the enroll-clip
   pattern: `superwhisper/recordings/<ts>/output.wav` → `~/enroll/alice.wav`, 22s).
   ```sh
   python3 .../ffmpeg_audio.py trim output.wav --start 0 --duration 22 -o ~/enroll/alice.wav --apply
   ```

3. **concat** — join N inputs into one normalized WAV (filter_complex concat).
   ```sh
   python3 .../ffmpeg_audio.py concat a.wav b.wav c.wav -o joined.wav --apply
   ```

4. **probe** — ffprobe readout (codec · channels · rate · duration). Read-only.
   ```sh
   python3 .../ffmpeg_audio.py probe alice.wav
   ```

## Reconcile a YAML catalog

For a fixed set of jobs (e.g. the enroll roster), declare them once and
reconcile — idempotent, so it's safe to re-run after adding one person.

```sh
python3 .../ffmpeg_audio.py reconcile jobs.yaml            # dry-run
python3 .../ffmpeg_audio.py reconcile jobs.yaml --apply    # execute
```

See `examples/enroll_roster.yaml` for the shape:

```yaml
jobs:
  - op: trim
    input: ~/superwhisper/recordings/2026-06-05/output.wav
    start: 0
    duration: 22
    output: ~/enroll/alice.wav
  - op: normalize
    input: ~/recordings/bob.m4a
    output: ~/enroll/bob.wav
  - op: concat
    inputs: [~/clips/a.wav, ~/clips/b.wav]
    output: ~/enroll/merged.wav
```

## Flags

- `--apply` — actually run ffmpeg (default: dry-run preview)
- `--force` — rebuild even if the output is up-to-date
- `--json` — machine-readable result array (for chaining)
- `--suffix` — output name when `-o` is omitted (normalize/trim batch mode)

## Notes

- macOS: `brew install ffmpeg` · Ubuntu: `apt-get install -y ffmpeg`. The script
  hard-fails on a missing `ffmpeg`/`ffprobe` rather than running half a batch.
- Stdlib only for the four ops; `reconcile` needs PyYAML.
- Output dirs are created as needed. Inputs are glob-expanded (order-preserving,
  de-duped); a missing input surfaces as a per-job error, never silent.

## License

Apache 2.0
