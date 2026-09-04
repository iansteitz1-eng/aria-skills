#!/usr/bin/env python3
"""
video-ingest: pull metadata + transcript from any video URL yt-dlp supports.

Default flow:
  1. yt-dlp --skip-download for metadata + auto/manual subtitles
  2. If no subs, fall back to audio-only download + faster-whisper transcription
  3. Cache the cleaned result at /tmp/video-ingest-cache/<id>.json

Usage:
  python3 ingest.py <url> [--whisper] [--timestamps] [--no-cache] [--lang en]
  python3 ingest.py <url> --json        # machine-readable
  python3 ingest.py <url> --brief       # metadata + first 800 chars only

Supports: youtube, youtu.be, instagram, x.com / twitter, tiktok, vimeo,
          facebook, reddit, twitch, and ~1000 other sites yt-dlp handles.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CACHE_DIR = Path("/tmp/video-ingest-cache")
CACHE_DIR.mkdir(exist_ok=True)


def vid_key(url: str) -> str:
    # Prefer the actual provider ID when we can extract it; otherwise hash.
    for pat in (r"(?:v=|youtu\.be/|/shorts/|/reel/|/status/)([A-Za-z0-9_-]{6,})",):
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def run(
    cmd: list[str], cwd: str | None = None, check: bool = False
) -> tuple[int, str, str]:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed: {p.stderr}")
    return p.returncode, p.stdout, p.stderr


def fetch_metadata(url: str) -> dict:
    rc, out, err = run(
        [
            "yt-dlp",
            "--skip-download",
            "--no-warnings",
            "--dump-single-json",
            url,
        ]
    )
    if rc != 0:
        raise RuntimeError(f"yt-dlp metadata failed: {err.strip()[:400]}")
    j = json.loads(out)
    return {
        "id": j.get("id"),
        "title": j.get("title"),
        "uploader": j.get("uploader") or j.get("channel"),
        "duration": j.get("duration"),
        "view_count": j.get("view_count"),
        "upload_date": j.get("upload_date"),
        "description": j.get("description") or "",
        "url": j.get("webpage_url") or url,
        "thumbnail": j.get("thumbnail"),
        "_subtitle_langs": list((j.get("subtitles") or {}).keys()),
        "_autocaption_langs": list((j.get("automatic_captions") or {}).keys()),
    }


def vtt_to_text(vtt_path: Path, with_timestamps: bool) -> str:
    raw = vtt_path.read_text(errors="ignore").splitlines()
    out, last = [], None
    ts_line = None
    for line in raw:
        s = line.strip()
        if not s or s.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        if "-->" in s:
            ts_line = s.split(" ")[0] if with_timestamps else None
            continue
        if s.isdigit():
            continue
        cleaned = re.sub(r"<[^>]+>", "", s).strip()
        if not cleaned or cleaned == last:
            continue
        last = cleaned
        if with_timestamps and ts_line:
            out.append(f"[{ts_line}] {cleaned}")
            ts_line = None
        else:
            out.append(cleaned)
    return "\n".join(out)


def try_subtitles(url: str, workdir: Path, lang: str) -> str | None:
    rc, out, err = run(
        [
            "yt-dlp",
            "--skip-download",
            "--write-auto-subs",
            "--write-subs",
            "--sub-langs",
            f"{lang}.*,{lang}",
            "--sub-format",
            "vtt",
            "-o",
            "%(id)s.%(ext)s",
            url,
        ],
        cwd=str(workdir),
    )
    if rc != 0:
        return None
    vtts = sorted(workdir.glob("*.vtt"), key=lambda p: p.stat().st_size, reverse=True)
    if not vtts:
        return None
    return vtt_to_text(vtts[0], with_timestamps=False)


def try_whisper(url: str, workdir: Path) -> str | None:
    rc, out, err = run(
        [
            "yt-dlp",
            "-x",
            "--audio-format",
            "mp3",
            "--no-warnings",
            "-o",
            "audio.%(ext)s",
            url,
        ],
        cwd=str(workdir),
    )
    audio = workdir / "audio.mp3"
    if rc != 0 or not audio.exists():
        return None
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    # base.en is fast on CPU; bump to small/medium if quality is an issue
    model_size = os.environ.get("VIDEO_INGEST_WHISPER_MODEL", "base.en")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(audio), vad_filter=True)
    return "\n".join(seg.text.strip() for seg in segments if seg.text.strip())


def ingest(
    url: str,
    *,
    use_whisper_fallback: bool,
    with_timestamps: bool,
    lang: str,
    use_cache: bool,
) -> dict:
    key = vid_key(url)
    cache_path = CACHE_DIR / f"{key}.json"
    if use_cache and cache_path.exists():
        return json.loads(cache_path.read_text())

    meta = fetch_metadata(url)
    transcript, source = None, None

    with tempfile.TemporaryDirectory() as td:
        wd = Path(td)
        # Prefer auto/manual subs in the requested lang or any en variant
        if meta["_subtitle_langs"] or meta["_autocaption_langs"]:
            transcript = try_subtitles(url, wd, lang)
            if transcript:
                source = "subtitles"
        if not transcript and use_whisper_fallback:
            transcript = try_whisper(url, wd)
            if transcript:
                source = "whisper"

    result = {
        **{k: v for k, v in meta.items() if not k.startswith("_")},
        "transcript": transcript,
        "transcript_source": source,
        "transcript_chars": len(transcript or ""),
    }
    if use_cache:
        cache_path.write_text(json.dumps(result, indent=2))
    return result


def render_text(r: dict, brief: bool) -> str:
    lines = []
    lines.append(f"TITLE      {r.get('title')}")
    lines.append(f"UPLOADER   {r.get('uploader')}")
    if r.get("duration"):
        m, s = divmod(int(r["duration"]), 60)
        h, m = divmod(m, 60)
        dur = f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"
        lines.append(f"DURATION   {dur}")
    if r.get("upload_date"):
        d = r["upload_date"]
        lines.append(f"UPLOADED   {d[:4]}-{d[4:6]}-{d[6:8]}")
    if r.get("view_count"):
        lines.append(f"VIEWS      {r['view_count']:,}")
    lines.append(f"URL        {r.get('url')}")
    lines.append("")
    if r.get("description"):
        lines.append("DESCRIPTION")
        desc = r["description"].strip()
        if brief and len(desc) > 600:
            desc = desc[:600] + " …[truncated]"
        lines.append(desc)
        lines.append("")
    t = r.get("transcript")
    if t:
        lines.append(
            f"TRANSCRIPT  ({r.get('transcript_source')}, {r.get('transcript_chars')} chars)"
        )
        if brief and len(t) > 800:
            t = t[:800] + " …[truncated — re-run without --brief for full text]"
        lines.append(t)
    else:
        lines.append(
            "TRANSCRIPT  (none available — try --whisper for audio transcription)"
        )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Pull metadata + transcript from a video URL."
    )
    ap.add_argument("url")
    ap.add_argument(
        "--whisper",
        action="store_true",
        help="Fall back to local faster-whisper if subtitles are missing.",
    )
    ap.add_argument(
        "--timestamps",
        action="store_true",
        help="Keep [hh:mm:ss] markers in the transcript (subtitles only).",
    )
    ap.add_argument(
        "--lang", default="en", help="Subtitle language root (default: en)."
    )
    ap.add_argument("--no-cache", action="store_true", help="Bypass /tmp cache.")
    ap.add_argument("--json", action="store_true", help="Emit raw JSON.")
    ap.add_argument(
        "--brief", action="store_true", help="Truncate description + transcript."
    )
    args = ap.parse_args()

    if not shutil.which("yt-dlp"):
        print("ERROR: yt-dlp not on PATH", file=sys.stderr)
        return 2

    try:
        r = ingest(
            args.url,
            use_whisper_fallback=args.whisper,
            with_timestamps=args.timestamps,
            lang=args.lang,
            use_cache=not args.no_cache,
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(r, indent=2))
    else:
        print(render_text(r, brief=args.brief))
    return 0


if __name__ == "__main__":
    sys.exit(main())
