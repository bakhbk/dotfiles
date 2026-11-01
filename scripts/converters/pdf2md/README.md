# pdf2md

Structured PDF -> Markdown converter. Output is a folder: `<stem>/<stem>.md` plus `images/`.

    uv run pdf2md.py document.pdf
    uv run pdf2md.py document.pdf --render-pages 19-20 --page-markers
    uv run pdf2md.py document.pdf -o my-output

Modules:

- `pdf_lines.py` - layout-aware line extraction, bold/italic, footers, soft hyphens
- `pdf_outline.py` - heading levels from the PDF bookmark tree
- `pdf_tables.py` - markdown tables rebuilt from column geometry
- `pdf_images.py` - embedded image extraction and page rendering
- `pdf2md.py` - entrypoint

Needs: pymupdf (declared in the script metadata, so `uv run` installs it).
