---
name: karem-pdf
description: "Create and verify Arabic and English PDF reports, documents, summaries and exports using the installed PDF toolkit. Use whenever Karem asks for a PDF or an analysis as a downloadable document."
---

# PDF reports
The Kubernetes image already includes reportlab, weasyprint, pypdf, Pango, Arabic Noto fonts, DejaVu and Poppler. Use `/opt/hermes/.venv/bin/python` (also the normal `python` on PATH). Do not install packages dynamically or claim a missing PDF capability before checking this interpreter.

For Arabic or mixed-language reports, prefer the local helper:

```
/opt/hermes/.venv/bin/python /opt/karem/scripts/pdf_report.py --input /opt/data/workspace/reports/report.json --output /opt/data/workspace/reports/report.pdf --preview
```

JSON schema: `title` (string), optional `subtitle`, `direction` (`rtl` default or `ltr`), `sections` list. Each section may have `heading`, `paragraphs` (strings), `bullets` (strings), `new_page` (boolean), and `table` with `headers` and equally sized `rows`. Text is escaped automatically. For custom designs, --input also accepts UTF-8 HTML with CSS; use dir=rtl and dir=auto appropriately. Keep images in an assets/ directory beside the input. The helper allows local report assets and installed fonts only; external URLs and unrelated file access are blocked.

Use ReportLab for graphics or specifically programmed layouts, but do not draw raw Arabic text with it without proper shaping/bidi support. WeasyPrint is the default for correct Arabic typography and mixed text.

Verify actual output: helper reports PDF pages and bytes, and --preview renders the first page. For all pages run `pdftoppm -scale-to 1400 -png report.pdf /tmp/report-page` and inspect previews with the available image tool. Check Arabic joins, English order, columns, page breaks and clipping. Use pdfinfo, pdffonts or pypdf to check pages and embedded fonts; text extraction alone does not verify appearance.

Save user files in /opt/data/workspace/reports on the persistent volume. Never report success before the real PDF exists and has been verified. Return the actual file using the current platform's supported file-attachment mechanism; a path alone is not a delivered attachment. Keep reports local; no external PDF service is required. If an earlier report failed, find its existing content in the authorized conversation/workspace before asking Karem to repeat it; do not invent missing analysis.
