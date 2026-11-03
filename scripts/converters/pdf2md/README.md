# pdf2md

Structured PDF -> Markdown converter. Output is a folder: `<stem>/<stem>.md` plus `images/`.

    uv run pdf2md.py document.pdf
    uv run pdf2md.py document.pdf --render-pages 19-20 --page-markers
    uv run pdf2md.py document.pdf -o my-output

Modules:

- `pdf_lines.py` - character-level layout extraction: overprinted spans deduped, bold/italic, repeated headers/footers dropped
- `pdf_outline.py` - heading levels from the bookmark tree, or from font sizes when the PDF has no outline
- `pdf_tables.py` - markdown tables from pymupdf cells, geometry rebuild as fallback
- `pdf_images.py` - embedded image extraction and page rendering
- `pdf2md.py` - entrypoint

Needs: pymupdf (declared in the script metadata, so `uv run` installs it).

    uv run --with pytest --with pymupdf pytest tests

