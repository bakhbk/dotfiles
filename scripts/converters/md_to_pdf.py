#!/usr/bin/env python3
"""md_to_pdf.py — Markdown → PDF (pandoc + headless Chrome).

Usage:
    md_to_pdf.py document.md
    md_to_pdf.py document.md -o document.pdf --css my.css --title "Document"
    md_to_pdf.py document.md --keep-html --verbose

Requirements:
    pandoc  (brew install pandoc)
    Google Chrome (or chromium in PATH)

How it works: pandoc generates HTML with embedded styles → headless Chrome prints the PDF.
WeasyPrint/typst are not used to avoid adding heavy dependencies.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_CSS = """
body {
  font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
  font-size: 11.5px;
  line-height: 1.4;
  max-width: 860px;
  margin: 0 auto;
  padding: 22px 26px;
  color: #1f2937;
}
h1 { font-size: 21px; margin-bottom: 4px; }
h2 { font-size: 15px; margin-top: 18px; border-bottom: 1px solid #d1d5db; padding-bottom: 4px; }
h3 { font-size: 13px; margin-top: 12px; }
table { border-collapse: collapse; width: 100%; font-size: 11px; }
th, td { border: 1px solid #cbd5e1; padding: 6px 8px; vertical-align: top; }
blockquote { border-left: 3px solid #6b7280; margin: 8px 0; padding: 6px 10px; background: #f8fafc; }
code { background: #f3f4f6; padding: 1px 4px; font-size: 11px; }
hr { border: none; border-top: 1px solid #e5e7eb; margin: 14px 0; }
ul, ol { margin: 6px 0 6px 18px; }
@page { margin: 12mm; }
"""

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "chromium",
    "google-chrome",
    "chrome",
]


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def find_browser() -> str:
    for c in CHROME_CANDIDATES:
        if Path(c).exists() or shutil.which(c):
            return c
    die("Chrome/Chromium not found. Install Chrome or add chromium to PATH.")


def run(cmd: list[str], quiet: bool = True) -> str:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        die(f"Command failed: {' '.join(cmd)}\n{res.stderr.strip()}")
    return res.stdout


def markdown_to_html(md_path: Path, css_path: Path, title: str) -> Path:
    html_path = Path(tempfile.mkdtemp(prefix="md2pdf_")) / "doc.html"
    run(["pandoc", str(md_path), "-o", str(html_path), "--css", str(css_path),
         "--metadata", f"title={title}"])
    return html_path


def html_to_pdf(html_path: Path, pdf_path: Path, browser: str, verbose: bool) -> None:
    cmd = [browser, "--headless=new", "--disable-gpu", "--no-sandbox",
           "--no-pdf-header-footer", f"--print-to-pdf={pdf_path}", str(html_path)]
    out = run(cmd, quiet=not verbose)
    if verbose and out:
        print(out.strip())


def page_count(pdf_path: Path) -> str:
    if sys.platform != "darwin":
        return "?"
    res = subprocess.run(["mdls", "-name", "kMDItemNumberOfPages", str(pdf_path)],
                         capture_output=True, text=True)
    return res.stdout.strip().split("=")[-1].strip() or "?"


def main() -> None:
    p = argparse.ArgumentParser(description="Markdown → PDF (pandoc + Chrome headless)")
    p.add_argument("input", help="Markdown file")
    p.add_argument("-o", "--output", help="PDF file (defaults to the same directory as the input)")
    p.add_argument("--css", help="Custom CSS file instead of the built-in styles")
    p.add_argument("--title", help="Document title (affects the filename in the PDF)")
    p.add_argument("--keep-html", action="store_true", help="Keep the intermediate HTML file")
    p.add_argument("--verbose", action="store_true", help="Show Chrome output")
    args = p.parse_args()

    md_path = Path(args.input).expanduser()
    if not md_path.exists():
        die(f"File not found: {md_path}")
    if shutil.which("pandoc") is None:
        die("pandoc not found. Install it with: brew install pandoc")

    pdf_path = Path(args.output).expanduser() if args.output else md_path.with_suffix(".pdf")
    title = args.title or md_path.stem

    browser = find_browser()
    tmp_css_dir = None
    if not args.css:
        tmp_css_dir = tempfile.mkdtemp(prefix="md2pdf_css_")
        css_path = Path(tmp_css_dir) / "style.css"
        css_path.write_text(DEFAULT_CSS, encoding="utf-8")
    else:
        css_path = Path(args.css).expanduser()

    html_path = markdown_to_html(md_path, css_path, title)

    try:
        if args.keep_html:
            kept = Path.cwd() / f"{md_path.stem}.html"
            shutil.copyfile(html_path, kept)
            print(f"HTML: {kept}")

        html_to_pdf(html_path, pdf_path, browser, args.verbose)
    finally:
        # Remove temporary files.
        if tmp_css_dir:
            shutil.rmtree(tmp_css_dir, ignore_errors=True)
        shutil.rmtree(html_path.parent, ignore_errors=True)

    size = pdf_path.stat().st_size
    print(f"Done: {pdf_path} ({size // 1024} KB, pages: {page_count(pdf_path)})")


if __name__ == "__main__":
    main()
