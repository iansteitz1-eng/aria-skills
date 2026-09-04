# ffmpeg-audio

The prod audio convention — **mono · 16 kHz · signed-16-bit PCM WAV**
(`ffmpeg -ac 1 -ar 16000 -c:a pcm_s16le`) — as one idempotent, dry-run-by-default
CLI. This is the exact input shape that TitaNet/voiceprint, NeMo diarization,
whisper, and the training corpus all expect; the skill stops you from hand-typing
(and drifting) that ffmpeg line in every session.

## Usage

```sh
python3 ffmpeg_audio.py normalize in.m4a -o out.wav --apply
python3 ffmpeg_audio.py trim rec.wav --start 0 --duration 22 -o alice.wav --apply
python3 ffmpeg_audio.py concat a.wav b.wav -o joined.wav --apply
python3 ffmpeg_audio.py probe in.wav
python3 ffmpeg_audio.py normalize alice.* bob.* --suffix .16k.wav --apply
python3 ffmpeg_audio.py reconcile examples/enroll_roster.yaml --apply
```

Drop `--apply` on any op to preview the exact ffmpeg command without running it.

## Why

Mined from the transcripts: the `-ac 1 -ar 16000 -c:a pcm_s16le` shape appeared
across 17 sessions in the voiceprint / diarization / whisper / training lanes,
always hand-rolled. Same convention, every time → a skill.

## License

Apache 2.0
