"""Unit tests for aigent_compact (no network: _summarize is mocked).

Run: cd scripts && python3 -m unittest tests.test_aigent_compact -v
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import aigent_compact as ac  # noqa: E402


def mk_cm(**over):
    d = tempfile.mkdtemp(prefix="aigent_c_")
    cfg = {"aigent_dir": d, "llm_base_url": "http://x", "llm_api_key": "k",
           "llm_model": "m", "status": lambda s: None, "log": lambda s="": None,
           **over}
    return ac.make(cfg), d


def mk_msgs(n_groups, tool_len=8000):
    msgs = [{"role": "system", "content": "sys" * 100},
            {"role": "user", "content": "task"}]
    for i in range(n_groups):
        msgs.append({"role": "assistant", "content": None,
                     "tool_calls": [{"id": str(i), "type": "function",
                                     "function": {"name": "bash",
                                                  "arguments": "{}"}}]})
        msgs.append({"role": "tool", "tool_call_id": str(i),
                     "content": "x" * tool_len})
    return msgs


class TestGroups(unittest.TestCase):
    def test_head_tool_tail(self):
        cm, _ = mk_cm()
        msgs = mk_msgs(3)
        g = cm._groups(msgs)
        self.assertEqual(len(g), 3)
        for grp in g:
            self.assertEqual(grp[0]["role"], "assistant")
            self.assertEqual(len(grp), 2)

    def test_standalone_and_orphan_tool(self):
        cm, _ = mk_cm()
        msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "t"},
                {"role": "assistant", "content": None,
                 "tool_calls": [{"id": "1", "type": "function",
                                 "function": {"name": "bash", "arguments": "{}"}}]},
                {"role": "tool", "tool_call_id": "1", "content": "out"},
                {"role": "user", "content": "nudge"},
                {"role": "tool", "tool_call_id": "??", "content": "orphan"}]
        g = cm._groups(msgs)
        self.assertEqual([len(x) for x in g], [2, 1, 1])

    def test_ref_stable(self):
        cm, _ = mk_cm()
        g = cm._groups(mk_msgs(1))
        self.assertEqual(cm._ref_of(g[0]), cm._ref_of(g[0]))


class TestEst(unittest.TestCase):
    def test_scales_and_image(self):
        cm, _ = mk_cm()
        small = [{"role": "user", "content": "hi"}]
        big = [{"role": "user", "content": "y" * 8000}]
        self.assertLess(cm._est(small), cm._est(big))
        img = [{"role": "tool",
                "content": [{"type": "image_url",
                             "image_url": {"url": "data:image/png;base64," + "A" * 60000}}]}]
        self.assertGreater(cm._est(img), 10000)


class TestPlan(unittest.TestCase):
    def test_selects_oldest_until_target(self):
        cm, _ = mk_cm(target=9000, tail_groups=1)
        msgs = mk_msgs(6)
        cm.last_prompt = 0
        sel = cm.plan(msgs)
        self.assertTrue(sel)
        self.assertEqual(sel[0], cm._groups(msgs)[0])

    def test_seed_uses_real_prompt(self):
        cm, _ = mk_cm(target=10000, tail_groups=2)
        msgs = mk_msgs(4, tool_len=1000)  # est < target, но реальное prompt выше
        cm.last_prompt = 12000
        self.assertTrue(cm.plan(msgs))
        cm.last_prompt = 5000
        self.assertFalse(cm.plan(msgs))

    def test_never_touches_tail(self):
        cm, _ = mk_cm(target=1, tail_groups=2)
        msgs = mk_msgs(4)
        cm.last_prompt = 10**9
        sel = cm.plan(msgs)
        tail = cm._groups(msgs)[-2:]
        self.assertTrue(all(s not in tail for s in sel))


class TestDoCompact(unittest.TestCase):
    def test_apply_head_summary_tail(self):
        cm, _ = mk_cm(target=1, tail_groups=1)
        msgs = mk_msgs(3)
        cm._summarize = lambda g, ref: "STATE: fake"
        cm._do_compact(msgs, list(msgs))
        self.assertEqual(msgs[0]["role"], "system")
        self.assertEqual(msgs[1]["role"], "user")
        self.assertIn("[CONTEXT COMPACTED]", msgs[2]["content"])
        self.assertIn("get_details", msgs[2]["content"])
        self.assertEqual(msgs[3]["role"], "assistant")  # tail group
        self.assertEqual(len(cm._applied), 2)
        self.assertEqual(cm.n_compacts, 2)

    def test_dedup_no_double_summarize(self):
        cm, _ = mk_cm(target=1, tail_groups=1)
        msgs = mk_msgs(3)
        cm._summarize = lambda g, ref: "STATE: fake"
        cm._do_compact(msgs, list(msgs))
        calls = []
        cm._summarize = lambda g, ref: (calls.append(ref), "STATE: fake")[1]
        cm._do_compact(msgs, list(msgs))
        self.assertEqual(calls, [])  # уже в _applied → не суммаризируем

    def test_store_and_idempotent(self):
        cm, d = mk_cm()
        g = cm._groups(mk_msgs(1))[0]
        ref = cm._ref_of(g)
        cm._store(ref, g)
        cm._store(ref, g)  # не затирает
        self.assertTrue(os.path.isfile(os.path.join(d, "details", ref + ".json")))

    def test_cancel_skips_apply(self):
        cm, _ = mk_cm(target=1, tail_groups=1)
        msgs = mk_msgs(3)
        cm._summarize = lambda g, ref: "STATE: fake"
        cm._cancel = True
        before = len(msgs)
        cm._do_compact(msgs, list(msgs))
        self.assertEqual(len(msgs), before)


class TestGetDetails(unittest.TestCase):
    def setUp(self):
        self.cm, self.d = mk_cm(ctx_limit=100_000, reserve=0.15)
        self.msgs = mk_msgs(2, tool_len=1000)
        self.g = self.cm._groups(self.msgs)[0]
        self.ref = self.cm._ref_of(self.g)
        self.cm._store(self.ref, self.g)

    def test_returns_wrapped_original(self):
        r = self.cm.get_details({"ref": self.ref})
        self.assertTrue(r.startswith('<retrieved_context ref="'))
        self.assertIn("Do not re-execute", r)
        self.assertIn("x" * 1000, r)

    def test_unknown_ref_lists_available(self):
        r = self.cm.get_details({"ref": "nope"})
        self.assertIn("no such ref", r)
        self.assertIn(self.ref, r)

    def test_budget_reject(self):
        self.cm.cfg["ctx_limit"] = 1000
        self.cm.last_prompt = 800
        r = self.cm.get_details({"ref": self.ref})
        self.assertIn("Refused", r)
        self.assertIn(self.ref, r)  # список доступных

    def test_empty_ref(self):
        self.assertIn("no such ref", self.cm.get_details({}))


class TestTTL(unittest.TestCase):
    def test_evict_and_retrieve(self):
        cm, d = mk_cm(retrieve_ttl=3)
        msg = {"role": "tool", "content": "x" * 500}
        cm._store("abc123", [{"role": "tool", "content": "x" * 500}])
        msg["content"] = '<retrieved_context ref="abc123">\nx</retrieved_context>'
        cm.track_retrieved(msg, "abc123", 1)
        cm.tick(3, [msg])
        self.assertTrue(msg["content"].startswith("<retrieved_context"))
        cm.tick(5, [msg])
        self.assertIn("evicted", msg["content"])
        self.assertIn("abc123", msg["content"])  # ref жив для повторного вызова
        self.assertEqual(cm._retrieved, [])
        shutil.rmtree(d, ignore_errors=True)


class Triggers(unittest.TestCase):
    def test_bg_scheduled_above_target(self):
        cm, _ = mk_cm(target=100, hard=1000)
        msgs = mk_msgs(3, tool_len=1000)
        cm.after_turn(msgs, {"prompt_tokens": 150})
        self.assertIsNotNone(cm._bg)
        cm._cancel = True
        cm._bg.join(timeout=5)

    def test_sync_above_hard(self):
        cm, _ = mk_cm(target=100, hard=150, tail_groups=1)
        msgs = mk_msgs(3, tool_len=1000)
        cm._summarize = lambda g, ref: "STATE: fake"
        cm.after_turn(msgs, {"prompt_tokens": 200})
        cm.before_call(msgs)
        self.assertTrue(cm._applied)

    def test_noop_below_target(self):
        cm, _ = mk_cm(target=10**9, hard=10**12)
        msgs = mk_msgs(2)
        cm.after_turn(msgs, {"prompt_tokens": 100})
        self.assertIsNone(cm._bg)

    def test_disabled_after_failures(self):
        cm, _ = mk_cm(target=100, hard=150, fail_break=2, tail_groups=1)
        msgs = mk_msgs(3, tool_len=1000)
        cm._summarize = lambda g, ref: None  # все фейлят
        cm.after_turn(msgs, {"prompt_tokens": 200})
        self.assertTrue(cm._disabled)
        cm.after_turn(msgs, {"prompt_tokens": 999})
        self.assertFalse(cm._busy)


class TestEdges(unittest.TestCase):
    def test_env_override(self):
        old = os.environ.get("AIGENT_COMPACT_TARGET")
        os.environ["AIGENT_COMPACT_TARGET"] = "1234"
        try:
            d = tempfile.mkdtemp(prefix="aigent_c_")
            cm = ac.make({"aigent_dir": d, "llm_base_url": "http://x",
                          "llm_api_key": "k", "llm_model": "m"})
            self.assertEqual(cm.cfg["target"], 1234)
            shutil.rmtree(d, ignore_errors=True)
        finally:
            if old is None:
                os.environ.pop("AIGENT_COMPACT_TARGET", None)
            else:
                os.environ["AIGENT_COMPACT_TARGET"] = old

    def test_cfg_beats_env(self):
        old = os.environ.get("AIGENT_COMPACT_TARGET")
        os.environ["AIGENT_COMPACT_TARGET"] = "1234"
        try:
            d = tempfile.mkdtemp(prefix="aigent_c_")
            cm = ac.make({"aigent_dir": d, "llm_base_url": "http://x",
                          "llm_api_key": "k", "llm_model": "m",
                          "target": 99})
            self.assertEqual(cm.cfg["target"], 99)
            shutil.rmtree(d, ignore_errors=True)
        finally:
            if old is None:
                os.environ.pop("AIGENT_COMPACT_TARGET", None)
            else:
                os.environ["AIGENT_COMPACT_TARGET"] = old

    def test_corrupt_ref_file(self):
        cm, d = mk_cm()
        with open(os.path.join(d, "details", "badref.json"), "w") as f:
            f.write("{not json")
        r = cm.get_details({"ref": "badref"})
        self.assertIn("cannot read ref", r)

    def test_after_turn_no_usage(self):
        cm, _ = mk_cm(target=10**9)
        msgs = mk_msgs(2, tool_len=100)
        cm.after_turn(msgs, None)  # не падает, est fallback
        self.assertEqual(cm.last_prompt, cm._est(msgs))
        self.assertIsNone(cm._bg)

    def test_apply_preserves_solo_and_content_msgs(self):
        cm, _ = mk_cm(target=1, tail_groups=1)
        msgs = mk_msgs(2, tool_len=100)
        # continuation/nudge — solo-сообщения в middle
        msgs.insert(2, {"role": "assistant", "content": "продолжаю"})
        msgs.insert(3, {"role": "user", "content": "nudge"})
        cm._summarize = lambda g, ref: "STATE: fake"
        cm._do_compact(msgs, list(msgs))
        contents = [m.get("content") for m in msgs]
        self.assertIn("продолжаю", contents)
        self.assertIn("nudge", contents)

    def test_fragment_image_and_content_assistant(self):
        cm, _ = mk_cm()
        g = [{"role": "assistant", "content": "взглянем",
              "tool_calls": [{"id": "1", "type": "function",
                              "function": {"name": "view_image",
                                           "arguments": "{}"}}]},
             {"role": "tool", "tool_call_id": "1",
              "content": [{"type": "image_url",
                           "image_url": {"url": "data:image/png;base64,AAAA"}}]}]
        frag = cm._fragment(g)
        self.assertIn("взглянем", frag)
        self.assertIn("image result, content omitted", frag)
        self.assertNotIn("AAAA", frag)

    def test_cleanup_missing_dir(self):
        cm, d = mk_cm()
        shutil.rmtree(d)
        cm.cleanup()  # не падает

    def test_plan_all_applied(self):
        cm, _ = mk_cm(target=1, tail_groups=1)
        msgs = mk_msgs(2)
        for g in cm._groups(msgs):
            cm._applied.add(cm._ref_of(g))
        self.assertEqual(cm.plan(msgs), [])

    def test_available_corrupt_listing(self):
        cm, d = mk_cm()
        with open(os.path.join(d, "details", "x1.json"), "w") as f:
            f.write("{bad")
        import json as _json
        with open(os.path.join(d, "details", "y2.json"), "w") as f:
            f.write(_json.dumps({"messages": [{"role": "tool",
                                               "content": "z" * 4000}]}))
        a = cm._available()
        self.assertIn("x1 (?)", a)
        self.assertIn("y2 (1008 tok", a)


class TestRenderGroup(unittest.TestCase):
    def test_render_no_limit_for_retrieval(self):
        cm, _ = mk_cm()
        g = [{"role": "tool", "tool_call_id": "1", "content": "q" * 50000}]
        self.assertEqual(len(cm._render(g, per_msg_limit=0)), 50000 + 6)
        self.assertLess(len(cm._render(g, per_msg_limit=6000)), 6100)


if __name__ == "__main__":
    unittest.main()
