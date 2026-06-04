#!/usr/bin/env python3
"""
session_cabinet.py — Claude Code session filing system.

Scans ~/.claude/projects/**/*.jsonl and files every session into a
human-navigable, date-anchored archive:

    <CABINET>/Year/Month[/Day-burst]/YYYY-MM-DD_HHMM__topic-slug/
        SESSION.md      — frontmatter card (title, times, cwd, topics…)
        manifest.log    — one-line event record
        docs/           — subfolder stubs
        artifacts/
        screenshots/
        notes/

Idempotent (keyed by session_id). Move-only (no deletion). Safe to re-run.

Usage:
    python3 session_cabinet.py [--dry-run] [--verbose] [--limit N]
                               [--cabinet DIR] [--tz OFFSET]
                               [--source-dir DIR] [--source-label LABEL]
"""

import datetime
import json
import os
import pathlib
import re
import shutil
import sys
import time
import traceback
from typing import Dict, List, Optional, Set

# ---------------------------------------------------------------------------
# Splat audit hook (no-op in standalone mode)
# ---------------------------------------------------------------------------
def _emit_splat(*args, **kwargs):
    """No-op in standalone mode. Aria Code hosted version logs to splat chain."""
    pass


# ---------------------------------------------------------------------------
# Config (set in main() from CLI / env)
# ---------------------------------------------------------------------------
HOME = pathlib.Path.home()

# Cabinet path: env CC_CABINET_DIR → CLI --cabinet → default
_DEFAULT_CABINET = HOME / "Desktop" / "Claude Code Sessions"
CABINET: pathlib.Path = None          # set in main()
SOURCE_ROOTS: List[tuple] = []        # (path, label) list, built in main()
SESSION_DIRS_MAP: pathlib.Path = None # set in main()

# Day-burst: days with more than this many sessions get a DD/ subdir
DAY_BURST_THRESHOLD = 6

# "Live" session detection threshold: newest event within this many minutes
_LIVE_THRESHOLD_MINUTES = 30

# Verbose / dry-run flags (set in main)
VERBOSE = False
DRY_RUN = False

# Local timezone offset (timedelta). Detected from system in main(); can be
# overridden with --tz +HH:MM or --tz -HH:MM.
_LOCAL_TZ_OFFSET: datetime.timedelta = None   # set in main()


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def log(msg):
    print(msg)


def vlog(msg):
    if VERBOSE:
        print("  " + msg)


# ---------------------------------------------------------------------------
# Timezone helpers
# ---------------------------------------------------------------------------
MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}


def detect_local_tz_offset() -> datetime.timedelta:
    """
    Return the system local UTC offset as a timedelta.
    Uses datetime.astimezone() which reads the OS timezone — no external libs.
    """
    now_local = datetime.datetime.now(datetime.timezone.utc).astimezone()
    return now_local.utcoffset()


def parse_tz_flag(tz_str: str) -> datetime.timedelta:
    """
    Parse a --tz string like '+05:30', '-04:00', '-7', '+1' into a timedelta.
    Raises ValueError on bad input.
    """
    tz_str = tz_str.strip()
    m = re.match(r"^([+-])(\d{1,2})(?::(\d{2}))?$", tz_str)
    if not m:
        raise ValueError(f"Cannot parse timezone offset '{tz_str}'. Use ±HH or ±HH:MM")
    sign = 1 if m.group(1) == "+" else -1
    hours = int(m.group(2))
    minutes = int(m.group(3) or "0")
    return datetime.timedelta(hours=sign * hours, minutes=sign * minutes)


def utc_to_local(dt_utc: datetime.datetime) -> datetime.datetime:
    """
    Convert a UTC datetime to the configured local time.
    Uses _LOCAL_TZ_OFFSET (set by main() from system tz or --tz flag).
    Returns a naive datetime in local time.
    """
    offset = _LOCAL_TZ_OFFSET or datetime.timedelta(0)
    if dt_utc.tzinfo is not None:
        return (dt_utc + offset).replace(tzinfo=None)
    return dt_utc + offset


def tz_label() -> str:
    """Return a short timezone label for display (e.g. '+05:30', 'UTC-4')."""
    offset = _LOCAL_TZ_OFFSET or datetime.timedelta(0)
    total_seconds = int(offset.total_seconds())
    sign = "+" if total_seconds >= 0 else "-"
    abs_sec = abs(total_seconds)
    h, rem = divmod(abs_sec, 3600)
    m = rem // 60
    if m:
        return f"UTC{sign}{h}:{m:02d}"
    return f"UTC{sign}{h}"


# ---------------------------------------------------------------------------
# JSONL parsing helpers
# ---------------------------------------------------------------------------
def safe_json(line: str):
    """Parse a JSONL line; return None on failure."""
    try:
        return json.loads(line.strip())
    except Exception:
        return None


def extract_text(content) -> str:
    """Pull plain text from message.content (string or list of blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif block.get("type") == "tool_result":
                    sub = block.get("content", "")
                    parts.append(extract_text(sub))
        return " ".join(parts)
    return ""


def extract_tool_path(event: dict) -> List[str]:
    """Extract file paths from tool_use blocks in assistant messages."""
    paths = []
    msg = event.get("message", {})
    content = msg.get("content", [])
    if not isinstance(content, list):
        return paths
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            inp = block.get("input", {})
            for key in ("file_path", "path", "old_file", "new_file"):
                val = inp.get(key)
                if val and isinstance(val, str) and val.startswith("/"):
                    paths.append(val)
            cmd = inp.get("command", "")
            if cmd:
                # Extract absolute path tokens from bash commands
                hits = re.findall(r"(/[^\s\"'\\]+)", cmd)
                # Only keep plausible file paths (contain at least one /)
                paths.extend(h for h in hits if h.count("/") >= 2)
    return paths


def parse_session(jsonl_path: pathlib.Path) -> dict:
    """
    Parse a session .jsonl file and return a structured dict with:
      session_id, started_utc, ended_utc, cwd, first_user_msg,
      last_assistant_msg, touched_paths, ai_title, jsonl_path
    Returns None if the file is unreadable or clearly not a session transcript.
    """
    sid = jsonl_path.stem   # full UUID
    sid_short = sid[:8]

    started_utc = None
    ended_utc = None
    cwd = None
    first_user_msg = None
    last_assistant_msg = None
    touched_paths = []
    ai_title = None

    try:
        lines = jsonl_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception as e:
        vlog(f"Cannot read {jsonl_path}: {e}")
        return None

    if not lines:
        return None

    for raw_line in lines:
        ev = safe_json(raw_line)
        if ev is None:
            continue

        ev_type = ev.get("type", "")
        ts_str = ev.get("timestamp")

        # Timestamps
        if ts_str:
            try:
                ts = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if started_utc is None or ts < started_utc:
                    started_utc = ts
                if ended_utc is None or ts > ended_utc:
                    ended_utc = ts
            except Exception:
                pass

        # CWD
        if cwd is None:
            ev_cwd = ev.get("cwd")
            if ev_cwd:
                cwd = ev_cwd

        # AI title (Claude Code auto-generates this)
        if ev_type == "ai-title":
            ai_title = ev.get("aiTitle", "")

        # First substantive user message
        if ev_type == "user" and first_user_msg is None:
            msg = ev.get("message", {})
            is_meta = ev.get("isMeta", False)
            if not is_meta:
                raw_content = msg.get("content", "")
                text = extract_text(raw_content)
                if (text and
                        "<local-command-caveat>" not in text and
                        "<command-name>" not in text and
                        len(text) > 20):
                    first_user_msg = _strip_bootstrap_preamble(text)[:400].strip()

        # Last assistant text
        if ev_type == "assistant":
            msg = ev.get("message", {})
            content = msg.get("content", [])
            for block in (content if isinstance(content, list) else []):
                if isinstance(block, dict) and block.get("type") == "text":
                    t = block.get("text", "").strip()
                    if t:
                        last_assistant_msg = t[:300]

        # Touched paths from tool calls
        for p in extract_tool_path(ev):
            if p not in touched_paths:
                touched_paths.append(p)

    # Fallback: use file mtime
    if started_utc is None:
        try:
            mtime = jsonl_path.stat().st_mtime
            started_utc = datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc)
            ended_utc = started_utc
        except Exception:
            pass

    if started_utc is None:
        return None

    # Normalize cwd: fall back to home dir (generic)
    fallback_cwd = str(HOME)
    return {
        "session_id": sid,
        "session_id_short": sid_short,
        "started_utc": started_utc,
        "ended_utc": ended_utc,
        "cwd": cwd or fallback_cwd,
        "first_user_msg": first_user_msg or "",
        "last_assistant_msg": last_assistant_msg or "",
        "touched_paths": touched_paths[:60],
        "ai_title": ai_title or "",
        "jsonl_path": jsonl_path,
    }


# ---------------------------------------------------------------------------
# Bootstrap / preamble stripping
# ---------------------------------------------------------------------------
_BOOTSTRAP_PREFIXES = (
    "<system",
    "you are aria",
    "you are an aria",
    "your job is to",
    "reply with exactly",
    "reply exactly",
)

_TRIVIAL_USER_TEXTS = frozenset([
    "hey", "hello", "hi", "hey you there",
    "hey hey", "yo", "sup", "ok", "okay",
    "whats up", "what's up",
])

_TEST_INQUIRY_PHRASES = (
    "just doing a test",
    "doing a test",
    "just testing",
    "what's your purpose",
    "what is your purpose",
    "what can you help",
    "what can you do",
    "testing the interface",
    "find out where the bugs",
    "what's working",
    "what is working",
)

_ROLE_HINTS = {
    "telegram": "AI Telegram relay",
    "architect": "AI Architect",
    "engineer": "AI Engineer",
    "inspector": "AI Inspector",
    "builder": "AI Builder",
    "registrar": "AI Registrar",
}


def _is_bootstrap_text(text: str) -> bool:
    lower = text.strip().lower()
    for prefix in _BOOTSTRAP_PREFIXES:
        if lower.startswith(prefix):
            return True
    return False


def _extract_user_tag_content(text: str) -> str:
    user_blocks = re.findall(r"<user>\s*(.*?)\s*</user>", text, re.DOTALL | re.IGNORECASE)
    if user_blocks:
        for block in reversed(user_blocks):
            stripped = block.strip()
            normalized = re.sub(r"[^a-z0-9\s]", "", stripped.lower()).strip()
            if stripped and normalized not in _TRIVIAL_USER_TEXTS and len(normalized) > 4:
                return stripped
        return user_blocks[-1].strip()
    parts = re.split(r"</system>", text, flags=re.IGNORECASE)
    if len(parts) > 1:
        return parts[-1].strip()
    return ""


def _extract_role_hint(text: str) -> str:
    lower = text.lower()
    for keyword, label in _ROLE_HINTS.items():
        if keyword in lower:
            return label
    return ""


def _strip_bootstrap_preamble(text: str) -> str:
    """
    Strip system/role-injection preamble from the first user message,
    returning the substantive human content.
    """
    stripped = text.strip()
    lower = stripped.lower()

    if lower.startswith("reply with exactly") or lower.startswith("reply exactly"):
        return stripped

    has_system_tag = "<system" in lower
    has_role_injection = any(lower.startswith(p) for p in (
        "you are aria", "you are an", "your job is",
    ))

    if not (has_system_tag or has_role_injection):
        return stripped

    user_content = _extract_user_tag_content(stripped)
    role = _extract_role_hint(stripped)

    user_is_trivial = True
    user_is_test_inquiry = False
    user_is_interface_test = False
    if user_content:
        norm = re.sub(r"[^a-z0-9\s]", "", user_content.lower()).strip()
        user_is_trivial = (norm in _TRIVIAL_USER_TEXTS or len(norm) <= 4)
        if not user_is_trivial:
            user_lower = user_content.lower()
            user_is_test_inquiry = any(p in user_lower for p in _TEST_INQUIRY_PHRASES[:6])
            user_is_interface_test = any(p in user_lower for p in _TEST_INQUIRY_PHRASES[6:])

    if user_content and not user_is_trivial:
        if user_is_interface_test and role:
            return f"{role} interface walkthrough"
        if user_is_test_inquiry and role:
            return f"{role} interface test"
        if role and len(user_content) < 60:
            return f"{role}: {user_content}"
        return user_content

    if role:
        if user_content:
            norm = re.sub(r"[^a-z0-9\s]", "", user_content.lower()).strip()
            if norm in _TRIVIAL_USER_TEXTS or len(norm) <= 4:
                return f"{role} greeting ping"
        return f"{role} session"

    return stripped


# ---------------------------------------------------------------------------
# Slug generation
# ---------------------------------------------------------------------------
def _slugify(text: str, max_words: int = 5) -> str:
    """Turn text into kebab-case slug."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s\-]", " ", text)
    words = text.split()
    stop = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "with", "by", "from", "up", "about", "into", "that",
        "this", "is", "it", "as", "be", "was", "are", "were", "i", "you",
        "me", "my", "let", "let's", "lets", "we", "ok", "okay", "just",
        "can", "hey", "hi", "hello", "please", "what", "how", "do",
        "did", "done", "now", "get", "got", "run", "make", "use",
        "so", "have", "its", "our",
    }
    meaningful = [w for w in words if w not in stop and len(w) > 1][:max_words]
    if not meaningful:
        meaningful = words[:max_words]
    return "-".join(meaningful) if meaningful else "session"


def derive_slug(info: dict) -> str:
    """
    Derive a human-readable topic slug from session info.
    Priority: ai_title > first_user_msg (bootstrap-stripped) > cwd project name > session_id_short
    """
    first_msg = info.get("first_user_msg", "")

    # Special case: pure LLM connectivity probe
    first_lower = first_msg.lower().strip()
    if first_lower.startswith("reply with exactly") or first_lower.startswith("reply exactly"):
        after = re.sub(r"reply (with )?exactly:?\s*", "", first_lower).strip()
        if "runner" in after or "llm" in after:
            return "runner-llm-connectivity-probe"
        return _slugify(f"connectivity probe {after}", max_words=4)

    candidates = []

    ai_title = info.get("ai_title", "")
    if ai_title and len(ai_title) > 4:
        at_lower = ai_title.lower()
        if not any(at_lower.startswith(p) for p in ("system", "reply exactly", "you are")):
            candidates.append(ai_title)

    if first_msg:
        candidates.append(first_msg)

    # CWD-based project hint
    cwd = info.get("cwd", "")
    if cwd:
        parts = cwd.rstrip("/").split("/")
        home_parts = str(HOME).split("/")
        # Get the last meaningful segment that isn't the user's home
        for part in reversed(parts):
            if part and part not in home_parts and part not in ("", "~"):
                candidates.append(part)
                break

    for candidate in candidates:
        slug = _slugify(candidate, max_words=5)
        if len(slug) >= 4:
            return slug[:60]

    return info["session_id_short"]


# ---------------------------------------------------------------------------
# Cabinet path computation
# ---------------------------------------------------------------------------
def cabinet_path_for(info: dict, day_counts: dict) -> pathlib.Path:
    """
    Compute the final cabinet folder path for a session.
    day_counts: { 'YYYY-MM-DD': count } — used to decide burst.
    """
    started_local = utc_to_local(info["started_utc"])
    year_str = started_local.strftime("%Y")
    month_num = started_local.month
    month_str = f"{month_num:02d}-{MONTH_NAMES[month_num]}"
    day_str = started_local.strftime("%d")
    date_key = started_local.strftime("%Y-%m-%d")

    folder_name = (
        started_local.strftime("%Y-%m-%d_%H%M")
        + "__"
        + derive_slug(info)
    )

    month_dir = CABINET / year_str / month_str
    if day_counts.get(date_key, 0) > DAY_BURST_THRESHOLD:
        return month_dir / day_str / folder_name
    else:
        return month_dir / folder_name


# ---------------------------------------------------------------------------
# SESSION.md card generation
# ---------------------------------------------------------------------------
def derive_projects(touched_paths: List[str], cwd: str) -> List[str]:
    """
    Extract project names from touched paths and cwd.

    Strategy:
    - When cwd is not the home dir, the basename of cwd is the project.
    - Any git-repo dir names found in touched absolute paths (the segment
      immediately under ~/ or a common dev root) are included.
    - No hardcoded project names or org-specific path fragments.
    """
    projects = set()
    home_str = str(HOME)
    home_basename = HOME.name  # e.g. "ian" — skip this

    # Segments we always skip
    skip_segments = {home_basename, "Users", "home", "", "~", "Desktop",
                     "Documents", "Downloads", "bin", "opt", "usr", "etc",
                     "var", "tmp", "private"}

    def _add_from_path(p: str):
        if not p:
            return
        # The cwd basename is almost always the project
        parts = p.rstrip("/").split("/")
        # Walk from deepest to shallowest looking for a meaningful segment
        for seg in reversed(parts):
            if seg and seg not in skip_segments and len(seg) > 1:
                # Avoid very long segments (likely filenames with extensions)
                if "." not in seg or seg.startswith("."):
                    projects.add(seg)
                    return
                # Accept dotted names that look like project names (e.g. my-backend)
                # but not filenames
                if len(seg) < 40 and not re.search(r"\.(py|js|ts|go|rs|md|txt|json|yaml|sh|log)$", seg):
                    projects.add(seg)
                    return

    # cwd gets highest priority — its basename is almost always the project
    if cwd and cwd != home_str:
        cwd_base = pathlib.Path(cwd).name
        if cwd_base and cwd_base not in skip_segments:
            projects.add(cwd_base)

    # From touched paths: extract the second-deepest dir under home (dev/project)
    for p in touched_paths:
        if not p.startswith("/"):
            continue
        try:
            rel = pathlib.Path(p).relative_to(HOME)
            parts = rel.parts
            if len(parts) >= 2:
                # second part (e.g. HOME/dev/myproject/...) = parts[1]
                seg = parts[1] if parts[0] not in skip_segments else (parts[0] if len(parts) == 1 else None)
                if seg and seg not in skip_segments:
                    projects.add(seg)
        except ValueError:
            pass  # path not under HOME

    return sorted(list(projects))[:8]


def derive_topics(info: dict) -> List[str]:
    """
    Derive topic tags from session content using universal dev keywords.
    No product-specific terms — anyone cloning this skill gets sensible tags.
    """
    text = " ".join([
        info.get("first_user_msg", ""),
        info.get("last_assistant_msg", ""),
        info.get("ai_title", ""),
        info.get("cwd", ""),
    ]).lower()

    topic_map = {
        "git":        ["git ", "commit", "branch", "merge", "rebase", "push", "pull request", "diff"],
        "deploy":     ["deploy", "nginx", "systemd", "docker", "kubernetes", "k8s", "prod", "staging",
                       "rsync", "release", "ship"],
        "testing":    ["test", "pytest", "jest", "spec", "assert", "mock", "fixture", "coverage"],
        "frontend":   ["react", "vue", "svelte", "html", "css", "tailwind", "component", "ui ", "ux ",
                       "browser", "dom", "webpack", "vite"],
        "backend":    ["flask", "django", "fastapi", "express", "rails", "server", "api ", "endpoint",
                       "rest", "graphql", "route"],
        "database":   ["sql", "postgres", "sqlite", "mysql", "mongodb", "redis", "query", "migration",
                       "schema", "orm"],
        "docs":       ["document", "readme", "changelog", "spec", "wiki", "writeup", "guide"],
        "refactor":   ["refactor", "rename", "cleanup", "clean up", "reorganize", "restructure",
                       "extract", "dedup"],
        "debugging":  ["debug", "error", "traceback", "exception", "bug ", "fix ", "broken", "crash",
                       "fail"],
        "ci":         ["ci ", "github actions", "workflow", "pipeline", "build", "lint", "check"],
        "infra":      ["infra", "terraform", "ansible", "cloud", "aws", "gcp", "azure", "vpc",
                       "subnet", "firewall"],
        "api":        ["api key", "oauth", "token", "auth", "credential", "sdk ", "client"],
        "sessions":   ["session", "cabinet", "filing", "transcript", "archive", "history"],
    }

    found = []
    for tag, keywords in topic_map.items():
        if any(kw in text for kw in keywords):
            found.append(tag)
    return found[:6] if found else ["general"]


def is_live_session(info: dict) -> bool:
    """
    Detect whether a session is still in progress:
    1. Its newest event timestamp is within _LIVE_THRESHOLD_MINUTES of now, OR
    2. The $CLAUDE_SESSION_ID env var matches this session's full UUID.
    No hardcoded IDs.
    """
    # Check env var first (exact match on the running session)
    env_sid = os.environ.get("CLAUDE_SESSION_ID", "")
    if env_sid and env_sid == info["session_id"]:
        return True

    # Recency check
    ended = info.get("ended_utc")
    if ended is None:
        return False
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    if ended.tzinfo is None:
        ended = ended.replace(tzinfo=datetime.timezone.utc)
    age_minutes = (now_utc - ended).total_seconds() / 60
    return age_minutes <= _LIVE_THRESHOLD_MINUTES


def build_session_md(info: dict, folder: pathlib.Path, is_live: bool = False) -> str:
    """Build the full SESSION.md card content."""
    tz = tz_label()
    started_local = utc_to_local(info["started_utc"])
    ended_local = utc_to_local(info["ended_utc"])

    started_str = started_local.strftime(f"%Y-%m-%d %H:%M {tz}")
    ended_str = "in progress" if is_live else ended_local.strftime(f"%Y-%m-%d %H:%M {tz}")

    slug = derive_slug(info)
    title = info.get("ai_title") or slug.replace("-", " ").title()

    touched = [p for p in info["touched_paths"]
               if not any(skip in p for skip in [".jsonl", "__pycache__", ".git/"])][:12]

    projects = derive_projects(info["touched_paths"], info["cwd"])
    topics = derive_topics(info)

    first_msg = info.get("first_user_msg", "")
    last_msg = info.get("last_assistant_msg", "")
    summary_parts = []
    if first_msg:
        summary_parts.append(f"Session started with: \"{first_msg[:160]}\".")
    if last_msg and last_msg != first_msg:
        summary_parts.append(f"Last assistant output: \"{last_msg[:160]}\".")
    summary = " ".join(summary_parts) if summary_parts else "No summary available."

    yaml_lines = [
        "---",
        f"title:      {title}",
        f"session_id: {info['session_id_short']}",
        f"full_id:    {info['session_id']}",
        f"started:    {started_str}",
        f"ended:      {ended_str}",
        f"cwd:        {info['cwd']}",
        f"source:     {info.get('source', 'local')}",
    ]
    if projects:
        yaml_lines.append(f"projects:   [{', '.join(projects)}]")
    else:
        yaml_lines.append("projects:   []")
    if touched:
        touched_display = [os.path.basename(p) for p in touched[:8]]
        yaml_lines.append(f"touched:    [{', '.join(touched_display)}]")
    else:
        yaml_lines.append("touched:    []")
    yaml_lines.append(f"topics:     [{', '.join(topics)}]")
    yaml_lines.append("---")

    body = f"""
## Summary

{summary}

## Subfolders

- `docs/` — written docs, plans, specs
- `artifacts/` — generated outputs, exports
- `screenshots/` — UI screenshots
- `notes/` — scratch notes
"""

    return "\n".join(yaml_lines) + body


# ---------------------------------------------------------------------------
# Session folder management
# ---------------------------------------------------------------------------
def find_existing_folder(sid_short: str) -> Optional[pathlib.Path]:
    """
    Find an existing session folder anywhere in the Cabinet by matching the
    session ID short. Checks the session_dirs pointer map first, then walks.
    """
    ptr = SESSION_DIRS_MAP / sid_short
    if ptr.exists():
        try:
            mapped = pathlib.Path(ptr.read_text().strip())
            if mapped.exists():
                return mapped
        except Exception:
            pass

    if CABINET.exists():
        for candidate in CABINET.rglob("SESSION.md"):
            folder = candidate.parent
            if sid_short in folder.name:
                return folder
            try:
                content = candidate.read_text(encoding="utf-8", errors="ignore")
                if (f"session_id: {sid_short}" in content or
                        f"full_id:    {sid_short}" in content):
                    return folder
            except Exception:
                pass

    return None


def ensure_subfolders(folder: pathlib.Path):
    """Create the standard subfolders if missing."""
    for sub in ("docs", "artifacts", "screenshots", "notes"):
        sub_dir = folder / sub
        if not sub_dir.exists() and not DRY_RUN:
            sub_dir.mkdir(parents=True, exist_ok=True)


def preserve_existing_content(old_folder: pathlib.Path, new_folder: pathlib.Path):
    """When moving a folder, merge its contents into the new location."""
    if old_folder == new_folder:
        return
    if not DRY_RUN:
        if new_folder.exists():
            for item in old_folder.iterdir():
                dest = new_folder / item.name
                if not dest.exists():
                    shutil.move(str(item), str(dest))
        else:
            new_folder.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old_folder), str(new_folder))


def get_human_notes(session_md: pathlib.Path) -> str:
    """Extract any human-written ## Notes section from an existing SESSION.md."""
    if not session_md.exists():
        return ""
    try:
        text = session_md.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"(^## Notes.*)", text, re.MULTILINE | re.DOTALL)
        if m:
            return "\n\n" + m.group(1).strip()
    except Exception:
        pass
    return ""


def session_md_is_stub(session_md: pathlib.Path) -> bool:
    """Return True if SESSION.md is the auto-generated stub (no full frontmatter)."""
    if not session_md.exists():
        return True
    try:
        text = session_md.read_text(encoding="utf-8", errors="ignore")
        return "full_id:" not in text and len(text) < 600
    except Exception:
        return True


# ---------------------------------------------------------------------------
# Day count pre-pass
# ---------------------------------------------------------------------------
def compute_day_counts(all_sessions: List[dict]) -> dict:
    """Count sessions per local date key (YYYY-MM-DD) for day-burst logic."""
    counts = {}
    for info in all_sessions:
        local_dt = utc_to_local(info["started_utc"])
        key = local_dt.strftime("%Y-%m-%d")
        counts[key] = counts.get(key, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Index generation
# ---------------------------------------------------------------------------
def parse_card_frontmatter(session_md: pathlib.Path) -> Optional[dict]:
    """Parse YAML-ish frontmatter from a SESSION.md card into a light dict."""
    try:
        text = session_md.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    out = {}
    for line in text[3:end].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    dt = None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})", out.get("started", ""))
    if m:
        y, mo, d, h, mi = map(int, m.groups())
        try:
            dt = datetime.datetime(y, mo, d, h, mi)
        except Exception:
            dt = None
    return {
        "title": (out.get("title", "") or session_md.parent.name)[:50],
        "session_id": out.get("session_id", ""),
        "source": out.get("source", "local"),
        "projects": out.get("projects", "[]").strip("[]")[:40],
        "started_local": dt,
        "folder": session_md.parent,
    }


def scan_cabinet_cards() -> List[dict]:
    """Walk the Cabinet and parse every SESSION.md card. Used for index rebuild."""
    cards = []
    if not CABINET.exists():
        return cards
    for sm in CABINET.rglob("SESSION.md"):
        c = parse_card_frontmatter(sm)
        if c and c["started_local"]:
            cards.append(c)
    return cards


def regenerate_all_indexes():
    """
    Rebuild master + per-month _INDEX.md files from ALL on-disk SESSION.md cards.
    Returns (total_cards, months_written).
    """
    cards = scan_cabinet_cards()
    cards.sort(key=lambda c: c["started_local"], reverse=True)
    tz = tz_label()
    now = datetime.datetime.now().strftime(f"%Y-%m-%d %H:%M {tz}")

    def row(c, folder_str):
        dt = c["started_local"]
        return (f"| {dt.strftime('%Y-%m-%d')} | {dt.strftime('%H:%M')} | "
                f"{c['source']} | {c['title']} | {c['projects']} | {folder_str} |")

    # Master index
    lines = [
        "# Claude Code Sessions — Master Index", "",
        f"_Generated: {now}_",
        f"_Total sessions: {len(cards)}_", "",
        f"| Date | Time ({tz}) | Source | Title | Projects | Folder |",
        "|------|------------|--------|-------|----------|--------|",
    ]
    for c in cards:
        rel = c["folder"].relative_to(CABINET) if c["folder"].is_relative_to(CABINET) else c["folder"]
        lines.append(row(c, str(rel)))
    if not DRY_RUN:
        (CABINET / "_INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Per-month indexes
    by_month = {}
    for c in cards:
        try:
            rel = c["folder"].relative_to(CABINET)
        except ValueError:
            continue
        if len(rel.parts) >= 2 and re.match(r"^\d{4}$", rel.parts[0]):
            by_month.setdefault((rel.parts[0], rel.parts[1]), []).append(c)

    for (year, month), mcards in by_month.items():
        mcards.sort(key=lambda c: c["started_local"], reverse=True)
        mlines = [
            f"# Sessions — {year} / {month}", "",
            f"_Generated: {now}_",
            f"_Sessions this month: {len(mcards)}_", "",
            f"| Date | Time ({tz}) | Source | Title | Projects | Folder |",
            "|------|------------|--------|-------|----------|--------|",
        ]
        mroot = CABINET / year / month
        for c in mcards:
            try:
                fstr = str(c["folder"].relative_to(mroot))
            except ValueError:
                fstr = c["folder"].name
            mlines.append(row(c, fstr))
        if not DRY_RUN:
            (mroot / "_INDEX.md").write_text("\n".join(mlines) + "\n", encoding="utf-8")

    return len(cards), len(by_month)


# ---------------------------------------------------------------------------
# Main filing logic
# ---------------------------------------------------------------------------
def collect_session_jsonl_paths() -> List[tuple]:
    """
    Find all main session .jsonl files across SOURCE_ROOTS.
    Skips subagent/workflow transcripts and non-UUID filenames.
    Returns list of (path, source_label) tuples.
    """
    paths = []
    for root, source in SOURCE_ROOTS:
        if not root.exists():
            continue
        for p in root.rglob("*.jsonl"):
            parts = p.parts
            if "subagents" in parts or "workflows" in parts:
                continue
            if "memory" in parts:
                continue
            stem = p.stem
            if re.match(
                r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                stem
            ):
                paths.append((p, source))
    return paths


def file_sessions(limit: int = None):
    """Main entry point: scan, parse, and file all sessions."""
    log(f"\n{'='*60}")
    log("Claude Code Session Cabinet")
    log(f"Cabinet: {CABINET}")
    log(f"Local timezone: {tz_label()}")
    log(f"Dry run: {DRY_RUN}")
    log(f"{'='*60}\n")

    if not DRY_RUN:
        CABINET.mkdir(parents=True, exist_ok=True)

    # 1. Collect JSONL paths
    log("Scanning for session transcripts...")
    jsonl_paths = collect_session_jsonl_paths()
    log(f"Found {len(jsonl_paths)} session transcript(s)")

    if limit:
        jsonl_paths = jsonl_paths[:limit]
        log(f"Limited to {limit} sessions for this run")

    # 2. Parse sessions
    log("\nParsing transcripts...")
    all_sessions = []
    parse_errors = []
    seen_sids: dict = {}
    for p, source in jsonl_paths:
        try:
            info = parse_session(p)
            if info:
                sid = info["session_id"]
                if sid in seen_sids:
                    continue   # duplicate across sources; keep first
                seen_sids[sid] = True
                info["source"] = source
                all_sessions.append(info)
            else:
                parse_errors.append(str(p))
        except Exception as e:
            parse_errors.append(f"{p}: {e}")

    log(f"Parsed {len(all_sessions)} sessions ({len(parse_errors)} errors)")
    if parse_errors:
        log("\nParse errors:")
        for e in parse_errors[:10]:
            log(f"  {e}")

    # 3. Day counts
    day_counts = compute_day_counts(all_sessions)
    burst_days = [d for d, c in day_counts.items() if c > DAY_BURST_THRESHOLD]
    if burst_days:
        log(f"\nDay-burst will apply for: {', '.join(sorted(burst_days))}")

    # 4. File each session
    log("\nFiling sessions...")
    filed = 0
    migrated = 0
    updated = 0
    skipped = 0
    sid_to_folder: dict = {}
    used_paths: Set[pathlib.Path] = set()

    for info in all_sessions:
        sid_short = info["session_id_short"]
        live = is_live_session(info)

        target = cabinet_path_for(info, day_counts)

        # Collision dedup within this run
        if target in used_paths:
            base_name = target.name
            if not base_name.endswith(sid_short):
                target = target.parent / (base_name + "-" + sid_short)
        elif target.exists():
            folder_is_ours = False
            existing_sm = target / "SESSION.md"
            if existing_sm.exists():
                try:
                    sm_text = existing_sm.read_text(encoding="utf-8", errors="ignore")
                    if (f"session_id: {sid_short}" in sm_text or
                            f"full_id:    {sid_short}" in sm_text):
                        folder_is_ours = True
                except Exception:
                    pass
            ptr = SESSION_DIRS_MAP / sid_short
            if ptr.exists():
                try:
                    ptr_path = pathlib.Path(ptr.read_text().strip())
                    if ptr_path == target:
                        folder_is_ours = True
                except Exception:
                    pass
            if not folder_is_ours:
                base_name = target.name
                if not base_name.endswith(sid_short):
                    target = target.parent / (base_name + "-" + sid_short)
        used_paths.add(target)

        # Check if already filed
        existing = find_existing_folder(sid_short)

        if existing and existing == target:
            sid_to_folder[sid_short] = target
            session_md = target / "SESSION.md"
            human_notes = get_human_notes(session_md)
            if session_md_is_stub(session_md):
                new_content = build_session_md(info, target, is_live=live) + human_notes
                if not DRY_RUN:
                    session_md.write_text(new_content, encoding="utf-8")
                vlog(f"Updated stub: {target.relative_to(CABINET)}")
                updated += 1
            else:
                vlog(f"OK (already filed): {target.relative_to(CABINET)}")
                skipped += 1
            continue

        if existing and existing != target:
            vlog(f"Migrating: {existing.name} → {target.relative_to(CABINET)}")
            if not DRY_RUN:
                target.parent.mkdir(parents=True, exist_ok=True)
                preserve_existing_content(existing, target)
                ensure_subfolders(target)
                session_md = target / "SESSION.md"
                human_notes = get_human_notes(session_md)
                new_content = build_session_md(info, target, is_live=live) + human_notes
                session_md.write_text(new_content, encoding="utf-8")
                ptr = SESSION_DIRS_MAP / sid_short
                ptr.write_text(str(target))
            sid_to_folder[sid_short] = target
            migrated += 1
            continue

        # New session — create folder
        vlog(f"Filing: {target.relative_to(CABINET)}")
        if not DRY_RUN:
            target.mkdir(parents=True, exist_ok=True)
            ensure_subfolders(target)
            if info.get("source", "local") != "local":
                raw_dir = target / "raw"
                raw_dir.mkdir(exist_ok=True)
                raw_dest = raw_dir / "transcript.jsonl"
                if not raw_dest.exists():
                    try:
                        shutil.copy2(str(info["jsonl_path"]), str(raw_dest))
                    except Exception:
                        pass
            session_md = target / "SESSION.md"
            content = build_session_md(info, target, is_live=live)
            session_md.write_text(content, encoding="utf-8")
            manifest = target / "manifest.log"
            if not manifest.exists():
                started_local = utc_to_local(info["started_utc"])
                manifest.write_text(
                    f"{started_local.strftime('%Y-%m-%d %H:%M:%S')}  SESSION START  "
                    f"sid={sid_short}  cwd={info['cwd']}\n",
                    encoding="utf-8"
                )
            ptr_dir = SESSION_DIRS_MAP
            ptr_dir.mkdir(parents=True, exist_ok=True)
            ptr = ptr_dir / sid_short
            if not ptr.exists():
                ptr.write_text(str(target))

        sid_to_folder[sid_short] = target
        filed += 1

    log(f"\nResults: {filed} new, {migrated} migrated, {updated} updated, {skipped} already-current")

    # 5. Rebuild indexes from all on-disk cards
    log("\nWriting indexes (from all on-disk cards)...")
    total_indexed, months_written = regenerate_all_indexes()
    log(f"Indexed {total_indexed} sessions across {months_written} month(s)")

    # 6. Brief tree
    log("\n--- Cabinet tree (2-3 levels) ---")
    print_cabinet_tree(CABINET, max_depth=3)

    _emit_splat(
        layer="session_cabinet_run",
        payload={
            "filed": filed, "migrated": migrated, "updated": updated,
            "skipped": skipped, "total": len(all_sessions),
            "parse_errors": len(parse_errors),
        }
    )

    return {
        "filed": filed,
        "migrated": migrated,
        "updated": updated,
        "skipped": skipped,
        "total": len(all_sessions),
        "parse_errors": len(parse_errors),
        "months": months_written,
    }


def print_cabinet_tree(path: pathlib.Path, max_depth: int = 3,
                       _depth: int = 0, _prefix: str = ""):
    """Print a depth-limited tree of the Cabinet."""
    if _depth >= max_depth:
        return
    try:
        items = sorted(
            [x for x in path.iterdir() if not x.is_symlink()],
            key=lambda x: (x.is_file(), x.name)
        )
    except (PermissionError, FileNotFoundError):
        return

    if _depth == 0:
        new_style = [x for x in items if re.match(r"^\d{4}$", x.name)]
        old_style = [x for x in items if x.is_dir()
                     and not re.match(r"^\d{4}$", x.name)
                     and not x.name.startswith("_")]
        special = [x for x in items if x.is_file() or x.name.startswith("_")]
        items = special + new_style
        if old_style:
            print(f"{_prefix}... ({len(old_style)} legacy folder(s) not yet migrated)")

    for i, item in enumerate(items):
        is_last = i == len(items) - 1
        connector = "└── " if is_last else "├── "
        print(f"{_prefix}{connector}{item.name}")
        if item.is_dir() and _depth + 1 < max_depth:
            extension = "    " if is_last else "│   "
            print_cabinet_tree(item, max_depth, _depth + 1, _prefix + extension)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main():
    global VERBOSE, DRY_RUN, CABINET, SOURCE_ROOTS, SESSION_DIRS_MAP, _LOCAL_TZ_OFFSET

    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print(
            "session-cabinet — file Claude Code sessions into a date-anchored cabinet.\n"
            "\nUsage: session_cabinet.py [--dry-run] [--verbose] [--limit N]\n"
            "         [--cabinet DIR] [--tz OFFSET] [--source-dir DIR] [--source-label LABEL]\n"
            "\n  --dry-run        scan + report, write nothing\n"
            "  --cabinet DIR    cabinet root (default: ~/Desktop/Claude Code Sessions)\n"
            "  --source-dir DIR add an extra transcript source (recovered backup, etc.)\n"
            "  --limit N        cap sessions processed (testing)\n"
        )
        sys.exit(0)
    dry_run = "--dry-run" in args
    verbose = "--verbose" in args or "-v" in args
    limit = None
    cabinet_override = None
    tz_override = None
    src_dir = None
    src_label = None

    for i, a in enumerate(args):
        if a == "--limit" and i + 1 < len(args):
            try:
                limit = int(args[i + 1])
            except ValueError:
                pass
        elif a == "--cabinet" and i + 1 < len(args):
            cabinet_override = args[i + 1]
        elif a == "--tz" and i + 1 < len(args):
            tz_override = args[i + 1]
        elif a == "--source-dir" and i + 1 < len(args):
            src_dir = args[i + 1]
        elif a == "--source-label" and i + 1 < len(args):
            src_label = args[i + 1]

    # Resolve cabinet path: CLI flag > env > default
    if cabinet_override:
        CABINET = pathlib.Path(cabinet_override).expanduser().resolve()
    elif os.environ.get("CC_CABINET_DIR"):
        CABINET = pathlib.Path(os.environ["CC_CABINET_DIR"]).expanduser().resolve()
    else:
        CABINET = _DEFAULT_CABINET

    # Session dirs pointer map lives inside the cabinet
    SESSION_DIRS_MAP = CABINET / ".session_dirs"

    # Build source roots
    SOURCE_ROOTS = [(HOME / ".claude" / "projects", "local")]
    if src_dir:
        SOURCE_ROOTS.append((
            pathlib.Path(src_dir).expanduser(),
            src_label or "external"
        ))

    # Timezone
    if tz_override:
        try:
            _LOCAL_TZ_OFFSET = parse_tz_flag(tz_override)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        _LOCAL_TZ_OFFSET = detect_local_tz_offset()

    VERBOSE = verbose
    DRY_RUN = dry_run

    if dry_run:
        print("DRY RUN — no files will be written")

    try:
        results = file_sessions(limit=limit)
        print(
            f"\nDone. {results['total']} sessions, "
            f"{results['filed']} new, {results['migrated']} migrated, "
            f"{results['updated']} updated, {results['skipped']} already-current, "
            f"{results['parse_errors']} parse errors."
        )
    except Exception as e:
        print(f"\nFATAL: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
