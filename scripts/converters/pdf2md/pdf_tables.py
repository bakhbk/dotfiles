import re


def cluster(values, tol=6.0):
    anchors = []
    for value in sorted(values):
        if anchors and value - anchors[-1][1] <= tol:
            anchors[-1] = (anchors[-1][0], value)
        else:
            anchors.append((value, value))
    return [round((a + b) / 2, 2) for a, b in anchors]


def column_of(x0, anchors):
    return min(range(len(anchors)), key=lambda i: abs(anchors[i] - x0))


def inside(line, bbox):
    return bbox[0] - 4 <= line["x0"] <= bbox[2] and bbox[1] - 4 <= line["y0"] <= bbox[3]


def region_indices(lines, bbox, skip):
    return [i for i, line in enumerate(lines) if i not in skip and inside(line, bbox)]


def cells_from_lines(lines, indices, anchors):
    by_col = [[] for _ in anchors]
    for index in indices:
        by_col[column_of(lines[index]["x0"], anchors)].append(index)
    cells = []
    for col, col_lines in enumerate(by_col):
        current = None
        for index in sorted(col_lines, key=lambda i: lines[i]["y0"]):
            line = lines[index]
            if current and line["y0"] - current["last"] < 15.0:
                glue = "" if current["text"].endswith("-") else " "
                current["text"] = f"{current['text']}{glue}{line['text']}".strip()
                current["y1"] = line["y1"]
                current["last"] = line["y0"]
                current["lines"].append(index)
            else:
                current = {"col": col, "y0": line["y0"], "y1": line["y1"],
                           "last": line["y0"], "text": line["text"], "lines": [index]}
                cells.append(current)
    return cells


def rows_from_cells(cells):
    rows = []
    for cell in sorted(cells, key=lambda c: c["y0"]):
        if rows and cell["y0"] - rows[-1]["y0"] <= 12.0:
            rows[-1]["cells"][cell["col"]] = cell
        else:
            rows.append({"y0": cell["y0"], "cells": {cell["col"]: cell}})
    return [row for row in rows if len(row["cells"]) >= 2]


def markdown_table(rows, ncols):
    used = [c for c in range(ncols) if any(c in row["cells"] for row in rows)]

    def cells(row):
        return " | ".join(
            row["cells"].get(c, {}).get("text", "").replace("|", "\\|") for c in used
        )

    lines = [f"| {cells(rows[0])} |", "| " + " | ".join(["---"] * len(used)) + " |"]
    lines += [f"| {cells(row)} |" for row in rows[1:]]
    return "\n".join(lines)


def table_from_bbox(lines, bbox, skip):
    indices = region_indices(lines, bbox, skip)
    anchors = cluster([lines[index]["x0"] for index in indices])
    if len(anchors) < 2:
        return None, set()
    rows = rows_from_cells(cells_from_lines(lines, indices, anchors))
    if len(rows) < 3:
        return None, set()
    consumed = {index for row in rows for cell in row["cells"].values() for index in cell["lines"]}
    return markdown_table(rows, len(anchors)), consumed


def table_markdown(table):
    try:
        rows = table.extract()
    except (AttributeError, TypeError, NotImplementedError):
        return ""
    rows = [["" if cell is None else re.sub(r"\s+", " ", str(cell)).strip()
             for cell in row] for row in rows]
    if len(rows) < 2:
        return ""
    used = [i for i in range(len(rows[0])) if any(row[i] for row in rows)]
    if len(used) < 2:
        return ""

    def cells(row):
        return "| " + " | ".join(cell.replace("|", "\\|") for cell in row) + " |"

    header = cells([rows[0][i] for i in used])
    lines = [header, "| " + " | ".join(["---"] * len(used)) + " |"]
    lines += [cells([row[i] for i in used]) for row in rows[1:]]
    return "\n".join(lines)


def page_tables(page, lines, skip):
    tables = []
    for table in page.find_tables():
        indices = region_indices(lines, table.bbox, skip)
        if len(indices) < 2:
            continue
        markdown = table_markdown(table)
        if markdown:
            tables.append((markdown, set(indices)))
            continue
        markdown, consumed = table_from_bbox(lines, table.bbox, skip)
        if markdown:
            tables.append((markdown, consumed))
    return tables
