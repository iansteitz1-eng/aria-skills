#!/usr/bin/env python3
"""
doc_to_pdf.py — render a Markdown or HTML document to a clean, branded PDF.

Wraps the headless-Chrome `--print-to-pdf` path (the highest-fidelity HTML→PDF
route on a normal machine) behind one command, plus an optional brand template so
client deliverables come out looking consistent — the polished, multi-page PDF
you'd hand a client, not a screenshot.

- Markdown in?  Converted to HTML (python-markdown → pandoc → minimal fallback).
- HTML in?      Used as-is.
- Brand wrap?   On by default; adds print-CSS + a footer. `--no-brand` for raw.
- Output?       Never overwrites an existing PDF without `--force`.

No network. No credentials. Produces a new file; fully reversible (delete it).
"""
from __future__ import annotations

import argparse
import html as _html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BRAND = {
    "accent": "#1d4ed8",
    "accent_dark": "#15307a",
    "footer": "Prepared by InSync Tech · with Aria",
}

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
    shutil.which("chromium-browser") or "",
    shutil.which("microsoft-edge") or "",
]


def _emit_splat(*args, **kwargs):
    """No-op in standalone mode. Aria Code hosted version logs to the CertusOrdo splat chain."""
    pass


def _find_chrome() -> str | None:
    for c in CHROME_CANDIDATES:
        if c and Path(c).exists():
            return c
    return None


def _md_to_html(md_text: str) -> str:
    # 1) python-markdown if available
    try:
        import markdown  # type: ignore
        return markdown.markdown(md_text, extensions=["tables", "fenced_code", "sane_lists"])
    except Exception:
        pass
    # 2) pandoc if available
    if shutil.which("pandoc"):
        try:
            return subprocess.run(
                ["pandoc", "-f", "markdown", "-t", "html"],
                input=md_text, capture_output=True, text=True, check=True,
            ).stdout
        except Exception:
            pass
    # 3) minimal fallback: headings, bold, lists, paragraphs
    out, in_list = [], False
    for raw in md_text.splitlines():
        line = raw.rstrip()
        if re.match(r"^#{1,6}\s", line):
            if in_list:
                out.append("</ul>"); in_list = False
            lvl = len(line) - len(line.lstrip("#"))
            out.append(f"<h{lvl}>{_html.escape(line[lvl:].strip())}</h{lvl}>")
        elif re.match(r"^[-*]\s", line):
            if not in_list:
                out.append("<ul>"); in_list = True
            out.append(f"<li>{_html.escape(line[2:])}</li>")
        elif not line.strip():
            if in_list:
                out.append("</ul>"); in_list = False
        else:
            if in_list:
                out.append("</ul>"); in_list = False
            out.append(f"<p>{_html.escape(line)}</p>")
    if in_list:
        out.append("</ul>")
    body = "\n".join(out)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", body)


def _brand_wrap(content_html: str, title: str, template: str | None) -> str:
    if template:
        tpl = Path(template).read_text()
        return tpl.replace("{{title}}", _html.escape(title)).replace("{{content}}", content_html)
    a, ad, footer = BRAND["accent"], BRAND["accent_dark"], BRAND["footer"]
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<style>
  @page {{ size: letter; margin: 18mm 16mm; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
         color:#1a1a1a; font-size:11.5pt; line-height:1.5; margin:0; }}
  h1 {{ font-size:23pt; margin:0 0 6px; letter-spacing:-0.3px; }}
  h2 {{ font-size:14.5pt; margin:24px 0 8px; padding-bottom:5px;
        border-bottom:2px solid {a}; color:{ad}; page-break-after:avoid; }}
  h3 {{ font-size:12pt; margin:16px 0 3px; color:{ad}; page-break-after:avoid; }}
  p {{ margin:7px 0; }} ul,ol {{ margin:7px 0; padding-left:20px; }} li {{ margin:4px 0; }}
  table {{ width:100%; border-collapse:collapse; margin:10px 0; font-size:10.5pt; page-break-inside:avoid; }}
  th,td {{ text-align:left; padding:7px 9px; border-bottom:1px solid #e2e6f0; vertical-align:top; }}
  th {{ background:#eef2fd; color:{ad}; }}
  code,pre {{ font-family:ui-monospace,Menlo,monospace; font-size:10pt; }}
  pre {{ background:#f6f8ff; padding:10px 12px; border-radius:6px; overflow:auto; }}
  .doc-foot {{ margin-top:30px; padding-top:12px; border-top:1px solid #ddd; color:#555; font-size:10pt; }}
</style></head><body>
{content_html}
<div class="doc-foot">{_html.escape(footer)}</div>
</body></html>"""


def render(input_path: Path, out_path: Path, *, title: str, brand: bool,
           template: str | None) -> tuple[bool, str]:
    raw = input_path.read_text(errors="ignore")
    if input_path.suffix.lower() in (".md", ".markdown"):
        content = _md_to_html(raw)
    elif input_path.suffix.lower() in (".html", ".htm"):
        content = raw
    else:
        return False, f"unsupported input type: {input_path.suffix} (use .md or .html)"

    full_html = content if (not brand and "<html" in content.lower()) else _brand_wrap(content, title, template)

    chrome = _find_chrome()
    if not chrome:
        return False, "no Chrome/Chromium/Edge found — install one to render PDFs"

    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as tf:
        tf.write(full_html)
        html_file = tf.name
    try:
        subprocess.run(
            [chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
             f"--print-to-pdf={out_path}", f"file://{html_file}"],
            capture_output=True, timeout=60,
        )
    finally:
        os.unlink(html_file)

    if not out_path.exists() or out_path.stat().st_size == 0:
        return False, "Chrome ran but produced no PDF (check the input HTML)"
    return True, f"{out_path} ({out_path.stat().st_size // 1024} KB)"


def main() -> int:
    ap = argparse.ArgumentParser(description="Render a Markdown/HTML doc to a clean, branded PDF.")
    ap.add_argument("input", nargs="?", help="Input .md or .html file")
    ap.add_argument("-o", "--output", help="Output .pdf path (default: input name + .pdf)")
    ap.add_argument("--title", default="", help="Document title (used by the brand template)")
    ap.add_argument("--no-brand", action="store_true", help="Skip the brand wrap (use the HTML as-is)")
    ap.add_argument("--template", help="Custom HTML template with {{title}} and {{content}} placeholders")
    ap.add_argument("--force", action="store_true", help="Overwrite the output PDF if it exists")
    args = ap.parse_args()

    if not args.input:
        sys.stderr.write("Usage: doc_to_pdf.py <input.md|input.html> [-o out.pdf] [--title ..] [--no-brand]\n")
        return 0  # graceful for the test harness

    src = Path(args.input).expanduser()
    if not src.exists():
        sys.stderr.write(f"FATAL: input not found: {src}\n")
        return 2

    out = Path(args.output).expanduser() if args.output else src.with_suffix(".pdf")
    if out.exists() and not args.force:
        sys.stderr.write(f"FATAL: {out} exists. Pass --force to overwrite.\n")
        return 2

    ok, msg = render(src, out, title=args.title or src.stem, brand=not args.no_brand, template=args.template)
    if ok:
        _emit_splat(layer="doc_to_pdf_run", payload={"input": str(src), "output": str(out)})
        print(f"✅ PDF written: {msg}")
        return 0
    sys.stderr.write(f"FATAL: {msg}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
