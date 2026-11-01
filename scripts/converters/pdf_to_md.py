#!/usr/bin/env python3
# /// script
# dependencies = ["pymupdf"]
# ///
import argparse
import re
from pathlib import Path

import pymupdf

from pdf_lines import page_lines, merge_wrapped, is_toc_page
from pdf_outline import outline, heads_by_page, match_heading, BULLET_RE
from pdf_tables import page_tables


def render_toc(entries):
    lines = ["## Table of Contents", ""]
    for level, title, page in entries:
        lines.append(f"{'  ' * (level - 1)}- {title} (p. {page})")
    lines.append("")
    return lines


def render_page(page, number, page_heads, used, page_markers):
    lines = merge_wrapped(page_lines(page))
    out = []
    if page_markers:
        out.append(f"<!-- page {number} -->")
    if is_toc_page(lines):
        return out
    headings = {}
    for index, line in enumerate(lines):
        found = match_heading(line, page_heads, used)
        if found:
            headings[index] = found
    tables = page_tables(page, lines, set(headings))
    consumed = set()
    starts = {}
    for markdown, indices in tables:
        consumed.update(indices)
        starts[min(indices)] = markdown
    for index, line in enumerate(lines):
        if index in starts:
            out.append(starts[index])
        if index in consumed:
            continue
        if index in headings:
            level, text = headings[index]
            out.append("#" * level + " " + text)
            continue
        if re.search(r"\.{4,}", line["text"]):
            continue
        bullet = BULLET_RE.match(line["text"])
        out.append(f"- {line['text'][bullet.end():]}" if bullet else line["text"])
    return out


def document_title(doc):
    title = (doc.metadata.get("title") or "").strip()
    if title:
        return title
    lines = page_lines(doc[0])
    if not lines:
        return Path(doc.name).stem
    return " ".join(re.sub(r"[*_]", "", line["text"]).strip() for line in lines[:2])


def convert(doc, page_markers=False):
    entries = outline(doc)
    grouped = heads_by_page(entries)
    used = {page: set() for page in grouped}
    body = [f"# {document_title(doc)}", ""]
    if entries:
        body.extend(render_toc(entries))
    for number in range(doc.page_count):
        page = doc[number]
        body.extend(render_page(page, number + 1, grouped.get(number + 1, []),
                                used.setdefault(number + 1, set()), page_markers))
    return "\n".join(body).strip() + "\n"


def main():
    parser = argparse.ArgumentParser(description="PDF -> Markdown using the document outline and geometry")
    parser.add_argument("files", nargs="+")
    parser.add_argument("-o", "--output")
    parser.add_argument("--page-markers", action="store_true")
    args = parser.parse_args()
    for source in args.files:
        path = Path(source)
        target = Path(args.output) if args.output and len(args.files) == 1 else path.with_suffix(".md")
        with pymupdf.open(path) as doc:
            target.write_text(convert(doc, page_markers=args.page_markers), encoding="utf-8")
        print(f"{path.name} -> {target}")


if __name__ == "__main__":
    main()
