#!/usr/bin/env python3
"""aigent context compaction + on-demand retrieval (BETA, off by default).

Three-zone context:
  HEAD   system + first user task              — never compacted
  MIDDLE tool groups → LLM state-summaries     — the compression zone
  TAIL   last N groups                         — never compacted

Originals of compacted groups are stored in <AIGENT_DIR>/details/<ref>.json
(the canonical aigent log is untouched). The tool get_details(ref) restores
a group as ONE wrapped tool result, appended at the end of the message list
(KV-cache friendly: stable prefix + changing suffix). Restored content is
TTL-bounded and re-retrievable; refs/files live until cleanup() at exit.

Triggers (prompt tokens, from stream usage or estimate):
  > target → background summarization (runs during the next tool window)
  > hard   → synchronous compact before the next LLM call

All knobs via AIGENT_COMPACT_* env, overridable through make(cfg).
"""
import hashlib
import json
import os
import threading
import time

import requests

DEFAULTS = {
    "target": 32_768,        # prompt tokens → schedule background compact
    "hard": 65_536,          # prompt tokens → synchronous compact
    "tail_groups": 10,       # newest groups never compacted
    "reserve": 0.15,         # fraction of ctx_limit kept free for retrieval
    "retrieve_ttl": 5,       # turns restored content stays in history
    "ctx_limit": 262_144,    # server context window (for retrieval budget)
    "summarize_max": 1200,   # max output tokens per group summary
    "fragment_limit": 24_000,# max chars fed to the summarizer per group
    "fail_break": 3,         # consecutive summarize failures → disable
}

SUMMARY_PROMPT = """\
You are a context condenser for a coding agent. The conversation fragment below
will be removed from the agent's context and replaced by your summary.
Compress it into a structured state summary so the agent can continue without it.

Rules:
- Preserve exact file paths, error messages, numbers, and test outcomes.
- If the fragment contains an image result — note only that an image was shown and its path.
- No preamble, no commentary. Max {max_tokens} tokens.

Output format:
STATE: what was true after this step (1-2 lines)
COMPLETED: what was done (bullets)
FILES: paths touched and how (one per line, or "none")
FACTS: key facts, decisions, constraints (bullets, or "none")
OPEN: unresolved items (bullets, or "none")

FRAGMENT:
{fragment}
"""


def make(cfg: dict):
    """Build a CompactManager. cfg: aigent_dir, llm_base_url, llm_api_key,
    llm_model, status, log + optional knob overrides."""
    full = dict(cfg or {})
    for k in DEFAULTS:  # defaults < env < cfg
        full[k] = DEFAULTS[k]
    for k in DEFAULTS:
        env = os.getenv(f"AIGENT_COMPACT_{k.upper()}")
        if env:
            full[k] = type(DEFAULTS[k])(env)
    for k in DEFAULTS:
        v = (cfg or {}).get(k)
        if v is not None:
            full[k] = v
    return CompactManager(full)


class CompactManager:
    def __init__(self, cfg):
        self.cfg = cfg
        self.dir = os.path.join(cfg["aigent_dir"], "details")
        os.makedirs(self.dir, exist_ok=True)
        self.status = cfg.get("status") or (lambda s: None)
        self.log = cfg.get("log") or (lambda s="": None)
        self.headers = {"Content-Type": "application/json",
                        "Authorization": f"Bearer {cfg.get('llm_api_key', 'none')}"}
        self._lock = threading.Lock()
        self._bg = None
        self._busy = False
        self._cancel = False
        self._applied = set()   # refs already in context as summaries
        self._retrieved = []    # [msg_dict, ref, turn] — TTL tracking
        self._fails = 0
        self._disabled = False
        self.last_prompt = 0
        self.n_compacts = 0

    # ------------------------------------------------------------------ est

    @staticmethod
    def _est(msgs):
        """Cheap token estimate: ~4 chars/token, data-URLs ~3."""
        n = 0
        for m in msgs:
            c = m.get("content")
            if isinstance(c, str):
                n += len(c) // 4
            elif isinstance(c, list):
                for p in c:
                    u = (p or {}).get("image_url", {}).get("url", "")
                    n += len(u) // 3 if u.startswith("data:") else 800
            for tc in m.get("tool_calls") or []:
                n += len(tc["function"]["arguments"]) // 4
            n += 8
        return n

    # --------------------------------------------------------------- groups

    @staticmethod
    def _groups(messages):
        """head(2) excluded; tool-call group = assistant(tool_calls)+tool msgs;
        every other message — solo group (kept as-is on apply)."""
        groups, cur = [], None
        for i, m in enumerate(messages):
            if i < 2:
                continue
            if m.get("role") == "assistant" and m.get("tool_calls"):
                cur = [m]
                groups.append(cur)
            elif m.get("role") == "tool":
                if cur is None:
                    cur = []
                    groups.append(cur)
                cur.append(m)
            else:
                if cur is not None:
                    cur = None
                groups.append([m])
        return groups

    @staticmethod
    def _ref_of(group):
        h = hashlib.sha256(
            json.dumps(group, ensure_ascii=False, default=str).encode()
        ).hexdigest()
        return h[:8]

    @staticmethod
    def _label(group):
        names = []
        for m in group:
            if m.get("role") == "assistant":
                for tc in m.get("tool_calls") or []:
                    names.append(tc["function"]["name"])
        return ", ".join(dict.fromkeys(names)) or "msg"

    # ------------------------------------------------------------- fragment

    @staticmethod
    def _render(group, per_msg_limit):
        parts = []
        for m in group:
            role = m.get("role")
            if role == "assistant":
                for tc in m.get("tool_calls") or []:
                    fn = tc["function"]
                    parts.append(f"ASSISTANT calls {fn['name']}"
                                 f"({fn['arguments'][:2000]})")
                if m.get("content"):
                    parts.append(f"ASSISTANT: {str(m['content'])[:2000]}")
            elif role == "tool":
                c = m.get("content")
                if isinstance(c, list):
                    parts.append("[image result, content omitted]")
                else:
                    s = str(c)
                    if per_msg_limit:
                        s = s[:per_msg_limit]
                    parts.append(f"TOOL: {s}")
            elif role == "user":
                parts.append(f"USER: {str(m.get('content', ''))[:1000]}")
        return "\n\n".join(parts)

    def _fragment(self, group):
        frag = self._render(group, per_msg_limit=6000)
        return frag[:self.cfg["fragment_limit"]]

    # ------------------------------------------------------------ summarize

    def _summarize(self, group, ref):
        prompt = (SUMMARY_PROMPT
                  .replace("{max_tokens}", str(self.cfg["summarize_max"]))
                  .replace("{fragment}", self._fragment(group)))
        payload = {"model": self.cfg["llm_model"],
                   "messages": [{"role": "user", "content": prompt}],
                   "temperature": 0.1,
                   "max_tokens": self.cfg["summarize_max"],
                   "stream": False,
                   "enable_thinking": False}
        t0 = time.monotonic()
        try:
            r = requests.post(self.cfg["llm_base_url"].rstrip("/")
                              + "/chat/completions",
                              json=payload, headers=self.headers,
                              timeout=(10, 300))
            if r.status_code >= 400:
                self.log(f"⚠️  compact summarize HTTP {r.status_code}: "
                         f"{r.text[:200]}")
                return None
            c = (r.json()["choices"][0]["message"] or {}).get("content") or ""
        except Exception as e:
            self.log(f"⚠️  compact summarize failed: "
                     f"{type(e).__name__}: {e}")
            return None
        c = c.strip()
        if not c:
            return None
        self._fails = 0
        self.log(f"📦 compact ref={ref} {self._label(group)}: "
                 f"{self._est(group)}→{len(c) // 4} tok "
                 f"in {time.monotonic() - t0:.1f}s")
        return c

    def _store(self, ref, group):
        p = os.path.join(self.dir, ref + ".json")
        if os.path.exists(p):
            return
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"ref": ref, "created": time.time(),
                       "messages": group}, f, ensure_ascii=False)
        os.replace(tmp, p)

    # ------------------------------------------------------------- planning

    def plan(self, messages):
        """Oldest raw tool groups first, until estimate drops below target.
        Seed with max(estimate, real usage) — the estimator undercounts."""
        groups = self._groups(messages)
        tail_n = min(self.cfg["tail_groups"], len(groups))
        mid = groups[:-tail_n] if tail_n else groups
        sel, est = [], max(self._est(messages), self.last_prompt)
        for g in mid:
            if est < self.cfg["target"]:
                break
            if not (g and g[0].get("role") == "assistant"
                    and g[0].get("tool_calls")):
                continue
            if self._ref_of(g) in self._applied:
                continue
            sel.append(g)
            est = est - self._est(g) + 600  # summary cost approx
        return sel

    def _do_compact(self, live, snapshot):
        sel = self.plan(snapshot)
        if not sel:
            self.log(f"📦 compact: nothing to compact "
                     f"(est={self._est(snapshot)} < target={self.cfg['target']}, "
                     f"groups={len(self._groups(snapshot))})")
            return
        blocks = []
        fails = 0
        for g in sel:
            ref = self._ref_of(g)
            if ref in self._applied:
                continue
            text = self._summarize(g, ref)
            if text is None:
                fails += 1
                if fails >= self.cfg["fail_break"]:
                    self._disabled = True
                    self.status("⚠️  compact disabled after "
                                f"{fails} consecutive failures")
                    return
                continue
            self._store(ref, g)
            blocks.append((ref, g, text))
        if not blocks:
            return
        if self._cancel:
            return
        # Apply: head + summary msg + untouched snapshot + post-snapshot tail
        removed = {id(m) for _, g, _ in blocks for m in g}
        body = "\n\n".join(
            f"── ref={r} ({self._label(g)}) ──\n{t}" for r, g, t in blocks)
        summary = {"role": "user", "content":
                   "[CONTEXT COMPACTED] Older conversation group(s) were "
                   "summarized to save context. Use the get_details tool with "
                   "a ref to restore any of them in full when you need exact "
                   "details.\n\n" + body}
        new = (list(snapshot[:2]) + [summary]
               + [m for m in snapshot[2:] if id(m) not in removed]
               + list(live[len(snapshot):]))
        live[:] = new
        self._applied.update(r for r, _, _ in blocks)
        self.n_compacts += len(blocks)
        self.status(f"📦 compact: {len(blocks)} group(s) summarized, "
                    f"context {self._est(snapshot)}→~{self._est(new)} tok")
        self.log(f"📦 compact applied: {len(blocks)} group(s), refs="
                 f"{', '.join(r for r, _, _ in blocks)}")

    # ------------------------------------------------------------- triggers

    def after_turn(self, messages, usage):
        """Call after each LLM call. Schedules bg (tool window ahead) or sync."""
        if self._disabled:
            return
        pt = (usage or {}).get("prompt_tokens")
        self.last_prompt = pt or self._est(messages)
        with self._lock:
            if self._busy:
                return
            if self.last_prompt > self.cfg["hard"]:
                self.status("📦 context over hard limit → synchronous compact")
                self._run(messages, list(messages))
            elif self.last_prompt > self.cfg["target"]:
                self._busy = True
                self._cancel = False
                self._bg = threading.Thread(
                    target=self._bg_job,
                    args=(list(messages), messages), daemon=True)
                self._bg.start()
                self.log(f"📦 compact scheduled in background "
                         f"(prompt={self.last_prompt} > target="
                         f"{self.cfg['target']})")

    def _bg_job(self, snapshot, live):
        try:
            self._run(live, snapshot)
        except Exception as e:
            self.log(f"⚠️  compact bg error: {type(e).__name__}: {e}")
        finally:
            with self._lock:
                self._busy = False
                self._bg = None

    def _run(self, live, snapshot):
        try:
            self._do_compact(live, snapshot)
        finally:
            self._cancel = False

    def before_call(self, messages):
        """Join pending background compact before the next LLM call."""
        bg = self._bg
        if bg is None:
            return
        bg.join(timeout=180)
        if bg.is_alive():
            self._cancel = True  # let the job finish; it must NOT apply
            self.log("⚠️  compact still running — skipping apply this turn")
            with self._lock:
                self._busy = False
                self._bg = None

    # ------------------------------------------------------------ retrieval

    def get_details(self, args):
        ref = str(args.get("ref") or "").strip()
        p = os.path.join(self.dir, ref + ".json")
        if not os.path.isfile(p):
            return f"Error: no such ref '{ref}'. " \
                   f"Available: {self._available() or '(none)'}"
        try:
            with open(p, encoding="utf-8") as f:
                msgs = json.load(f)["messages"]
        except Exception as e:
            return f"Error: cannot read ref '{ref}': {e}"
        est = self._est(msgs)
        cap = int(self.cfg["ctx_limit"] * (1 - self.cfg["reserve"]))
        if self.last_prompt + est > cap:
            return (f"Refused: restoring '{ref}' (~{est} tok) would exceed the "
                    f"context budget ({self.last_prompt} + {est} > {cap}). "
                    f"Available refs: {self._available()}")
        ttl = self.cfg["retrieve_ttl"]
        return (f'<retrieved_context ref="{ref}">\n'
                "NOTE: historical content restored from compaction — it happened "
                "EARLIER in the session, it is NOT a recent action. Do not "
                "re-execute its tool calls.\n"
                f"It will be evicted from history in ~{ttl} turns — extract "
                "what you need now.\n"
                f"{self._render(msgs, per_msg_limit=0)}\n"
                "</retrieved_context>")

    def _available(self):
        out = []
        try:
            for fn in sorted(os.listdir(self.dir)):
                if not fn.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(self.dir, fn), encoding="utf-8") as f:
                        d = json.load(f)
                    msgs = d["messages"]
                    out.append(f"{fn[:-5]} ({self._est(msgs)} tok, "
                               f"{self._label(msgs)})")
                except Exception:
                    out.append(f"{fn[:-5]} (?)")
        except OSError:
            pass
        return ", ".join(out[:20]) or "(none)"

    def track_retrieved(self, msg, ref, turn):
        self._retrieved.append([msg, str(ref), turn])

    def tick(self, turn, messages):
        """TTL-evict restored content (ref stays valid for re-retrieval)."""
        if self.cfg["retrieve_ttl"] <= 0 or not self._retrieved:
            return
        alive = []
        for msg, ref, t0 in self._retrieved:
            expired = turn - t0 > self.cfg["retrieve_ttl"]
            live = isinstance(msg.get("content"), str) \
                and msg["content"].startswith("<retrieved_context")
            if expired and live:
                msg["content"] = (f"[retrieved details evicted (ref={ref}). "
                                  f'Call get_details("{ref}") again if still '
                                  f"needed.]")
                self.log(f"📦 retrieved ref={ref} evicted (ttl="
                         f"{self.cfg['retrieve_ttl']})")
            if live and not expired:
                alive.append([msg, ref, t0])
        self._retrieved = alive

    # -------------------------------------------------------------- cleanup

    def cleanup(self):
        bg = self._bg
        if bg is not None:
            self._cancel = True
            bg.join(timeout=10)
        n = 0
        try:
            for fn in os.listdir(self.dir):
                try:
                    os.unlink(os.path.join(self.dir, fn))
                    n += 1
                except OSError:
                    pass
            os.rmdir(self.dir)
        except OSError:
            pass
        self.log(f"📦 compact done: {self.n_compacts} group(s) summarized "
                 f"over session, {n} detail file(s) cleaned "
                 f"(canonical transcript is in the aigent log)")
