# Hermes `read_file` + anydoc (verified 2026-08-22)

Firecrawl [anydoc](https://github.com/firecrawl/anydoc) converts Word / PPT / Excel / ODF / RTF / EPUB / CSV / PDF to GFM. Hermes wires it into the **`read_file` lazy-install path**; it is not a separate tool.

Official docs: https://hermes-agent.nousresearch.com/docs/user-guide/features/document-extraction

## Routing (hard)

| Extension | Converter | Notes |
|-----------|-----------|-------|
| `.ipynb` `.docx` `.xlsx` | **stdlib** (`tools/read_extract.py`) | Stays on stdlib even with anydoc installed; `.docx` formulas / Excel percentages do not improve |
| `.pdf` `.doc` `.ppt` `.xls` `.pptx` + variants, `.odt` `.ods` `.odp` `.rtf` `.epub` | **anydoc** | First read runs `lazy_deps.ensure("tool.doc_extract", prompt=False)` |
| `.csv` | anydoc **library can convert** | Hermes `ANYDOC_EXTENSIONS` does not include it → `read_file` rejects it as binary |

Cap 50 MB. Scanned / text-less PDFs are not anydoc's job → `ocr-and-documents` (marker-pdf) or `pdftoppm` + `vision_analyze`.

## Version pin

```
tools/lazy_deps.py  LAZY_DEPS["tool.doc_extract"] = ("firecrawl-anydoc==0.2.3",)
pyproject.toml      [tool.uv].exclude-newer-package.firecrawl-anydoc = false
```

A release newer than uv's `exclude-newer` window needs an exact pin plus the per-package exemption to lazy-install; drop the exemption once the release ages out of the window. After changing the pin, restart the gateway (`/restart`), otherwise the process keeps the cached `_anydoc_module`.

## 0.1.6 → 0.2.3 quality

| Item | 0.1.6 | 0.2.3 |
|------|-------|-------|
| Formulas (docx/pptx/rtf/odt/epub) | OMML/MathML **eaten into spaces** | `$x=\frac{-b\pm\sqrt{...}}{2a}$` / `$$` blocks |
| xls/xlsx numbers | `0.155` / `1234.5` | `15.5%` / `$1,234.50` |
| Text-PDF strikethrough | `struck` | `<s>struck</s>` |
| Empty / scanned PDF | often `MalformedError` | `UnsupportedError: … (Scanned, 0 pages): OCR is required` |
| Encrypted / truncated | Encrypted / Malformed | same, more precise errors |
| Python package = CLI | no | **yes** (byte-identical output) |

Speed: most files stay sub-millisecond; 0.2.3 is at most ~60% slower on xlsx/xls (still < 0.3 ms). Negligible next to an LLM turn.

## How to test (repeatable)

Official fixtures: https://github.com/firecrawl/anydoc/tree/main/tests/fixtures

```bash
PY="$HERMES_HOME/hermes-agent/.venv/bin/python"
cd "$HERMES_HOME/hermes-agent"

$PY -c 'from tools.lazy_deps import ensure; ensure("tool.doc_extract", prompt=False); import anydoc, importlib.metadata as m; print(m.version("firecrawl-anydoc"), anydoc.__file__)'

$PY -c 'from tools.read_extract import extract_document_text; print(extract_document_text("/path/to/handmade-math.pptx"))'

$PY -m unittest tests.tools.test_read_extract.TestAnydocExtraction \
  tests.tools.test_read_extract.TestAnydocSizeCap \
  tests.tools.test_read_extract.TestAnydocAbsent \
  tests.tools.test_read_extract.TestAnydocInitLifecycle -v
```

## Why not `npx skills add firecrawl/anydoc`

The skills.sh installer writes into the agent's skills tree and can overwrite Hermes category directories with the same name. This routing skill replaces it: `read_file` first, the venv `anydoc` library only for stdlib gaps.
