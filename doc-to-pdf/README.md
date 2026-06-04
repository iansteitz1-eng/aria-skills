# doc-to-pdf

> One command from Markdown/HTML to a clean, branded, multi-page PDF.

The deliverable you'd actually hand a client — not a screenshot, not a print-to-PDF with the browser's URL stamped in the header. Uses headless Chrome's `--print-to-pdf` (the best-fidelity HTML→PDF path on a normal machine) and wraps your content in a consistent brand template.

## Install

```sh
pip install -r requirements.txt   # PyYAML optional; python-markdown recommended
```

Requires Chrome, Chromium, or Edge installed (any one — the script finds it).

## Use

```sh
# Markdown → branded PDF
python3 doc_to_pdf.py roadmap.md -o "Roadmap.pdf" --title "Brothers Composites — Roadmap"

# HTML that's already styled → render without the brand wrap
python3 doc_to_pdf.py hub.html --no-brand
```

## Options

| Flag | Effect |
|------|--------|
| `-o, --output` | Output path (default: input name with `.pdf`) |
| `--title` | Title used by the brand template |
| `--no-brand` | Don't wrap — render the HTML as-is |
| `--template tpl.html` | Custom shell with `{{title}}` / `{{content}}` placeholders |
| `--force` | Overwrite the output PDF if it already exists |

## Markdown support

In order of preference, the converter uses: `python-markdown` (tables, fenced code, sane lists) → `pandoc` if installed → a built-in minimal converter (headings, bold, lists, paragraphs). Install `python-markdown` for the best results with tables.

## Safety model

- Produces a **new file**; refuses to overwrite without `--force`.
- No network, no credentials, nothing leaves the machine.

## License

Apache 2.0
