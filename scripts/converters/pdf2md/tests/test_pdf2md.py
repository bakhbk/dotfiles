from pathlib import Path

import pymupdf

from pdf2md import convert, resolve_output
from pdf_lines import page_lines
from pdf_outline import heading_levels, repeated_texts
from pdf_tables import markdown_table, page_tables


def page_with(spans):
    doc = pymupdf.open()
    page = doc.new_page()
    for text, x, y, size in spans:
        page.insert_text((x, y), text, fontsize=size)
    return doc, page


def first_x_of(page, needle):
    for block in page.get_text("rawdict")["blocks"]:
        for line in block["lines"]:
            for span in line["spans"]:
                text = "".join(c["c"] for c in span["chars"])
                index = text.find(needle)
                if index >= 0:
                    return span["chars"][index]["bbox"][0]
    return 0.0


def test_overlap_is_merged_once():
    _doc, page = page_with([
        ("The server with the id 113610", 40, 50, 10),
        ("world", 60, 70, 10),
        ("world", 60, 70, 10),
    ])
    overlay = first_x_of(page, "113610")
    page.insert_text((overlay, 50), "113610 has been renewed with", fontsize=10)
    lines = page_lines(page)
    assert len(lines) == 2
    assert sum(line["text"].count("world") for line in lines) == 1
    assert lines[0]["text"] == "The server with the id 113610 has been renewed with"


def test_table_columns_match_cells():
    path = Path(__file__).parent / "fixtures/table.pdf"
    if not path.exists():
        return
    with pymupdf.open(path) as doc:
        page = doc[1]
        tables = page_tables(page, page_lines(page), set())
    markdown = tables[0][0]
    header = markdown.splitlines()[0].strip("|").split("|")
    assert len(header) == 2
    assert all(cell.strip() for cell in header)


def test_size_headings_when_no_outline():
    doc, page = page_with([
        ("Big Section", 40, 50, 20),
        ("body text here", 40, 70, 10),
    ])
    levels = heading_levels(doc)
    assert page_lines(page)[0]["size"] in levels
    markdown = convert(doc)
    assert markdown.startswith("# Big Section")
    assert "body text here" in markdown


def test_repeated_footer_dropped():
    doc = pymupdf.open()
    for i in range(4):
        page = doc.new_page()
        page.insert_text((40, 60), f"unique content {i}")
        page.insert_text((40, 790), "MVPS.net www.mvps.net")
    drop = repeated_texts(doc)
    assert "MVPS.net www.mvps.net" in drop
    assert "MVPS.net" not in convert(doc)


def test_html_metadata_title_is_not_used():
    doc, _page = page_with([("Real Report Title", 40, 50, 18)])
    doc.set_metadata({"title": "doc.html"})
    assert convert(doc).startswith("# Real Report Title")


def test_markdown_escapes_pipes_and_drops_empty_columns():
    grid = {(0, 0): "a|b", (0, 1): "", (0, 2): "c",
            (1, 0): "d", (1, 1): "", (1, 2): "e"}
    markdown = markdown_table(grid, 2, 3)
    assert "\\|" in markdown
    header = markdown.splitlines()[0]
    assert header.count("|") - header.count("\\|") == 3


def test_two_files_get_two_targets(tmp_path):
    out = tmp_path / "out"
    assert resolve_output(Path("a.pdf"), out)[1].name == "a.md"
    assert resolve_output(Path("b.pdf"), out)[1].name == "b.md"


def test_title_not_duplicated_in_body():
    doc, _page = page_with([("Real Report Title", 40, 50, 18), ("body text", 40, 70, 10)])
    doc.set_metadata({"title": "scan.html"})
    markdown = convert(doc)
    assert markdown.count("Real Report Title") == 1
    assert markdown.startswith("# Real Report Title")


def test_punctuation_glued_to_markers():
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((40, 50), "The cost has been", fontsize=10)
    page.insert_text((120, 50), " 4 EUR", fontsize=10, fontname="Helvetica-Bold")
    page.insert_text((160, 50), " .", fontsize=10)
    assert page_lines(page)[0]["text"] == "The cost has been **4 EUR**."
