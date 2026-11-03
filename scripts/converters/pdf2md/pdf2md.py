#!/usr/bin/env python3
# /// script
# dependencies = ["pymupdf"]
# ///
import argparse
import re
from pathlib import Path

import pymupdf

from pdf_images import gather_images
from pdf_lines import DOT_LEADER_RE, is_toc_page, merge_wrapped, page_lines
from pdf_outline import (
    BULLET_RE,
    heading_levels,
    heads_by_page,
    match_heading,
    normalize,
    outline,
    repeated_texts,
    size_heading,
    strip_marks,
)
from pdf_tables import page_tables


def render_toc(entries):
    lines = ["## Table of Contents", ""]
    for level, title, page in entries:
        lines.append(f"{'  ' * (level - 1)}- {title} (p. {page})")
    lines.append("")
    return lines


def find_headings(lines, page_heads, used, levels):
    found = {}
    for index, line in enumerate(lines):
        head = match_heading(line, page_heads, used) or size_heading(line, levels)
        if head:
            found[index] = head
    return found


def table_blocks(tables):
    starts, consumed = {}, set()
    for markdown, indices in tables:
        consumed.update(indices)
        starts[min(indices)] = markdown
    return starts, consumed


def line_block(line):
    if DOT_LEADER_RE.search(line["text"]):
        return ""
    bullet = BULLET_RE.match(line["text"])
    return f"- {line['text'][bullet.end():]}" if bullet else line["text"]


def render_page(page, number, page_heads, used, page_markers, images, levels, drop):
    lines = merge_wrapped(page_lines(page, drop))
    out = []
    if page_markers:
        out.append(f"<!-- page {number} -->")
    if is_toc_page(lines):
        return out
    headings = find_headings(lines, page_heads, used, levels)
    tables = page_tables(page, lines, set(headings))
    starts, consumed = table_blocks(tables)
    for index, line in enumerate(lines):
        if index in starts:
            out.append(starts[index])
        if index in consumed:
            continue
        if index in headings:
            level, text = headings[index]
            out.append("#" * level + " " + text)
            continue
        block = line_block(line)
        if block:
            out.append(block)
    for name in images:
        out.append(f"![page {number} image]({name})")
    return out


def clean_title(doc, drop):
    lines = page_lines(doc[0])
    title = (doc.metadata.get("title") or "").strip()
    page_text = " ".join(line["text"] for line in lines)
    if (title and not re.search(r"\.(html?|pdf|txt)$", title.lower())
            and normalize(title)[:20] in normalize(page_text)):
        return title, set()
    first = " ".join(strip_marks(line["text"]) for line in page_lines(doc[0], drop)[:2])
    return first or Path(doc.name).stem, {line["text"] for line in lines[:2]}


def convert(doc, page_markers=False, images_by_page=None):
    images_by_page = images_by_page or {}
    entries = outline(doc)
    levels = {} if entries else heading_levels(doc)
    drop = set(repeated_texts(doc))
    title, consumed = clean_title(doc, frozenset(drop))
    drop |= consumed
    grouped = heads_by_page(entries)
    used = {page: set() for page in grouped}
    body = [f"# {title}", ""]
    if entries:
        body.extend(render_toc(entries))
    for number in range(doc.page_count):
        page = doc[number]
        body.extend(render_page(page, number + 1, grouped.get(number + 1, []),
                                used.setdefault(number + 1, set()), page_markers,
                                images_by_page.get(number + 1, []), levels, drop))
    return "\n".join(body).strip() + "\n"


def resolve_output(source, requested):
    out_dir = Path(requested) if requested else Path(source).with_suffix("")
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir, out_dir / (Path(source).stem + ".md")


def main():
    parser = argparse.ArgumentParser(description="PDF -> Markdown folder (md + images)")
    parser.add_argument("files", nargs="+")
    parser.add_argument("-o", "--output", help="target folder (default: <stem>/)")
    parser.add_argument("--page-markers", action="store_true")
    parser.add_argument("--render-pages", default="", help="render these pages as PNG: all or 1-3,20")
    args = parser.parse_args()
    for source in args.files:
        path = Path(source)
        out_dir, target = resolve_output(path, args.output)
        with pymupdf.open(path) as doc:
            images = gather_images(doc, out_dir, args.render_pages)
            target.write_text(convert(doc, args.page_markers, images), encoding="utf-8")
        print(f"{path.name} -> {target} (+{sum(len(v) for v in images.values())} images)")


if __name__ == "__main__":
    main()
