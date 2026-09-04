#!/usr/bin/env python3
"""
ffmpeg-audio — the prod audio convention, made declarative.

Across the voiceprint / diarization / whisper / training lanes the SAME ffmpeg
shape recurs: take any container and coerce it to **mono 16 kHz signed-16-bit
PCM WAV** — `ffmpeg -ac 1 -ar 16000 -c:a pcm_s16le`. This wraps that convention
(plus trim-to-clip, batch-roster, and concat) behind one idempotent, dry-run-by-
default CLI so the exact same bytes come out every time, no matter who runs it.

Four ops + a reconcile mode:

  normalize   any audio  -> mono 16k PCM WAV          (the canonical convention)
  trim        slice [--start/--duration] then normalize (enroll-clip extraction)
  concat      N inputs   -> one normalized WAV         (filter_complex concat)
  probe       read duration / channels / rate / codec  (ffprobe, read-only)
  reconcile   run a YAML catalog of the above jobs, idempotently

Idempotent: an output that already exists and is newer than its input(s) is
SKIPPED unless --force. Dry-run by default everywhere — nothing touches disk
until --apply.

No third-party deps for the four ops (stdlib only). `reconcile` needs PyYAML.

Usage
  ffmpeg_audio.py normalize in.m4a -o out.wav [--apply]
  ffmpeg_audio.py trim output.wav --start 0 --duration 22 -o alice.wav [--apply]
  ffmpeg_audio.py concat a.wav b.wav c.wav -o joined.wav [--apply]
  ffmpeg_audio.py probe in.wav
  ffmpeg_audio.py normalize alice.* bob.* carol.*  --suffix .16k.wav [--apply]
  ffmpeg_audio.py reconcile jobs.yaml [--apply]
  ffmpeg_audio.py --json normalize in.m4a -o out.wav

License: Apache 2.0
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ── the prod convention ──────────────────────────────────────────────────────
SR = 16000           # 16 kHz — TitaNet / whisper input rate
CH = 1               # mono
CODEC = "pcm_s16le"  # signed 16-bit little-endian PCM


# ── result model ─────────────────────────────────────────────────────────────
@dataclass
class JobResult:
    op: str
    inputs: list[str]
    output: str | None
    status: str                       # would-run | ran | skipped | error | probe
    cmd: list[str] = field(default_factory=list)
    detail: str = ""

    def as_dict(self) -> dict:
        return {
            "op": self.op,
            "inputs": self.inputs,
            "output": self.output,
            "status": self.status,
            "cmd": " ".join(self.cmd),
            "detail": self.detail,
        }


# ── preflight ────────────────────────────────────────────────────────────────
def _require_binaries() -> None:
    missing = [b for b in ("ffmpeg", "ffprobe") if shutil.which(b) is None]
    if missing:
        sys.exit(
            f"error: {', '.join(missing)} not found on PATH "
            f"(macOS: brew install ffmpeg · Ubuntu: apt-get install -y ffmpeg)"
        )


def _expand(patterns: list[str]) -> list[str]:
    """Glob-expand each input; preserve order, drop dupes, keep literals that
    don't glob (so a missing file surfaces as an error downstream, not silence)."""
    out: list[str] = []
    for p in patterns:
        hits = sorted(glob.glob(p)) if any(c in p for c in "*?[") else [p]
        for h in (hits or [p]):
            if h not in out:
                out.append(h)
    return out


def _newer_than_all(output: Path, inputs: list[Path]) -> bool:
    """True if output exists and is at least as new as every input."""
    if not output.exists():
        return False
    omt = output.stat().st_mtime
    return all(i.exists() and i.stat().st_mtime <= omt for i in inputs)


# ── ffprobe ──────────────────────────────────────────────────────────────────
def probe(path: str) -> dict:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries",
        "stream=codec_name,channels,sample_rate:format=duration",
        "-of", "json", path,
    ]
    try:
        raw = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True)
    except subprocess.CalledProcessError as e:
        return {"error": (e.stderr or "ffprobe failed").strip()}
    except FileNotFoundError:
        return {"error": "ffprobe not found"}
    data = json.loads(raw.stdout or "{}")
    stream = next((s for s in data.get("streams", []) if s.get("codec_name")), {})
    dur = data.get("format", {}).get("duration")
    return {
        "codec": stream.get("codec_name"),
        "channels": stream.get("channels"),
        "sample_rate": stream.get("sample_rate"),
        "duration_s": round(float(dur), 2) if dur else None,
    }


def _fmt_probe(p: dict) -> str:
    if "error" in p:
        return f"probe error: {p['error']}"
    return (
        f"{p.get('codec')} · {p.get('channels')}ch · "
        f"{p.get('sample_rate')}Hz · {p.get('duration_s')}s"
    )


# ── command builders ─────────────────────────────────────────────────────────
def _norm_tail() -> list[str]:
    return ["-ac", str(CH), "-ar", str(SR), "-c:a", CODEC]


def build_normalize(src: str, dst: str) -> list[str]:
    return ["ffmpeg", "-y", "-loglevel", "error", "-i", src, *_norm_tail(), dst]


def build_trim(src: str, dst: str, start: float | None, duration: float | None) -> list[str]:
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    # -ss before -i = fast input seek; accurate enough for clip extraction
    if start is not None:
        cmd += ["-ss", str(start)]
    cmd += ["-i", src]
    if duration is not None:
        cmd += ["-t", str(duration)]
    cmd += [*_norm_tail(), dst]
    return cmd


def build_concat(srcs: list[str], dst: str) -> list[str]:
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for s in srcs:
        cmd += ["-i", s]
    maps = "".join(f"[{i}:a]" for i in range(len(srcs)))
    filt = f"{maps}concat=n={len(srcs)}:v=0:a=1[out]"
    cmd += ["-filter_complex", filt, "-map", "[out]", *_norm_tail(), dst]
    return cmd


# ── runner ───────────────────────────────────────────────────────────────────
def _run(cmd: list[str], op: str, inputs: list[str], output: str,
         apply: bool, force: bool, planned: set[str] | None = None) -> JobResult:
    in_paths = [Path(i) for i in inputs]
    out_path = Path(output)

    # In a reconcile dry-run, an input produced by an EARLIER job in the same
    # catalog won't exist on disk yet — treat those as satisfied so chained
    # catalogs preview without spurious "input not found" errors.
    planned = planned or set()
    missing = [str(i) for i in in_paths if not i.exists() and str(i) not in planned]
    if missing:
        return JobResult(op, inputs, output, "error", cmd,
                         f"input not found: {', '.join(missing)}")

    if not force and _newer_than_all(out_path, in_paths):
        return JobResult(op, inputs, output, "skipped", cmd,
                         "output up-to-date (use --force to rebuild)")

    if not apply:
        return JobResult(op, inputs, output, "would-run", cmd, "dry-run")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=600, check=True)
    except subprocess.CalledProcessError as e:
        return JobResult(op, inputs, output, "error", cmd,
                         (e.stderr or "ffmpeg failed").strip()[:400])
    return JobResult(op, inputs, output, "ran", cmd, _fmt_probe(probe(output)))


# ── op dispatch (single-shot CLI) ────────────────────────────────────────────
def _default_out(src: str, suffix: str) -> str:
    return str(Path(src).with_suffix("")) + suffix


def op_normalize(args) -> list[JobResult]:
    srcs = _expand(args.inputs)
    results = []
    if args.output and len(srcs) > 1:
        sys.exit("error: -o/--output with multiple inputs is ambiguous; use --suffix")
    for s in srcs:
        dst = args.output or _default_out(s, args.suffix)
        results.append(_run(build_normalize(s, dst), "normalize", [s], dst,
                            args.apply, args.force))
    return results


def op_trim(args) -> list[JobResult]:
    srcs = _expand(args.inputs)
    if len(srcs) != 1:
        sys.exit("error: trim takes exactly one input")
    src = srcs[0]
    dst = args.output or _default_out(src, args.suffix)
    cmd = build_trim(src, dst, args.start, args.duration)
    return [_run(cmd, "trim", [src], dst, args.apply, args.force)]


def op_concat(args) -> list[JobResult]:
    srcs = _expand(args.inputs)
    if len(srcs) < 2:
        sys.exit("error: concat needs at least two inputs")
    if not args.output:
        sys.exit("error: concat requires -o/--output")
    return [_run(build_concat(srcs, args.output), "concat", srcs, args.output,
                 args.apply, args.force)]


def op_probe(args) -> list[JobResult]:
    results = []
    for s in _expand(args.inputs):
        p = probe(s)
        results.append(JobResult("probe", [s], None, "probe", [], _fmt_probe(p)))
    return results


# ── reconcile (YAML catalog) ─────────────────────────────────────────────────
def op_reconcile(args) -> list[JobResult]:
    try:
        import yaml
    except ImportError:
        sys.exit("error: reconcile needs PyYAML (pip install pyyaml)")
    catalog = Path(args.catalog)
    if not catalog.exists():
        sys.exit(f"error: catalog not found: {catalog}")
    doc = yaml.safe_load(catalog.read_text()) or {}
    jobs = doc.get("jobs", [])
    if not isinstance(jobs, list):
        sys.exit("error: catalog 'jobs' must be a list")

    results: list[JobResult] = []
    planned: set[str] = set()  # outputs earlier jobs will produce (dry-run chaining)
    for n, job in enumerate(jobs, 1):
        op = job.get("op", "normalize")
        out = job.get("output")
        if op == "normalize":
            src = job.get("input")
            if not src or not out:
                results.append(JobResult(op, [src or "?"], out, "error", [],
                                         f"job {n}: normalize needs input + output"))
                continue
            results.append(_run(build_normalize(src, out), op, [src], out,
                                args.apply, args.force, planned))
        elif op == "trim":
            src = job.get("input")
            if not src or not out:
                results.append(JobResult(op, [src or "?"], out, "error", [],
                                         f"job {n}: trim needs input + output"))
                continue
            cmd = build_trim(src, out, job.get("start"), job.get("duration"))
            results.append(_run(cmd, op, [src], out, args.apply, args.force, planned))
        elif op == "concat":
            srcs = job.get("inputs", [])
            if len(srcs) < 2 or not out:
                results.append(JobResult(op, srcs, out, "error", [],
                                         f"job {n}: concat needs inputs[2+] + output"))
                continue
            results.append(_run(build_concat(srcs, out), op, srcs, out,
                                args.apply, args.force, planned))
        else:
            results.append(JobResult(op, [], out, "error", [],
                                     f"job {n}: unknown op '{op}'"))
        if out:
            planned.add(out)
    return results


# ── reporting ────────────────────────────────────────────────────────────────
_ICON = {
    "ran": "✅", "would-run": "·", "skipped": "⏭", "error": "🔴", "probe": "🔎",
}


def report(results: list[JobResult], apply: bool, as_json: bool) -> int:
    if as_json:
        print(json.dumps([r.as_dict() for r in results], indent=2))
    else:
        mode = "APPLY" if apply else "DRY-RUN (use --apply to execute)"
        print(f"ffmpeg-audio · {mode}\n" + "─" * 72)
        for r in results:
            icon = _ICON.get(r.status, "?")
            tgt = r.output or (r.inputs[0] if r.inputs else "")
            print(f"  {icon} {r.op:9} {tgt}")
            if r.detail:
                print(f"        {r.detail}")
            if r.status in ("would-run",) and r.cmd:
                print(f"        $ {' '.join(r.cmd)}")
        print("─" * 72)
        c = {k: sum(1 for r in results if r.status == k) for k in _ICON}
        print(
            f"  {c['ran']} ran · {c['would-run']} would-run · "
            f"{c['skipped']} skipped · {c['error']} error"
        )
    return 1 if any(r.status == "error" for r in results) else 0


# ── argparse ─────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="ffmpeg_audio.py",
        description="Declarative mono-16k-PCM audio pipeline (the prod convention).",
    )
    ap.add_argument("--json", action="store_true", help="machine-readable output")

    def common(sp):
        sp.add_argument("--apply", action="store_true",
                        help="actually run ffmpeg (default: dry-run)")
        sp.add_argument("--force", action="store_true",
                        help="rebuild even if output is up-to-date")

    sub = ap.add_subparsers(dest="op", required=True)

    p_norm = sub.add_parser("normalize", help="any audio -> mono 16k PCM WAV")
    p_norm.add_argument("inputs", nargs="+")
    p_norm.add_argument("-o", "--output")
    p_norm.add_argument("--suffix", default=".16k.wav",
                        help="output suffix when -o omitted (default .16k.wav)")
    common(p_norm)

    p_trim = sub.add_parser("trim", help="slice then normalize (enroll-clip)")
    p_trim.add_argument("inputs", nargs=1)
    p_trim.add_argument("-o", "--output")
    p_trim.add_argument("--suffix", default=".clip.wav")
    p_trim.add_argument("--start", type=float, help="start seconds")
    p_trim.add_argument("--duration", type=float, help="clip length seconds")
    common(p_trim)

    p_cat = sub.add_parser("concat", help="N inputs -> one normalized WAV")
    p_cat.add_argument("inputs", nargs="+")
    p_cat.add_argument("-o", "--output", required=False)
    common(p_cat)

    p_probe = sub.add_parser("probe", help="ffprobe: codec/channels/rate/duration")
    p_probe.add_argument("inputs", nargs="+")

    p_rec = sub.add_parser("reconcile", help="run a YAML catalog of jobs")
    p_rec.add_argument("catalog")
    common(p_rec)

    args = ap.parse_args(argv)
    _require_binaries()

    dispatch = {
        "normalize": op_normalize,
        "trim": op_trim,
        "concat": op_concat,
        "probe": op_probe,
        "reconcile": op_reconcile,
    }
    results = dispatch[args.op](args)
    apply = getattr(args, "apply", False)
    return report(results, apply, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
