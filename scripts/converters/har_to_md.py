#!/usr/bin/env python3
# /// script
# dependencies = []
# ///

"""
har_to_md: Converts a HAR (HTTP Archive) file to a Markdown document.

Designed for safely pasting network logs into an AI chat.
Masks values that look sensitive (tokens, passwords, cookies) by default.

Usage:
    uv run har_to_md.py input.har                      # to stdout
    uv run har_to_md.py input.har -o digest.md         # to file
    uv run har_to_md.py input.har --max-body 8000 --no-mask
    uv run har_to_md.py input.har --method POST        # filter entries
    uv run har_to_md.py input.har --url auth          # filter by URL substring
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SENSITIVE_HEADER_RE = re.compile(
    r"authorization|cookie|set-cookie|token|session|password|x-auth", re.I
)
SENSITIVE_KEY_RE = re.compile(
    r"password|passwd|token|secret|api[_-]?key|session|auth", re.I
)
MAX_HEADERS_SHOWN = 12


def mask(text: str, no_mask: bool = False) -> str:
    if no_mask or not text:
        return text
    return "***" if len(text) < 20 else text[:8] + "***" + text[-4:]


def mask_json_keys(value, no_mask: bool, indent: int = 0) -> str:
    """Render JSON with proper nesting, masking values of sensitive keys."""
    pad = "  " * indent
    if no_mask:
        return json.dumps(value, ensure_ascii=False, indent=2)
    if isinstance(value, dict):
        if not value:
            return "{}"
        lines = []
        for k, v in value.items():
            if isinstance(v, (dict, list)) and v:
                lines.append(f"{pad}  {k}: {mask_json_keys(v, no_mask, indent + 1).lstrip()}")
            elif SENSITIVE_KEY_RE.search(str(k)):
                lines.append(f"{pad}  {k}: ***")
            else:
                lines.append(f"{pad}  {k}: {v!r}")
        return pad + "{\n" + ",\n".join(lines) + "\n" + pad + "}"
    if isinstance(value, list):
        if not value:
            return "[]"
        items = ",\n".join(mask_json_keys(v, no_mask, indent + 1).lstrip() for v in value)
        return f"{pad}[\n  {items}\n{pad}]"
    return str(value)


def try_pretty_json(text: str, no_mask: bool) -> str | None:
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if isinstance(data, (dict, list)):
        return mask_json_keys(data, no_mask)
    return text


def trunc(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n… [truncated, {len(text) - limit} chars omitted]"


def fmt_size(n: int) -> str:
    if n is None:
        return "?"
    if n < 1024:
        return f"{n}B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f}KB"
    return f"{n / 1024 / 1024:.1f}MB"


def render_entry(e: dict, no_mask: bool, max_body: int) -> list[str]:
    req, res = e["request"], e.get("response", {})
    url = req.get("url", "?")
    status = res.get("status", "?")
    ms = e.get("time") or 0
    out = [
        f"### {req.get('method', '?')} `{url}`",
        f"- **Status:** {status} {res.get('statusText', '')}".rstrip()
        + f" | **Time:** {ms / 1000:.1f} ms | **Size:** {fmt_size(res.get('content', {}).get('size'))}",
    ]

    # request headers (sensitive ones masked)
    rheaders = {h["name"]: h["value"] for h in req.get("headers", [])}
    interesting = [h for h in rheaders.items() if not re.match(r"^:|(accept|referer|user-agent|accept-)", h[0], re.I)]
    if interesting:
        lines = []
        for k, v in interesting[:MAX_HEADERS_SHOWN]:
            if SENSITIVE_HEADER_RE.search(k):
                v = mask(v, no_mask)
            lines.append(f"    {k}: {v}")
        out.append("**Request headers:**")
        out.extend(lines)

    # request body
    pdata = req.get("postData")
    if pdata:
        text = pdata.get("text", "")
        if pdata.get("mimeType", "").startswith("application/json"):
            text = try_pretty_json(text, no_mask) or text
        if text:
            out.append("**Request body:**")
            out.append("```")
            out.append(trunc(text, max_body))
            out.append("```")

    # response headers worth showing
    cheaders = {h["name"]: h["value"] for h in res.get("headers", [])}
    for k in ("content-type", "location", "www-authenticate"):
        if k in cheaders:
            out.append(f"**{k}:** {cheaders[k]}")

    # response body
    content = res.get("content", {})
    text = content.get("text", "")
    if text:
        if content.get("mimeType", "").startswith("application/json"):
            text = try_pretty_json(text, no_mask) or text
        out.append(f"**Response body** ({content.get('mimeType', '')}):")
        out.append("```")
        out.append(trunc(text, max_body))
        out.append("```")

    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Convert HAR file to a Markdown document")
    p.add_argument("har_file", type=Path)
    p.add_argument("-o", "--output", type=Path, help="write to file instead of stdout")
    p.add_argument("--max-body", type=int, default=4000, help="max body chars per entry (default 4000)")
    p.add_argument("--no-mask", action="store_true", help="do not mask sensitive values")
    p.add_argument("--method", help="only entries with this HTTP method (e.g. POST)")
    p.add_argument("--url", help="only entries whose URL contains this substring")
    args = p.parse_args()

    try:
        har = json.loads(args.har_file.read_text())
    except (OSError, ValueError) as e:
        print(f"error: cannot read {args.har_file}: {e}", file=sys.stderr)
        return 1

    log = har.get("log", {})
    entries = log.get("entries", [])
    if args.method:
        entries = [e for e in entries if e.get("request", {}).get("method", "").upper() == args.method.upper()]
    if args.url:
        entries = [e for e in entries if args.url.lower() in e.get("request", {}).get("url", "").lower()]

    lines = [f"# HAR: {args.har_file.name}", ""]
    if log.get("creator"):
        lines.append(f"Captured by {log['creator'].get('name', '?')} v{log['creator'].get('version', '?')}")
        lines.append("")

    for page in log.get("pages", []):
        t = page.get("pageTimings", {})
        if t:
            lines.append(f"Page `{page.get('title', '?')}` — content load {t.get('onContentLoad', 0) / 1000:.2f}s")
    if log.get("pages"):
        lines.append("")

    if not entries:
        lines.append("_No entries match the filter._")
    for i, e in enumerate(entries, 1):
        lines.append(f"## Entry {i}")
        lines.extend(render_entry(e, args.no_mask, args.max_body))
        lines.append("")

    text = "\n".join(lines)
    if args.output:
        args.output.write_text(text)
        print(f"wrote {args.output} ({len(text)} chars, {len(entries)} entries)")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
