---
name: video-ingest
description: Pull metadata + transcript from any YouTube, Instagram, X/Twitter, TikTok, Vimeo, or other yt-dlp-supported video URL so Claude can actually "watch" it. Use when the user pastes a video link and asks "watch this", "what's this video about", "summarize this", "let's talk about this video", or any time a URL points at video content. First tries subtitles (fast, no GPU). Optional `--whisper` fallback transcribes audio locally via faster-whisper.
---

# Video Ingest

I cannot watch video. This skill turns a video URL into text I can reason over — title, uploader, duration, description, and the full transcript — so the conversation can actually be about the content of the video.

## Steps

1. **Run the collector.** Pass the URL as-is — yt-dlp handles shortened forms, redirects, query strings, and ~1000 sites:
   ```sh
   python3 ~/.claude/skills/video-ingest/ingest.py "<url>"
   ```

2. **Flags worth knowing:**
   - `--brief` — metadata + first 800 chars of transcript. Use this first when the user just wants a quick take; re-run without `--brief` if they want to go deep.
   - `--whisper` — if the video has no subtitles (common on Instagram reels, some X posts, raw uploads), download the audio and transcribe with local faster-whisper. Slower (CPU, ~1× realtime on `base.en`) but works offline. Skip unless needed — most YouTube content has auto-captions.
   - `--timestamps` — keep `[hh:mm:ss]` markers in the transcript (subtitles only, ignored on whisper).
   - `--lang xx` — subtitle language root (default `en`). Use when the source is non-English.
   - `--json` — machine-readable. Use when piping into another skill or saving structured.
   - `--no-cache` — bypass the `/tmp/video-ingest-cache/` cache. Default behavior caches per video-id so re-asking is instant.

3. **Read the report.** Sections in order: TITLE, UPLOADER, DURATION, UPLOADED, VIEWS, URL, DESCRIPTION, TRANSCRIPT. The transcript line shows the source (`subtitles` vs `whisper`) and total char count so you know how much you're reasoning over.

4. **Then talk about the video.** Don't just dump the transcript back at the user — that's what they pasted the link to avoid. Summarize the thesis, pull the 3-5 most load-bearing points, and connect it to whatever context they brought to the conversation (a project, a doctrine memory, a current build). If the user wants verbatim quotes, fetch them from the transcript text in your context.

## Supported sources

yt-dlp handles: youtube, youtu.be, youtube shorts, instagram (reels + posts), x.com / twitter, tiktok, vimeo, facebook, reddit (v.redd.it), twitch clips, soundcloud, and ~1000 more. If a site fails, the error message will say so explicitly — don't retry blindly.

## Notes

- Subtitle-first by design. Auto-captions on YouTube are good enough for content reasoning even with the occasional homophone. Don't reach for whisper unless subtitles genuinely aren't there.
- Cache lives at `/tmp/video-ingest-cache/<id>.json`. Survives until the box reboots. Manually clear with `rm -rf /tmp/video-ingest-cache` if a video was re-uploaded and you need a fresh pull.
- Whisper model defaults to `base.en` (fast, low quality). Override with `VIDEO_INGEST_WHISPER_MODEL=small.en` or `medium.en` env var for better accuracy on hard audio.
- For private/auth-walled videos (Instagram private accounts, paid YouTube), yt-dlp can take a `--cookies-from-browser` flag, but this skill doesn't expose it. If you need that, extend the script — don't try to work around it in the shell.
- Output goes to stdout. Capture into a file with `> /tmp/foo.txt` if a transcript is gigantic and you want to grep it instead of loading into context.
