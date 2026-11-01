import re

import pymupdf


def safe_name(text):
    return re.sub(r"[^0-9a-zA-Z._-]+", "-", text).strip("-").lower()


def image_path(out_dir, page_number, index, ext):
    name = f"page-{page_number}.{ext}" if index is None else f"page-{page_number}-{index}.{ext}"
    path = out_dir / "images" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path, f"images/{name}"


def extract_embedded(doc, out_dir, page_number, min_side=120):
    saved = []
    for index, info in enumerate(doc[page_number - 1].get_images(full=True), start=1):
        xref = info[0]
        if min(info[2], info[3]) < min_side:
            continue
        image = doc.extract_image(xref)
        path, name = image_path(out_dir, page_number, index, image["ext"])
        path.write_bytes(image["image"])
        saved.append(name)
    return saved


def render_page(doc, out_dir, page_number, dpi=150):
    path, name = image_path(out_dir, page_number, None, "png")
    pix = doc[page_number - 1].get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72))
    path.write_bytes(pix.tobytes("png"))
    return [name]


def parse_pages(spec, page_count):
    if spec == "all":
        return list(range(1, page_count + 1))
    pages = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        low, _, high = part.partition("-")
        start = int(low)
        end = int(high) if high else start
        pages.extend(range(max(1, start), min(page_count, end) + 1))
    return pages


def page_images(doc, out_dir, page_number, rendered):
    if page_number in rendered:
        return render_page(doc, out_dir, page_number)
    return extract_embedded(doc, out_dir, page_number)
