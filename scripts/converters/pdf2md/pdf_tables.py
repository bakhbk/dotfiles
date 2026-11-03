import re


def cluster(values, tol=6.0):
    anchors = []
    for value in sorted(values):
        if anchors and value - anchors[-1][1] <= tol:
            anchors[-1] = (anchors[-1][0], value)
        else:
            anchors.append((value, value))
    return [round((a + b) / 2, 2) for a, b in anchors]


def index_of(value, anchors):
    return min(range(len(anchors)), key=lambda i: abs(anchors[i] - value))


def inside(line, bbox):
    return bbox[0] - 4 <= line["x0"] <= bbox[2] and bbox[1] - 4 <= line["y0"] <= bbox[3]


def region_indices(lines, bbox, skip):
    return [i for i, line in enumerate(lines) if i not in skip and inside(line, bbox)]


def cell_text(lines, indices):
    ordered = sorted(indices, key=lambda i: (lines[i]["y0"], lines[i]["x0"]))
    return re.sub(r"\s+", " ", " ".join(lines[i]["text"] for i in ordered)).strip()


def grid_from_cells(lines, table, skip):
    cells, used = [], set()
    for rect in table.cells:
        if not rect:
            continue
        indices = [i for i in region_indices(lines, rect, skip) if i not in used]
        if not indices:
            continue
        used.update(indices)
        cells.append({"x0": rect[0], "y0": rect[1], "text": cell_text(lines, indices)})
    if not cells:
        return {}, 0, 0, used
    xs = cluster([cell["x0"] for cell in cells])
    ys = cluster([cell["y0"] for cell in cells])
    grid = {}
    for cell in cells:
        key = (index_of(cell["y0"], ys), index_of(cell["x0"], xs))
        if len(grid.get(key, "")) < len(cell["text"]):
            grid[key] = cell["text"]
    return grid, len(ys), len(xs), used


def markdown_table(grid, nrows, ncols):
    used = [c for c in range(ncols) if any(grid.get((r, c)) for r in range(nrows))]
    if len(used) < 2:
        return ""
    rows = [[grid.get((r, c), "") for c in used] for r in range(nrows)]
    rows = [row for row in rows if any(row)]
    if len(rows) < 2:
        return ""

    def cells(row):
        return "| " + " | ".join(cell.replace("|", "\\|") for cell in row) + " |"

    return "\n".join([cells(rows[0]), "| " + " | ".join(["---"] * len(used)) + " |"]
                     + [cells(row) for row in rows[1:]])


def table_markdown(lines, table, skip):
    grid, nrows, ncols, used = grid_from_cells(lines, table, skip)
    if not grid:
        return "", set()
    return markdown_table(grid, nrows, ncols), used


def page_tables(page, lines, skip):
    tables = []
    for table in page.find_tables():
        indices = region_indices(lines, table.bbox, skip)
        if len(indices) < 2:
            continue
        markdown, consumed = table_markdown(lines, table, skip)
        if markdown:
            tables.append((markdown, consumed))
    return tables
