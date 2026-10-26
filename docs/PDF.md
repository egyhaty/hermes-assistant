# Persistent PDF support

The main Hermes image includes pinned ReportLab, WeasyPrint and pypdf, Pango, Arabic Noto fonts, DejaVu and Poppler. They are installed into `/opt/hermes/.venv/bin/python` during the image build. No package installation or elevated runtime privileges are needed.

Hermes discovers `karem-pdf` through its existing external skills directory. Use `/opt/karem/scripts/pdf_report.py` for Arabic/English JSON or HTML reports and save them under `/opt/data/workspace/reports` on the persistent volume. JSON text is escaped. HTML resource loading permits only local fonts, data URLs and the input directory's `assets/` tree; network URLs and other files are blocked.

Example:

```sh
/opt/hermes/.venv/bin/python /opt/karem/scripts/pdf_report.py --self-test --output /opt/data/workspace/reports/pdf-check.pdf --preview
```

The sample contains synthetic data, not an earlier user analysis. `--preview` renders page one; render and inspect every page of real deliverables with `pdftoppm`. Never claim delivery until a real file has been generated and verified. Existing output files require explicit `--overwrite`.

## Accepted deployment (2026-10-27)

The pinned image passed 50 offline tests and its immutable-image security scan (zero patchable HIGH/CRITICAL findings). A restricted, credential-free Kubernetes Pod generated the two-page bilingual sample; both rendered pages were inspected, including Arabic shaping, English direction, tables and page numbers. Arabic and Latin fonts are embedded. The real main gateway discovered `karem-pdf` and successfully wrote a sample PDF and preview to its persistent reports directory. Main gateway and dashboard became Ready; HTTPS login returned 200. See `build-receipts/pdf-runtime.json` for the exact image and CI receipts.
