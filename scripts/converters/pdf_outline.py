import re

HEAD_MARK = {1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 6}
NUMBERED = re.compile(r"^\d+(?:\.\d+)*\.?\s")
BULLET_RE = re.compile(r"^[\u00b7\u00d8\u00a7\u00b0\u00b1\uf000-\uf0ff]\s*")


def normalize(text):
    return re.sub(r"[^0-9a-z]+", "", text.lower())


def strip_marks(text):
    return re.sub(r"\s+", " ", re.sub(r"[*_]+", " ", text)).strip()


def is_heading(title):
    title = title.strip()
    if not title or len(title) > 160 or BULLET_RE.match(title):
        return False
    return bool(NUMBERED.match(title))


def outline(doc):
    return [(level, title, page) for level, title, page in doc.get_toc() if is_heading(title)]


def heads_by_page(entries):
    grouped = {}
    for entry in entries:
        grouped.setdefault(entry[2], []).append(entry)
    return grouped


def match_heading(line, page_heads, used):
    text = normalize(line["text"])
    if not text:
        return None
    for index, (level, title, page) in enumerate(page_heads):
        if index in used:
            continue
        target = normalize(title)
        if not target or len(target) < 2:
            continue
        if text == target or text.startswith(target[:18]) or target.startswith(text[:18]):
            used.add(index)
            body = strip_marks(line["text"])
            name = title if len(target) >= len(text) else body
            return HEAD_MARK.get(level, 6), name
    return None
