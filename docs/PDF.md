# Persistent PDF support

The main Hermes image includes pinned ReportLab, WeasyPrint and pypdf, Pango, Arabic Noto fonts, DejaVu and Poppler. They are installed into `/opt/hermes/.venv/bin/python` during the image build. No package installation or elevated runtime privileges are needed.

Hermes discovers `karem-pdf` through its existing external skills directory. Use `/opt/karem/scripts/pdf_report.py` for Arabic/English JSON or HTML reports and save them under `/opt/data/workspace/reports` on the persistent volume. JSON text is escaped. HTML resource loading permits only local fonts, data URLs and the input directory's `assets/` tree; network URLs and other files are blocked.

Example:

```sh
/opt/hermes/.venv/bin/python /opt/karem/scripts/pdf_report.py --self-test --output /opt/data/workspace/reports/pdf-check.pdf --preview
```

The sample contains synthetic data, not an earlier user analysis. `--preview` renders page one; render and inspect every page of real deliverables with `pdftoppm`. Never claim delivery until a real file has been generated and verified. Existing output files require explicit `--overwrite`.
