import re

FOOTER_RE = re.compile(r"^(page \d+ of \d+|version \d+ \()", re.IGNORECASE)
DOT_LEADER_RE = re.compile(r"\.{3,}")
MAX_TITLE_LEN = 80
BASELINE = 2.0
TOLERANCE = 0.5


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


def page_spans(page):
    spans = []
    for block in page.get_text("rawdict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                chars = [c for c in span["chars"] if c["c"]]
                if chars:
                    spans.append({"y0": span["bbox"][1], "y1": span["bbox"][3],
                                  "x0": span["bbox"][0], "x1": span["bbox"][2],
                                  "font": span["font"], "size": span["size"], "chars": chars})
    return sorted(spans, key=lambda s: (s["y0"], s["x0"]))


def kept_chars(spans):
    out = []
    covered = None
    baseline = None
    for span in spans:
        if baseline is None or abs(span["y0"] - baseline) > BASELINE:
            baseline, covered = span["y0"], None
        if covered is not None and span["x1"] <= covered + TOLERANCE:
            continue
        chars = span["chars"]
        if covered is not None:
            chars = [c for c in chars if c["bbox"][0] >= covered - TOLERANCE]
            if not chars:
                continue
        covered = span["x1"] if covered is None else max(covered, span["x1"])
        out.extend({"c": c["c"], "x0": c["bbox"][0], "x1": c["bbox"][2], "y0": span["y0"],
                    "y1": span["y1"], "font": span["font"], "size": span["size"]} for c in chars)
    return sorted(out, key=lambda ch: (ch["y0"], ch["x0"]))


def group_lines(chars):
    lines = []
    for ch in chars:
        if lines and abs(ch["y0"] - lines[-1]["y0"]) <= BASELINE:
            lines[-1]["chars"].append(ch)
        else:
            lines.append({"y0": ch["y0"], "x0": ch["x0"], "chars": [ch]})
    return lines


def line_record(group):
    runs = []
    previous = None
    for ch in group["chars"]:
        if previous is not None and ch["x0"] - previous > TOLERANCE:
            runs.append([None, " "])
        if runs and runs[-1][0] == ch["font"]:
            runs[-1][1] += ch["c"]
        else:
            runs.append([ch["font"], ch["c"]])
        previous = ch["x1"]
    text = re.sub(r"\s+", " ", "".join(span_style(f, t) if f else " " for f, t in runs)).strip()
    return {"x0": group["x0"], "y0": group["y0"], "size": max(c["size"] for c in group["chars"]),
           "y1": max(c["y1"] for c in group["chars"]), "text": text}


def page_lines(page, drop=()):
    lines = []
    for group in group_lines(kept_chars(page_spans(page))):
        line = line_record(group)
        if not line["text"] or FOOTER_RE.match(line["text"].strip("*").lower()):
            continue
        if line["text"] in drop:
            continue
        lines.append(line)
    return lines


def repeated_texts(doc):
    if doc.page_count < 3:
        return frozenset()
    counts = {}
    for page in doc:
        seen = set()
        for line in page_lines(page):
            text = line["text"]
            if len(text) < MAX_TITLE_LEN and text not in seen:
                seen.add(text)
                counts[text] = counts.get(text, 0) + 1
    threshold = max(3, doc.page_count * 0.6)
    return frozenset(text for text, count in counts.items() if count >= threshold)


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
