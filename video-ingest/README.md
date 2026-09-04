# video-ingest

Pull metadata + transcript from any YouTube, Instagram, X/Twitter, TikTok, Vimeo, or other yt-dlp-supported video URL so Claude can actually "watch" it. Use when the user pastes a video link and asks "watch this", "what's this video about", "summarize this", "let's talk about this video", or any time a URL points at video content. First tries subtitles (fast, no GPU). Optional `--whisper` fallback transcribes audio locally via faster-whisper.

## Usage

```sh
python3 ~/.claude/skills/video-ingest/ingest.py "<url>"
```

---

_README generated from `SKILL.md`; the canonical contract lives there._  
Stdlib-first. Apache 2.0.
