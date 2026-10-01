#!/usr/bin/env python3
"""dumpdir: collect every file under a directory (default: .) and print them to stdout,
masking values that look sensitive.

Designed for safely pasting a project tree into an AI chat / clipboard.

Usage:
    dumpdir.py [DIR] [--no-mask]

- Skips junk directories (.git, node_modules, vendor, ...).
- Skips binary and very large files (prints a note instead).
- Skips known junk files (lockfiles, minified bundles, ...).
- Masks values whose *name* contains a sensitive stem (key, token, secret,
  pass, ...), unless the value is a known placeholder ($VAR, <token>,
  change_me, connect_secret, ...).
- Masks values matching known secret *formats* regardless of name:
  private key blocks, JWTs, AWS/GitHub/Slack/OpenAI/Anthropic/Google keys,
  user:pass inside connection strings.

Replacement text: ***REDACTED***
"""

import os
import re
import sys

# ---------------------------------------------------------------- config

EXCLUDE_DIRS = {
    ".git", ".svn", ".hg",
    "node_modules", "bower_components",
    "__pycache__", ".venv", "venv", "env", ".env.d",
    ".mypy_cache", ".pytest_cache", ".tox", ".ruff_cache",
    "vendor", "dist", "build", "out", "target",
    ".idea", ".vscode", ".next", ".nuxt", ".turbo", "coverage",
    ".dart_tool", "Pods", "Carthage", "DerivedData",
    "k8s", "helm",  # adjust freely
}

JUNK_FILES = re.compile(
    r"(?ix)"
    r"^(?:package-lock\.json|composer\.lock|yarn\.lock|pnpm-lock\.yaml"
    r"|Gemfile\.lock|poetry\.lock|bun\.lockb|Cargo\.lock"
    r"|.*\.min\.js|.*\.min\.css"
    r"|.*\.phar|.*\.DS_Store)$"
)

MAX_SIZE = 1_000_000          # files bigger than this are skipped
MASK = "***REDACTED***"

# ---------------------------------------------------------------- value patterns
# Applied unconditionally (format-based detection).
# MULTI_LINE_* run over the whole file text first (they span lines),
# the rest run per line.

MULTI_LINE_PATTERNS = [
    # PEM private keys (whole block, possibly inside a quoted string)
    (re.compile(
        r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----.*?"
        r"-----END [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----", re.S), "***PRIVATE_KEY***"),
]

VALUE_PATTERNS = [
    # base64 private key inside JSON strings
    (re.compile(r'("(?:private_?key|key|secret)"\s*:\s*")[A-Za-z0-9+/=]{64,}(")'), r"\1***\2"),
    # AWS access key ids
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "***AWS_KEY***"),
    # JWTs
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{16,}\.[A-Za-z0-9_\-]{16,}\.[A-Za-z0-9_\-]{8,}"), "***JWT***"),
    # GitHub tokens
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"), "***GITHUB_TOKEN***"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "***GITHUB_TOKEN***"),
    # Slack tokens
    (re.compile(r"\bxox[baprs][a-z]{0,2}-[A-Za-z0-9\-]{10,}\b"), "***SLACK_TOKEN***"),
    # OpenAI / Anthropic keys
    (re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{20,}\b"), "***ANTHROPIC_KEY***"),
    (re.compile(r"\bsk-[A-Za-z0-9]{28,}\b"), "***OPENAI_KEY***"),
    # Google API keys
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "***GOOGLE_KEY***"),
    # user:pass embedded in URLs  (scheme://user:pass@host)
    (re.compile(r"((?<=://)[^:@/\s]+):([^@/\s]+)(?=@)"), r"\1:" + MASK),
]

# ------------------------------------------------- sensitive *name* detection
# A name is sensitive if any of its _ . - separated parts hits these stems.

SENSITIVE_STEMS = {
    "key", "apikey", "keys", "token", "secret", "pass", "password",
    "passwd", "pwd", "private", "credential", "credentials", "auth",
    "signature", "signing", "secretkey", "passport", "ssn", "iban",
}

PLACEHOLDER_VALUES = re.compile(
    r"(?ix)"
    r"^\s*$"                       # empty
    r"|^\$[{\w\$]"                 # $VAR, ${VAR}
    r"|^%\(\w+\)%"                 # $(var)
    r"|^<[^>]*>$"                  # <your-token>
    r"|^(?:null|none|nil|na|n/a|-|off|on|no|yes|true|false|disabled|unset|not[-_ ]?set)$"
    r"|^(?:[0xoxzy]+|\*{3,}|1{3,}|0{4,})$"
    r"|^(?:example|sample|dummy|fake|mock)\w*$"
    r"|^change\w*$|^replace\w*$|^your\w*$|^enter\w*$|^input\w*$"
    r"|^insert\w*$|^put\w*$|^set\w*$|^some\w*$|^any\w*$"
    r"|^todo$|^tbd$|^fixme\w*$|^placeholder\w*$"
)

PURE_ALPHA_WITH_STEM = re.compile(r"^[a-z_]+$")

ASSIGN = re.compile(
    r"^\s*"
    r"(?:export\s+)?(?:const\s+|let\s+|var\s+|def\s+|val\s+|func\s+)?(?:public\s+|private\s+|static\s+|final\s+)*"
    r"[\"']?([A-Za-z_][A-Za-z0-9_.\-]*)[\"']?"
    r"\s*(?::\s+|:=\s*|=)"
    r"(.*)$"
)


def is_sensitive_name(name: str) -> bool:
    for part in re.split(r"[_\-.]", name.lower()):
        if part in SENSITIVE_STEMS:
            return True
    return any(s in name.lower() for s in ("apikey", "secretkey"))


def is_placeholder(value: str) -> bool:
    if PLACEHOLDER_VALUES.match(value):
        return True
    # "connect_secret", "client_secret", "mytoken" — letters only + sensitive stem
    v = value.lower()
    if len(v) <= 30 and PURE_ALPHA_WITH_STEM.match(v):
        return any(s in v for s in SENSITIVE_STEMS)
    return False


def mask_text(text: str) -> str:
    for pat, rep in MULTI_LINE_PATTERNS:
        text = pat.sub(rep, text)
    return "\n".join(mask_line(l) for l in text.splitlines())


def mask_line(line: str) -> str:
    for pat, rep in VALUE_PATTERNS:
        line = pat.sub(rep, line)
    m = ASSIGN.match(line)
    if m:
        name, value = m.group(1), m.group(2).strip()
        # strip surrounding quotes / trailing comment
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        value = re.split(r"\s+#", value)[0].strip()
        if value and is_sensitive_name(name) and not is_placeholder(value):
            line = m.group(0)[: m.start(2)] + MASK
    return line


# ---------------------------------------------------------------- file walk

def render_file(path: str, mask: bool) -> str:
    try:
        size = os.path.getsize(path)
    except OSError:
        return "  ⟨unreadable⟩\n"
    if size > MAX_SIZE:
        return "  ⟨large file, skipped: %.1fMB⟩\n" % (size / 1_000_000)
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as e:
        return "  ⟨error: %s⟩\n" % e
    if b"\x00" in raw[:8192]:
        return "  ⟨binary, skipped⟩\n"
    text = raw.decode("utf-8", errors="replace")
    if mask:
        text = mask_text(text)
    if text and not text.endswith("\n"):
        text += "\n"
    return text


def main() -> int:
    args = sys.argv[1:]
    mask = "--no-mask" not in args
    dirs = [a for a in args if a != "--no-mask"]
    root = dirs[0] if dirs else "."
    if not os.path.isdir(root):
        print("dumpdir: not a directory: %s" % root, file=sys.stderr)
        return 1

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDE_DIRS)
        for fn in sorted(filenames):
            if JUNK_FILES.match(fn):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, os.path.curdir)
            print("════════ %s ════════" % rel, flush=True)
            try:
                sys.stdout.write(render_file(path, mask))
            except Exception as e:  # never die on one file
                print("  ⟨error: %s⟩" % e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
