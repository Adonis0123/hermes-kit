---
name: convert-documents-to-markdown
description: Convert Word/PPT/Excel/PDF to Markdown via read_file.
version: 0.1.0
author: Adonis0123 (adapted from firecrawl/anydoc)
license: MIT
metadata:
  hermes:
    tags: [Documents, Markdown, anydoc, PDF, Office]
    related_skills: [ocr-and-documents]
---

# Convert documents to Markdown

Hermes already converts most office files inside `read_file` (lazy `firecrawl-anydoc`). This skill is the **routing**, not a second converter.

**Use when** a task needs the contents of `.doc` `.docx` `.ppt` `.pptx` `.xls` `.xlsx` `.odt` `.ods` `.odp` `.rtf` `.epub` `.csv` `.pdf` that cannot be read as plain text.

Upstream CLI skill (do **not** `npx skills add` it here): https://github.com/firecrawl/anydoc/tree/main/skills/convert-documents-to-markdown

Pin / routing / quality notes: `references/anydoc-read-file.md`.

## When to Use

- User (or a task) needs an office document, spreadsheet, presentation, ebook, or PDF
- `read_file` returned a binary-file guard, empty math, or raw percents that look wrong
- Do **not** use for scanned/image-only PDFs → `ocr-and-documents` (or `pdftoppm` + `vision_analyze`)

## Procedure

1. **Local file, normal read** — `read_file` the path. It auto-extracts Markdown for:
   - stdlib: `.ipynb` `.docx` `.xlsx`
   - anydoc (lazy `firecrawl-anydoc==0.2.3`): `.pdf` `.doc` `.ppt` `.xls` `.pptx` + variants, `.odt` `.ods` `.odp` `.rtf` `.epub`
   Stop here if the text is usable.
2. **stdlib gap** — `.docx` formulas and `.xlsx` number formats (`15.5%` / `$1,234.50`) stay on the stdlib path even with anydoc installed. Re-convert with the **venv library**, not `npx`:

   ```bash
   "$HERMES_HOME/hermes-agent/.venv/bin/python" -c 'import anydoc,sys; print(anydoc.to_markdown(sys.argv[1]))' -- "/path/to/file.docx"
   ```

   Large output: write a `.md` next to the source and `read_file` slices of it.
3. **CSV** — Hermes `read_file` does **not** extract `.csv`. Same Python one-liner, or pass format when the extension is missing:

   ```bash
   "$HERMES_HOME/hermes-agent/.venv/bin/python" -c 'import anydoc,sys; print(anydoc.to_markdown_bytes(open(sys.argv[1],"rb").read(),"csv"))' -- "/path/to/file.csv"
   ```
4. **URL** — `web_extract` the PDF/Office URL first. Fall back to download + step 1.
5. **Scanned / empty PDF** — anydoc raises `UnsupportedError: … OCR is required`. Load `ocr-and-documents`. Do not retry anydoc.

`npx -y @firecrawl/anydoc` is a last resort (no venv, or need to prove CLI==Python). Prefer the already-installed 0.2.3 wheel.

## Failures

| Symptom | Meaning | Next |
|---------|---------|------|
| binary-file guard on `.pdf`/`.pptx` | anydoc not loaded in **this** process | `/restart` after pin bump; then `read_file` again |
| “The roots are  for any a.” | stdlib `.docx` ate OMML | step 2 |
| `0.155` instead of `15.5%` | stdlib `.xlsx` | step 2 on `.xlsx`, or `read_file` a `.xls` |
| `EncryptedError` | password-protected | stop; ask for an unlocked copy |
| `MalformedError` | truncated/corrupt | stop; file is unusable |
| `UnsupportedError` + Scanned | no text layer | `ocr-and-documents` |

## Pitfalls

- Do **not** `npx skills add firecrawl/anydoc -g` — installer can overwrite Hermes category dirs (see `references/anydoc-read-file.md`).
- Do **not** shell `npx` on every document; the Python binding is the same converter and is already in the Hermes venv.
- Cap 50 MB (`read_file`). Bigger files: convert to a `.md` on disk, then paginate.
- Pin lives in `tools/lazy_deps.py` (`tool.doc_extract`). Changing it needs a gateway `/restart`.
