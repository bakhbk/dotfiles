import re

FOOTER_RE = re.compile(r"^(page \d+ of \d+|version \d+ \()", re.I)
DOT_LEADER_RE = re.compile(r"\.{3,}")


def span_text(span):
    text = span["text"].strip()
    if not text:
        return ""
    font = span["font"].lower()
    if "bold" in font:
        return f"**{text}**"
    if "italic" in font:
        return f"_{text}_"
    return text


def line_text(line):
    parts = [span_text(span) for span in line["spans"]]
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def page_lines(page):
    lines = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for ln in block["lines"]:
            text = line_text(ln)
            if not text or FOOTER_RE.match(text.strip("*").lower()):
                continue
            bbox = ln["bbox"]
            lines.append({"x0": bbox[0], "y0": bbox[1], "y1": bbox[3], "text": text})
    return sorted(lines, key=lambda l: (l["y0"], l["x0"]))


def merge_wrapped(lines):
    merged = []
    i = 0
    while i < len(lines):
        line = lines[i]
        number = re.fullmatch(r"\*+([0-9]+(?:\.[0-9]+)*\.?)\*+", line["text"])
        if number and i + 1 < len(lines) and lines[i + 1]["x0"] > line["x0"] + 10:
            merged.append({
                "x0": line["x0"],
                "y0": line["y0"],
                "y1": lines[i + 1]["y1"],
                "text": f"{number.group(1)} {lines[i + 1]['text']}",
            })
            i += 2
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if (line["text"].endswith("-") and nxt and nxt["y0"] - line["y1"] < 6.0
                and abs(nxt["x0"] - line["x0"]) < 6.0):
            merged.append({
                "x0": line["x0"],
                "y0": line["y0"],
                "y1": lines[i + 1]["y1"],
                "text": line["text"] + lines[i + 1]["text"],
            })
            i += 2
            continue
        merged.append(line)
        i += 1
    return merged


def is_toc_page(lines):
    if len(lines) < 10:
        return False
    leaders = sum(1 for l in lines if DOT_LEADER_RE.search(l["text"]))
    return leaders >= max(5, len(lines) // 3)
