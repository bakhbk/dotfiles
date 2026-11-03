import re

FOOTER_RE = re.compile(r"^(page \d+ of \d+|version \d+ \()", re.IGNORECASE)
DOT_LEADER_RE = re.compile(r"\.{3,}")
MAX_TITLE_LEN = 80
BASELINE = 2.0
TOLERANCE = 1.2
MERGE_GAP = 6.0
EDGE = 0.15


def span_style(font, text):
    lead = text[:len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()):]
    core = text.strip()
    if not core:
        return text
    low = font.lower()
    if "bold" in low or "medium" in low:
        return f"{lead}**{core}**{trail}"
    if "italic" in low or "oblique" in low:
        return f"{lead}_{core}_{trail}"
    return text


def page_units(page):
    units = []
    for block in page.get_text("rawdict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            spans = [{"y0": s["bbox"][1], "y1": s["bbox"][3], "x0": s["bbox"][0],
                      "x1": s["bbox"][2], "font": s["font"], "size": s["size"],
                      "chars": [c for c in s["chars"] if c["c"]]} for s in line["spans"]]
            spans = [s for s in spans if s["chars"]]
            if spans:
                units.append({"y0": line["bbox"][1], "y1": line["bbox"][3],
                              "x0": min(s["x0"] for s in spans),
                              "x1": max(s["x1"] for s in spans), "spans": spans})
    return sorted(units, key=lambda u: (u["y0"], u["x0"]))


def is_duplicate(char, placed):
    x0 = char["bbox"][0]
    return any(abs(p[0] - x0) <= TOLERANCE and p[2] == char["c"] for p in placed)


def dedup_units(units):
    kept, placed, baseline = [], [], None
    for unit in units:
        if baseline is None or abs(unit["y0"] - baseline) > BASELINE:
            baseline, placed = unit["y0"], []
        spans = []
        for span in sorted(unit["spans"], key=lambda s: s["x0"]):
            chars = [c for c in span["chars"] if not is_duplicate(c, placed)]
            if not chars:
                continue
            placed.extend((c["bbox"][0], c["bbox"][2], c["c"]) for c in chars)
            spans.append({"x0": span["x0"], "x1": span["x1"],
                          "text": "".join(c["c"] for c in chars),
                          "font": span["font"], "size": span["size"]})
        if spans:
            unit = dict(unit, spans=spans, x0=min(s["x0"] for s in spans))
            kept.append(unit)
    return kept


def join_adjacent(units):
    out = []
    for unit in units:
        previous = out[-1] if out else None
        if (previous and abs(unit["y0"] - previous["y0"]) <= BASELINE
                and unit["x0"] - previous["x1"] < MERGE_GAP):
            previous["spans"].extend(unit["spans"])
            previous["x1"] = max(previous["x1"], unit["x1"])
            previous["y1"] = max(previous["y1"], unit["y1"])
        else:
            out.append(unit)
    return out


PUNCT_RE = re.compile(r"([*_]{1,2})\s+([.,;:!?])")


def line_record(unit):
    text = re.sub(r"\s+", " ", " ".join(
        span_style(span["font"], span["text"]) for span in unit["spans"])).strip()
    return {"x0": unit["x0"], "y0": unit["y0"], "y1": unit["y1"],
            "size": max(span["size"] for span in unit["spans"]),
            "text": PUNCT_RE.sub(r"\1\2", text)}


def page_lines(page, drop=()):
    lines = []
    for unit in join_adjacent(dedup_units(page_units(page))):
        line = line_record(unit)
        if not line["text"] or FOOTER_RE.match(line["text"].strip("*").lower()):
            continue
        if line["text"] in drop:
            continue
        lines.append(line)
    return lines


def merge_wrapped(lines):
    merged = []
    i = 0
    while i < len(lines):
        line = lines[i]
        number = re.fullmatch(r"\*+([0-9]+(?:\.\d+)*\.?)\*+", line["text"])
        if number and i + 1 < len(lines) and lines[i + 1]["x0"] > line["x0"] + 10:
            merged.append({
                "x0": line["x0"],
                "y0": line["y0"],
                "y1": lines[i + 1]["y1"],
                "size": max(line["size"], lines[i + 1]["size"]),
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
                "y1": nxt["y1"],
                "size": max(line["size"], nxt["size"]),
                "text": line["text"] + nxt["text"],
            })
            i += 2
            continue
        merged.append(line)
        i += 1
    return merged


def is_toc_page(lines):
    if len(lines) < 10:
        return False
    leaders = sum(1 for line in lines if DOT_LEADER_RE.search(line["text"]))
    return leaders >= max(5, len(lines) // 3)
