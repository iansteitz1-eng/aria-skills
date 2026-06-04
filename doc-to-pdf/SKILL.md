---
name: doc-to-pdf
description: Render a Markdown or HTML document into a clean, branded, multi-page PDF via headless Chrome — the polished deliverable you'd hand a client, not a screenshot. Brand wrap (print-CSS + footer) is on by default; --no-brand for raw; --template for a custom shell. Never overwrites without --force. Use when the user says "make a PDF", "turn this into a PDF", "PDF this", "send them a PDF", "build a client doc", "export to PDF", "branded PDF".
---

# doc-to-pdf

One command from a Markdown or HTML file to a presentation-grade PDF. Uses headless Chrome's `--print-to-pdf` (best-fidelity HTML→PDF on a normal machine) and wraps your content in a consistent brand template so every client deliverable matches.

## When to use

- Turning a Markdown brief or an HTML page into a client-ready PDF
- Producing a branded workflow/roadmap/proposal document
- Any "send them a PDF" moment where it should look intentional

## How it works

1. **Markdown** input → HTML (python-markdown, falling back to pandoc, then a minimal converter).
2. **HTML** input → used as-is.
3. Wraps in the **brand template** (letter page, print margins, blue accents, footer) unless `--no-brand`.
4. Renders via headless Chrome (`--headless=new --no-pdf-header-footer`).

## CLI

```sh
python3 doc_to_pdf.py <input.md|input.html> [-o out.pdf] [--title "..."] [--no-brand] [--template tpl.html] [--force]
```

Examples:
```sh
python3 doc_to_pdf.py roadmap.md -o "Brothers - Roadmap.pdf" --title "Brothers Composites — Roadmap"
python3 doc_to_pdf.py hub.html --no-brand        # already-styled HTML, no wrap
```

## Safety

- Produces a **new file**; never overwrites an existing PDF without `--force`.
- No network, no credentials.
- Requires Chrome / Chromium / Edge installed (any one).

## See also

- **[client-delivery](../client-delivery/)** — renders deliverables as part of the audit → render → publish pipeline.
