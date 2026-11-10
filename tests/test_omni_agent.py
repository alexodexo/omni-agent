"""Tests for the Omni-Agent core. Standard library only: python3 -m unittest discover -s tests -v

No test talks to a real provider. The end-to-end tests use a fake `claude`.
"""
import atexit
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from omni_agent import extras  # noqa: E402
from omni_agent.providers import Provider, get_provider, load_providers  # noqa: E402
from omni_agent.config import ConfigError, read_key_file  # noqa: E402
from omni_agent.runner import RUNNER, resolve_tools, fits, choose_runner, effective_protocol  # noqa: E402
from omni_agent.runner.base import RunContext  # noqa: E402

# Hermetic: tests that do not set their own home must never read the real ~/.omni-agent.
_TESTHOME = tempfile.mkdtemp(prefix="omni-agent-test-home-")
os.environ["OMNI_AGENT_HOME"] = _TESTHOME
atexit.register(shutil.rmtree, _TESTHOME, ignore_errors=True)

BIN = ROOT / "bin" / "omni-agent"
FAKE_KEY = "sk-test-12345678-only-for-tests"


class WithHome(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "oa"
        self._old_home = os.environ.get("OMNI_AGENT_HOME")
        os.environ["OMNI_AGENT_HOME"] = str(self.home)
        self.addCleanup(self._restore)

    def _restore(self):
        if self._old_home is None:
            os.environ.pop("OMNI_AGENT_HOME", None)
        else:
            os.environ["OMNI_AGENT_HOME"] = self._old_home


class Providers(unittest.TestCase):
    def test_all_entries_valid(self):
        show_all = load_providers()
        for expected in ("deepseek", "openrouter", "kimi", "ollama", "eurouter", "nvidia", "claude-account"):
            self.assertIn(expected, show_all)

    def test_model_required(self):
        with self.assertRaises(ConfigError):
            get_provider("openrouter").pick_model(None)
        self.assertEqual(get_provider("openrouter").pick_model("x/y"), "x/y")

    def test_short_name(self):
        self.assertEqual(get_provider("deepseek").pick_model("strong"), "deepseek-v4-pro")

    def test_unknown_protocol_is_rejected(self):
        from omni_agent.providers import _from_dict
        with self.assertRaises(ConfigError):
            _from_dict({"id": "x", "protocols": ["soap"], "key_envs": [], "models": {"default": "m"}}, "test")

    def test_own_providers_override(self):
        with tempfile.TemporaryDirectory() as t:
            os.environ["OMNI_AGENT_HOME"] = t
            try:
                (Path(t) / "providers.d").mkdir()
                (Path(t) / "providers.d" / "meiner.json").write_text(json.dumps([
                    {"id": "meiner", "protocols": ["anthropic"], "base_url": "http://x", "key_envs": ["K"], "models": {"default": "m"}}
                ]))
                self.assertIn("meiner", load_providers())
            finally:
                os.environ["OMNI_AGENT_HOME"] = _TESTHOME


class Fit(unittest.TestCase):
    def test_matrix(self):
        d, n, e, k = (get_provider(x) for x in ("deepseek", "nvidia", "eurouter", "claude-account"))
        self.assertTrue(fits(d, RUNNER["claude"]))
        self.assertFalse(fits(n, RUNNER["claude"]))
        self.assertTrue(fits(n, RUNNER["claude"], via_litellm=True))
        self.assertTrue(fits(n, RUNNER["opencode"]))
        self.assertFalse(fits(n, RUNNER["codex"]))
        self.assertTrue(fits(e, RUNNER["codex"]))
        self.assertFalse(fits(e, RUNNER["claude"]))
        self.assertTrue(fits(k, RUNNER["claude"]))
        self.assertFalse(fits(k, RUNNER["opencode"]))

    def test_dsh_only_deepseek_and_never_automatic(self):
        self.assertTrue(fits(get_provider("deepseek"), RUNNER["dsh"]))
        self.assertFalse(fits(get_provider("kimi"), RUNNER["dsh"]))

    def test_effective_protocol_via_litellm(self):
        self.assertEqual(effective_protocol(get_provider("nvidia"), RUNNER["claude"], True), "anthropic")
        self.assertIsNone(effective_protocol(get_provider("eurouter"), RUNNER["claude"], False))

    def test_mismatched_request_names_a_way_out(self):
        if not RUNNER["claude"].file_path():
            self.skipTest("claude not installed")
        with self.assertRaises(ConfigError) as ctx:
            choose_runner(get_provider("nvidia"), "claude")
        self.assertIn("--via-litellm", str(ctx.exception))


class Tools(unittest.TestCase):
    def test_default_without_shell(self):
        w = resolve_tools(None, RUNNER["claude"])
        self.assertNotIn("shell", w)
        self.assertEqual(set(w), {"read", "write", "web_search", "web_fetch"})

    def test_plus_minus(self):
        w = resolve_tools("+shell -web_search", RUNNER["claude"])
        self.assertIn("shell", w)
        self.assertNotIn("web_search", w)

    def test_replace(self):
        self.assertEqual(set(resolve_tools("read,write", RUNNER["claude"])), {"read", "write"})

    def test_unknown_tool(self):
        with self.assertRaises(ConfigError):
            resolve_tools("zaubern", RUNNER["claude"])

    def test_runner_without_sandbox_requires_shell_explicitly(self):
        with self.assertRaises(ConfigError) as ctx:
            resolve_tools(None, RUNNER["dsh"])
        self.assertIn("+shell", str(ctx.exception))
        self.assertIn("shell", resolve_tools("+shell", RUNNER["dsh"]))

    def test_codex_shell_runs_in_sandbox_and_is_visible(self):
        w = resolve_tools(None, RUNNER["codex"])
        self.assertIn("shell", w)  # always present, but only inside the sandbox (writes in the folder, no network)
        self.assertNotIn("web_search", w)  # the default shrinks silently because it was not requested

    def test_requested_impossible_is_refused(self):
        with self.assertRaises(ConfigError):
            resolve_tools("+web_search,+shell", RUNNER["codex"])


class KeyFile(WithHome):
    def test_permissions_too_open(self):
        self.home.mkdir()
        data_file = self.home / "env"
        data_file.write_text("A=bbbbbbbb\n")
        os.chmod(data_file, 0o644)
        with self.assertRaises(ConfigError):
            read_key_file()

    def test_parse(self):
        self.home.mkdir()
        data_file = self.home / "env"
        data_file.write_text("# comment\nexport A=one\nB='two'\nC=\"three\"\nEMPTY=\nno equals sign\n")
        os.chmod(data_file, 0o600)
        self.assertEqual(read_key_file(), {"A": "one", "B": "two", "C": "three"})

    def test_missing_is_empty(self):
        self.assertEqual(read_key_file(), {})


class ClaudeCommand(unittest.TestCase):
    def _ctx(self, provider_id="deepseek", model=None, base_url="auto", key_values=None, tool_list=("read", "write", "web_search", "web_fetch")):
        a = get_provider(provider_id)
        return RunContext(
            prompt="task", folder=Path("/tmp/x"), provider=a, model=model or a.models["default"],
            base_url=a.base_url if base_url == "auto" else base_url, protocol="anthropic",
            key_values=key_values if key_values is not None else {"DEEPSEEK_API_KEY": FAKE_KEY},
            tool_list=tuple(tool_list), max_turns=12,
        )

    def test_environment_is_minimal_and_complete(self):
        os.environ["ANTHROPIC_API_KEY"] = "must-not-leak"
        os.environ["ANTHROPIC_BASE_URL"] = "http://wrong"
        try:
            b = RUNNER["claude"].build(self._ctx())
        finally:
            os.environ.pop("ANTHROPIC_API_KEY")
            os.environ.pop("ANTHROPIC_BASE_URL")
        env = b.env
        self.assertEqual(env["ANTHROPIC_BASE_URL"], "https://api.deepseek.com/anthropic")
        self.assertEqual(env["ANTHROPIC_AUTH_TOKEN"], FAKE_KEY)
        for name in ("ANTHROPIC_MODEL", "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL",
                     "ANTHROPIC_DEFAULT_HAIKU_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL"):
            self.assertEqual(env[name], "deepseek-flash", name)
        self.assertNotIn("must-not-leak", json.dumps(env))
        self.assertNotIn("ANTHROPIC_API_KEY", env)

    def test_flags(self):
        argv = RUNNER["claude"].build(self._ctx()).argv
        for flag in ("--strict-mcp-config", "--allowed-tools"):
            self.assertIn(flag, argv)
        self.assertEqual(argv[argv.index("--setting-sources") + 1], "project")
        self.assertEqual(argv[argv.index("--permission-mode") + 1], "dontAsk")
        self.assertNotIn("Bash", argv)
        self.assertNotIn("--no-session-persistence", argv)  # the session stays so that --resume works

    def test_shell_only_when_requested(self):
        argv = RUNNER["claude"].build(self._ctx(tool_list=("read", "shell"))).argv
        self.assertIn("Bash", argv)

    def test_openrouter_gives_empty_anthropic_key(self):
        env = RUNNER["claude"].build(self._ctx("openrouter", model="x/y", key_values={"OPENROUTER_API_KEY": FAKE_KEY})).env
        self.assertEqual(env["ANTHROPIC_API_KEY"], "")

    def test_kimi_haiku_tier_only_with_default_model(self):
        a = get_provider("kimi")
        env = RUNNER["claude"].build(self._ctx("kimi", key_values={"MOONSHOT_API_KEY": FAKE_KEY})).env
        self.assertEqual(env["ANTHROPIC_DEFAULT_HAIKU_MODEL"], a.models["small"])
        env2 = RUNNER["claude"].build(self._ctx("kimi", model="eigenes", key_values={"MOONSHOT_API_KEY": FAKE_KEY})).env
        self.assertEqual(env2["ANTHROPIC_DEFAULT_HAIKU_MODEL"], "eigenes")

    def test_ollama_placeholder_instead_of_key(self):
        env = RUNNER["claude"].build(self._ctx("ollama", key_values={})).env
        self.assertEqual(env["ANTHROPIC_AUTH_TOKEN"], "ollama")

    def test_claude_account_sets_no_base_url(self):
        env = RUNNER["claude"].build(self._ctx("claude-account", model="sonnet", base_url=None, key_values={"ANTHROPIC_API_KEY": FAKE_KEY})).env
        self.assertNotIn("ANTHROPIC_BASE_URL", env)
        self.assertEqual(env["ANTHROPIC_API_KEY"], FAKE_KEY)

    def test_progress_counts_turns(self):
        state = {"turns": 0}
        line = json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "WebSearch", "input": {"query": "x"}}]}})
        out = RUNNER["claude"].progress(line, state)
        self.assertEqual(state["turns"], 1)
        self.assertIn("WebSearch", out[0])
        self.assertEqual(RUNNER["claude"].progress("not json", state), [])


class Accounts(WithHome):
    def _cli(self, *argv, entry_text=None):
        env = {"PATH": os.environ["PATH"], "HOME": self.tmp.name, "OMNI_AGENT_HOME": str(self.home)}
        return subprocess.run([sys.executable, str(BIN), *argv], capture_output=True, text=True, env=env, input=entry_text)

    def _write_env(self, text):
        self.home.mkdir(parents=True, exist_ok=True)
        os.chmod(self.home, 0o700)
        d = self.home / "env"
        d.write_text(text, encoding="utf-8")
        os.chmod(d, 0o600)
        return d

    def test_any_number_of_accounts_side_by_side(self):
        from omni_agent import accounts
        for n, kind in (("felipe", "token"), ("fps", "api"), ("third-firm", "api")):
            accounts.create(n, kind)
        self.assertEqual({k["name"] for k in accounts.list_items()}, {"felipe", "fps", "third-firm"})
        self.assertEqual(get_provider("claude-fps").key_envs, ("OMNI_AGENT_ACCOUNT_FPS",))
        self.assertEqual(get_provider("claude-third-firm").key_envs, ("OMNI_AGENT_ACCOUNT_THIRD_FIRM",))

    def test_invalid_names_rejected(self):
        from omni_agent import accounts
        for n in ("", "Felipe", "../x", "a b", "-x", "x" * 40):
            with self.assertRaises(ConfigError, msg=n):
                accounts.create(n, "api")

    def test_duplicate_name_only_with_replace(self):
        from omni_agent import accounts
        accounts.create("fps", "api")
        with self.assertRaises(ConfigError):
            accounts.create("fps", "api")
        accounts.create("fps", "token", overwrite=True)
        self.assertEqual(get_provider("claude-fps").account_kind, "token")

    def test_account_only_with_claude_runner(self):
        from omni_agent import accounts
        accounts.create("fps", "api")
        a = get_provider("claude-fps")
        self.assertTrue(fits(a, RUNNER["claude"]))
        self.assertFalse(fits(a, RUNNER["opencode"]))

    def test_kind_picks_the_right_claude_key(self):
        from omni_agent import accounts
        accounts.create("tok", "token")
        accounts.create("api", "api")
        for name, expected, other in (("tok", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY"), ("api", "ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")):
            a = get_provider(f"claude-{name}")
            env = RUNNER["claude"].build(ClaudeCommand._ctx(self, f"claude-{name}", model="sonnet", base_url=None, key_values={a.key_envs[0]: FAKE_KEY})).env
            self.assertEqual(env[expected], FAKE_KEY)
            self.assertNotIn(other, env)
            self.assertNotIn("ANTHROPIC_BASE_URL", env)

    def test_add_adopts_existing_line_without_showing_value(self):
        d = self._write_env(f"DEEPSEEK_API_KEY=abc\nCLAUDE_CODE_OAUTH_TOKEN={FAKE_KEY}\n")
        res = self._cli("account", "add", "felipe", "--kind", "token", "--adopt", "CLAUDE_CODE_OAUTH_TOKEN")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn(FAKE_KEY, res.stdout + res.stderr)
        content = d.read_text()
        self.assertIn(f"OMNI_AGENT_ACCOUNT_FELIPE={FAKE_KEY}", content)
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN=", content)
        self.assertIn("DEEPSEEK_API_KEY=abc", content)
        self.assertEqual(stat.S_IMODE(d.stat().st_mode), 0o600)

    def test_add_without_terminal_gives_instructions_and_never_key(self):
        self._write_env("")
        res = self._cli("account", "add", "fps", "--kind", "api")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("Key still missing", res.stdout)
        self.assertIn("OMNI_AGENT_ACCOUNT_FPS", res.stdout)

    def test_adopt_missing_line_fails_cleanly(self):
        self._write_env("DEEPSEEK_API_KEY=abc\n")
        res = self._cli("account", "add", "felipe", "--kind", "token", "--adopt", "DOES_NOT_EXIST")
        self.assertEqual(res.returncode, 2)

    def test_list_and_remove(self):
        d = self._write_env(f"OMNI_AGENT_ACCOUNT_FPS={FAKE_KEY}\n")
        self._cli("account", "add", "fps", "--kind", "api")
        list_items = self._cli("account", "list", "--no-usage")
        self.assertIn("claude-fps", list_items.stdout)
        self.assertIn("Key set", list_items.stdout)
        self.assertNotIn(FAKE_KEY, list_items.stdout)
        self._cli("account", "remove", "fps", "--with-key")
        self.assertNotIn("OMNI_AGENT_ACCOUNT_FPS", d.read_text())
        self.assertIn("No named account", self._cli("account", "list", "--no-usage").stdout)

    def test_usage_subscription_from_headers(self):
        from omni_agent import accounts
        h = {"anthropic-ratelimit-unified-5h-utilization": "0.04", "anthropic-ratelimit-unified-5h-reset": "1793977200",
             "anthropic-ratelimit-unified-7d-utilization": "0.29", "anthropic-ratelimit-unified-7d-reset": "1794499200",
             "anthropic-ratelimit-unified-status": "allowed"}
        text = accounts.usage_text(h, "token")
        self.assertIn("5 h 4%", text)
        self.assertIn("7 days 29%, resets", text)
        self.assertIn("(in ", text)
        self.assertNotIn("STATUS", text)
        h["anthropic-ratelimit-unified-status"] = "rejected"
        self.assertIn("STATUS: rejected", accounts.usage_text(h, "token"))

    def test_usage_missing_window_is_dash(self):
        from omni_agent import accounts
        self.assertIn("5 h -", accounts.usage_text({"anthropic-ratelimit-unified-7d-utilization": "0.1"}, "token"))

    def test_usage_api_key_from_headers(self):
        from omni_agent import accounts
        h = {"anthropic-ratelimit-requests-remaining": "49", "anthropic-ratelimit-requests-limit": "50",
             "anthropic-ratelimit-tokens-remaining": "39000", "anthropic-ratelimit-tokens-limit": "40000"}
        text = accounts.usage_text(h, "api")
        self.assertIn("Requests left 49/50", text)
        self.assertIn("Tokens left 39000/40000", text)

    def test_usage_error_becomes_text_and_does_not_leak_key(self):
        from omni_agent import accounts
        accounts.create("fps", "api")
        self._write_env(f"OMNI_AGENT_ACCOUNT_FPS={FAKE_KEY}\n")
        def broken(env, kind, key_values):
            raise ConfigError("HTTP 401")
        text = accounts.usage(accounts.list_items()[0], fetch=broken)
        self.assertIn("Query failed", text)
        self.assertNotIn(FAKE_KEY, text)

    def test_default_account_set_read_delete(self):
        self._cli("account", "add", "fbs", "--kind", "token")
        self.assertIn("none", self._cli("account", "default").stdout)
        self.assertEqual(self._cli("account", "default", "fbs").returncode, 0)
        self.assertIn("claude-fbs", self._cli("account", "default").stdout)
        self.assertIn("[DEFAULT]", self._cli("account", "list", "--no-usage").stdout)
        self._cli("account", "default", "--delete")
        self.assertIn("none", self._cli("account", "default").stdout)

    def test_default_only_for_existing_account(self):
        self.assertEqual(self._cli("account", "default", "doesnotexist").returncode, 2)

    def test_run_without_provider_and_without_default_fails_clearly(self):
        res = self._cli("run", "--text", "x")
        self.assertEqual(res.returncode, 2)
        self.assertIn("default", res.stderr + res.stdout)

    def test_run_account_and_provider_exclude_each_other(self):
        res = self._cli("run", "--text", "x", "--account", "fbs", "--provider", "deepseek")
        self.assertEqual(res.returncode, 2)

    def test_run_without_provider_takes_default_account(self):
        self._cli("account", "add", "fbs", "--kind", "token")
        self._cli("account", "default", "fbs")
        res = self._cli("run", "--text", "x")  # key missing: fails, but names the default
        self.assertIn("default: claude-fbs", res.stdout)
        self.assertEqual(res.returncode, 2)

    def test_account_visible_in_provider_command(self):
        self._cli("account", "add", "fps", "--kind", "api")
        self.assertIn("claude-fps", self._cli("providers").stdout)


class OpencodeCodex(unittest.TestCase):
    def _ctx(self, provider_id, protocol, tool_list):
        a = get_provider(provider_id)
        return RunContext(prompt="p", folder=Path("/tmp/x"), provider=a, model="m", base_url=a.base_url,
                           protocol=protocol, key_values={a.key_envs[0]: FAKE_KEY}, tool_list=tool_list, max_turns=5)

    def test_opencode_config_without_key_value(self):
        b = RUNNER["opencode"].build(self._ctx("nvidia", "openai-chat", ("read", "write")))
        config = json.loads(b.env["OPENCODE_CONFIG_CONTENT"])
        self.assertNotIn(FAKE_KEY, b.env["OPENCODE_CONFIG_CONTENT"])
        self.assertEqual(config["permission"]["bash"], "deny")
        self.assertEqual(config["permission"]["edit"], "allow")
        self.assertEqual(b.env["NVIDIA_API_KEY"], FAKE_KEY)

    def test_codex_arguments(self):
        b = RUNNER["codex"].build(self._ctx("eurouter", "openai-responses", ("read", "write", "shell")))
        self.assertIn("workspace-write", b.argv)
        self.assertTrue(any("wire_api = \"responses\"" in x for x in b.argv))
        self.assertNotIn(FAKE_KEY, " ".join(b.argv))


class CodexAndResume(unittest.TestCase):
    def _ctx(self, provider_id, **extra):
        a = get_provider(provider_id)
        return RunContext(prompt="p", folder=Path("/tmp/x"), provider=a, model="gpt-x", base_url=a.base_url,
                           protocol="openai-responses", key_values={}, tool_list=("read", "write", "shell"),
                           max_turns=5, extra=extra)

    def test_codex_login_uses_only_login_not_the_user_config(self):
        b = RUNNER["codex"].build(self._ctx("codex", effort="low"))
        self.assertIn("--ignore-user-config", b.argv)
        self.assertIn("--ignore-rules", b.argv)
        self.assertEqual(b.argv[b.argv.index("--model") + 1], "gpt-x")
        self.assertIn('model_reasoning_effort="low"', b.argv)
        self.assertFalse(any("model_provider" in x for x in b.argv))
        self.assertNotIn("OPENAI_API_KEY", b.env)

    def test_provider_codex_runs_only_via_codex(self):
        a = get_provider("codex")
        self.assertTrue(fits(a, RUNNER["codex"]))
        self.assertFalse(fits(a, RUNNER["claude"]))
        self.assertFalse(fits(get_provider("claude-account"), RUNNER["codex"]))

    def test_codex_resume_uses_resume(self):
        b = RUNNER["codex"].build(self._ctx("codex", resume="thread-1"))
        self.assertEqual(b.argv[1:3], ["exec", "resume"])
        self.assertIn("thread-1", b.argv)
        self.assertNotIn("--cd", b.argv)

    def test_codex_remembers_the_session(self):
        z = {}
        RUNNER["codex"].progress(json.dumps({"type": "thread.started", "thread_id": "t-9"}), z)
        self.assertEqual(z["session"], "t-9")

    def test_claude_resume_uses_resume(self):
        a = get_provider("claude-account")
        ctx = RunContext(prompt="p", folder=Path("/tmp/x"), provider=a, model="sonnet", base_url=None, protocol="anthropic",
                          key_values={"ANTHROPIC_API_KEY": FAKE_KEY}, tool_list=("read",), max_turns=5, extra={"resume": "sess-7"})
        argv = RUNNER["claude"].build(ctx).argv
        self.assertEqual(argv[argv.index("--resume") + 1], "sess-7")


class Plugin(unittest.TestCase):
    def test_version_in_plugin_json_equals_core(self):
        from omni_agent import VERSION
        manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
        self.assertEqual(manifest["version"], VERSION)

    def test_skills_have_description(self):
        for folder in sorted((ROOT / "skills").iterdir()):
            head = (folder / "SKILL.md").read_text().split("---")[1]
            self.assertIn("description:", head, folder.name)

    def test_agent_is_callable_by_claude_itself_also_in_goal(self):
        # /goal and the main thread must not call blocked commands. They delegate through the agent type omni-agent:worker,
        # whose description names Omni-Agent and the providers, so the user does not have to type a command.
        description = (ROOT / "agents" / "worker.md").read_text().split("---")[1]
        for word in ("Omni-Agent", "Codex", "fbs, felipe, llc", "proactively", "Never pick a third-party provider"):
            self.assertIn(word, description)


class Extras(unittest.TestCase):
    def test_litellm_config_without_secret(self):
        text = extras.make_config(get_provider("nvidia"), "z-ai/glm-5.3-flash")
        self.assertIn("nvidia_nim/z-ai/glm-5.3-flash", text)
        self.assertIn("os.environ/NVIDIA_NIM_API_KEY", text)
        self.assertNotIn("api_base", text)
        self.assertIn("telemetry: false", text)

    def test_litellm_generic_uses_openai_and_base(self):
        text = extras.make_config(get_provider("eurouter"), "gpt-x")
        self.assertIn('"openai/gpt-x"', text)
        self.assertIn("api.eurouter.ai", text)

    def test_lock_file_pinned_with_hashes(self):
        content = extras.LOCK_FILE.read_text()
        self.assertEqual(extras.pinned_version(), "1.106.3")
        self.assertNotIn("1.107.0", content.split("litellm==")[1][:12])
        self.assertGreater(content.count("--hash=sha256:"), 100)


FAKE_CLAUDE = textwrap.dedent("""\
    #!/usr/bin/env python3
    import json, os, sys, time
    mode = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mode")).read().strip()
    if "--version" in sys.argv:
        print("0.0.0 (Fake)"); sys.exit(0)
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "argv.log"), "a") as f:
        f.write(json.dumps(sys.argv[1:]) + "\\n")
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cwd.log"), "a") as f:
        f.write(os.getcwd() + "\\n")
    print(json.dumps({"type": "system", "subtype": "init", "model": os.environ.get("ANTHROPIC_MODEL"), "session_id": "sess-1"}), flush=True)
    print(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "WebSearch", "input": {"query": "test"}}]}}), flush=True)
    print("Line with secret: " + os.environ.get("ANTHROPIC_AUTH_TOKEN", ""), flush=True)
    sys.stderr.write("stderr with secret: " + os.environ.get("ANTHROPIC_AUTH_TOKEN", "") + "\\n")
    if mode == "hangs":
        time.sleep(60)
    if mode == "ok":
        open("report.md", "w").write("# Report\\nDone\\n" + sys.argv[2][-80:] + "\\n")
    if mode in ("block", "allow"):
        open("report.md", "w").write(("BLOCK: file m.py line 1 is broken" if mode == "block" else "ALLOW: looks good") + "\\nDetails\\n")
    if mode == "short":
        time.sleep(2)
        open("report.md", "w").write("# Report\\nFinished late\\n")
    print(json.dumps({"type": "result", "subtype": "success", "num_turns": 1, "duration_ms": 10, "total_cost_usd": 0,
                      "result": "Final answer of the agent" if mode == "answer" else "ok"}), flush=True)
""")


class FakeAgentCase(WithHome):
    def setUp(self):
        super().setUp()
        self.bin = Path(self.tmp.name) / "bin"
        self.bin.mkdir()
        fake = self.bin / "claude"
        fake.write_text(FAKE_CLAUDE)
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        self.env = {
            "PATH": f"{self.bin}{os.pathsep}/usr/bin:/bin:{Path(sys.executable).parent}",
            "HOME": self.tmp.name, "OMNI_AGENT_HOME": str(self.home),
            "OMNI_AGENT_NO_NETCHECK": "1", "DEEPSEEK_API_KEY": FAKE_KEY,
        }

    def run_cli(self, *args, mode="ok"):
        (self.bin / "mode").write_text(mode)  # environment variables deliberately do not reach the runner
        return subprocess.run([sys.executable, str(BIN), *args], env=dict(self.env), capture_output=True, text=True, timeout=60)

    def last_run(self) -> Path:
        return sorted((self.home / "runs").iterdir())[-1]

    def _repo(self, content="a = 1\n"):
        repo = Path(self.tmp.name) / "repo"
        repo.mkdir()
        git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=repo, check=True, capture_output=True)
        git("init", "-q", ".")
        (repo / "m.py").write_text(content)
        git("add", ".")
        git("commit", "-qm", "init")
        return repo, git

    def _review(self, repo, *args, mode="ok"):
        (self.bin / "mode").write_text(mode)
        return subprocess.run([sys.executable, str(BIN), "review", *args], env=dict(self.env), cwd=repo,
                              capture_output=True, text=True, timeout=60)


class EndToEnd(FakeAgentCase):
    def test_run_with_report(self):
        res = self.run_cli("run", "--text", "Say hello", "--provider", "deepseek", "--runner", "claude")
        self.assertEqual(res.returncode, 0, res.stderr)
        folder = self.last_run()
        status = json.loads((folder / "status.json").read_text())
        self.assertEqual(status["state"], "done")
        self.assertEqual(status["turns"], 1)
        self.assertEqual(status["provider"], "deepseek")
        self.assertTrue((folder / "report.md").exists())
        self.assertIn("Say hello", (folder / "task.md").read_text())
        self.assertIn("Tool 1: WebSearch", res.stdout)

    def test_secrets_are_redacted(self):
        self.run_cli("run", "--text", "x", "--provider", "deepseek")
        folder = self.last_run()
        for data_file in ("log.jsonl", "error.log"):
            content = (folder / data_file).read_text()
            self.assertNotIn(FAKE_KEY, content, data_file)
            self.assertIn("***", content, data_file)

    def test_without_report_is_error(self):
        res = self.run_cli("run", "--text", "x", "--provider", "deepseek", mode="none")
        self.assertEqual(res.returncode, 1)
        self.assertEqual(json.loads((self.last_run() / "status.json").read_text())["state"], "failed")

    def test_time_limit(self):
        res = self.run_cli("run", "--text", "x", "--provider", "deepseek", "--timeout", "3", mode="hangs")
        self.assertEqual(res.returncode, 124)
        status = json.loads((self.last_run() / "status.json").read_text())
        self.assertEqual(status["state"], "failed")
        self.assertIn("Time limit", status["remark"])

    def test_missing_key_exit_2(self):
        self.env.pop("DEEPSEEK_API_KEY")
        res = self.run_cli("run", "--text", "x", "--provider", "deepseek")
        self.assertEqual(res.returncode, 2)
        self.assertIn("DEEPSEEK_API_KEY", res.stderr)
        self.assertNotIn(FAKE_KEY, res.stderr)

    def test_unknown_provider_exit_2(self):
        self.assertEqual(self.run_cli("run", "--text", "x", "--provider", "doesnotexist").returncode, 2)

    def test_unreachable_exit_3(self):
        self.env.pop("OMNI_AGENT_NO_NETCHECK")
        (self.home / "providers.d").mkdir(parents=True)
        (self.home / "providers.d" / "tot.json").write_text(json.dumps([
            {"id": "tot", "protocols": ["anthropic"], "base_url": "http://127.0.0.1:9", "key_envs": [], "key_placeholder": "x", "models": {"default": "m"}}
        ]))
        res = self.run_cli("run", "--text", "x", "--provider", "tot", "--runner", "claude")
        self.assertEqual(res.returncode, 3, res.stderr)

    def test_resume_uses_same_session_and_updates_report(self):
        self.run_cli("run", "--text", "First task", "--provider", "deepseek")
        folder = self.last_run()
        self.assertEqual(json.loads((folder / "status.json").read_text())["session"], "sess-1")
        res = self.run_cli("run", "--resume", "--text", "Follow-up one")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(len(list((self.home / "runs").iterdir())), 1)  # same folder, no new one
        calls = [json.loads(z) for z in (self.bin / "argv.log").read_text().splitlines()]
        self.assertEqual(calls[1][calls[1].index("--resume") + 1], "sess-1")
        self.assertNotIn("--resume", calls[0])
        self.assertIn("Follow-up one", (folder / "task.md").read_text())
        status = json.loads((folder / "status.json").read_text())
        self.assertEqual((status["state"], status["nachfragen"], status["provider"]), ("done", 1, "deepseek"))

    def test_resume_with_old_report_does_not_count_as_done(self):
        self.run_cli("run", "--text", "First task", "--provider", "deepseek")
        folder = self.last_run()
        os.utime(folder / "report.md", (1_000_000, 1_000_000))
        res = self.run_cli("run", "--resume", "--text", "Follow-up", mode="none")
        self.assertEqual(res.returncode, 1)
        self.assertEqual(json.loads((folder / "status.json").read_text())["state"], "failed")

    def test_resume_without_follow_up_or_session_fails_cleanly(self):
        self.run_cli("run", "--text", "x", "--provider", "deepseek")
        self.assertEqual(self.run_cli("run", "--resume").returncode, 2)
        folder = self.last_run()
        status = json.loads((folder / "status.json").read_text())
        status.pop("session")
        (folder / "status.json").write_text(json.dumps(status))
        self.assertEqual(self.run_cli("run", "--resume", "--text", "y").returncode, 2)

    def test_resume_with_another_provider_is_refused(self):
        self.run_cli("run", "--text", "x", "--provider", "deepseek")
        self.assertEqual(self.run_cli("run", "--resume", "--provider", "kimi", "--text", "y").returncode, 2)

    def test_result_shows_report_and_path(self):
        self.run_cli("run", "--text", "Result question", "--provider", "deepseek")
        res = self.run_cli("result")
        self.assertIn("# Report", res.stdout)
        self.assertIn("--resume", res.stdout)
        self.assertTrue(self.run_cli("result", "--path").stdout.strip().endswith("report.md"))

    def test_result_without_runs_fails_clearly(self):
        self.assertEqual(self.run_cli("result").returncode, 2)

    def test_cancel_aborts_running_run(self):
        (self.bin / "mode").write_text("hangs")
        proc = subprocess.Popen([sys.executable, str(BIN), "run", "--text", "x", "--provider", "deepseek", "--timeout", "60"],
                                env=dict(self.env), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            for _ in range(60):
                time.sleep(0.25)
                runs = list((self.home / "runs").iterdir()) if (self.home / "runs").exists() else []
                if runs and (runs[0] / "log.jsonl").exists() and (runs[0] / "log.jsonl").stat().st_size > 0:
                    break  # the runner is running and hanging
            res = subprocess.run([sys.executable, str(BIN), "cancel"], env=dict(self.env), capture_output=True, text=True, timeout=60)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("cancelled", res.stdout)
            proc.wait(timeout=20)
            self.assertEqual(json.loads((self.last_run() / "status.json").read_text())["state"], "cancelled")
        finally:
            if proc.poll() is None:
                proc.kill()

    def test_cancel_without_running_run(self):
        self.assertIn("No run is active", self.run_cli("cancel").stdout)

    def test_cancel_cleans_up_dead_run(self):
        folder = self.home / "runs" / "20260101-000000-tot"
        folder.mkdir(parents=True)
        (folder / "status.json").write_text(json.dumps({"state": "running", "pid": 999999, "run_dir": str(folder)}))
        self.assertIn("already gone", self.run_cli("cancel").stdout)
        self.assertEqual(json.loads((folder / "status.json").read_text())["state"], "failed")

    # ---- review ----
    def test_review_gives_diff_as_material_and_read_only(self):
        repo, _ = self._repo()
        (repo / "m.py").write_text("a = 2\n")
        res = self._review(repo, "--provider", "deepseek", "--adversarial", "check permissions")
        self.assertEqual(res.returncode, 0, res.stderr)
        folder = self.last_run()
        self.assertIn("+a = 2", (folder / "changes.patch").read_text())
        self.assertIn("M\tm.py", (folder / "changed_files.txt").read_text())
        task = (folder / "task.md").read_text()
        self.assertIn("<stance>", task)
        self.assertIn("check permissions", task)
        self.assertIn("read, write", res.stdout)
        self.assertNotIn("shell", res.stdout.split("tools:")[1].splitlines()[0])

    def test_review_preview_sends_nothing(self):
        repo, _ = self._repo()
        (repo / "m.py").write_text("a = 2\n")
        res = self._review(repo, "--provider", "deepseek", "--preview")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("nothing sent", res.stdout)
        self.assertFalse((self.home / "runs").exists())

    def test_review_without_changes(self):
        repo, _ = self._repo()
        res = self._review(repo, "--provider", "deepseek")
        self.assertEqual(res.returncode, 2)
        self.assertIn("No changes", res.stderr)

    def test_review_blocks_diff_with_secret(self):
        repo, git = self._repo()
        (repo / "k.py").write_text('API_KEY = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"\n')
        git("add", "-N", "k.py")
        res = self._review(repo, "--provider", "deepseek")
        self.assertEqual(res.returncode, 2)
        self.assertIn("secrets", res.stderr)
        self.assertNotIn("sk-ant-api03-abcdefghij", res.stdout + res.stderr)
        self.assertFalse((self.home / "runs").exists())
        self.assertEqual(self._review(repo, "--provider", "deepseek", "--force").returncode, 0)

    def test_review_blocks_env_file(self):
        repo, git = self._repo()
        (repo / ".env").write_text("A=1\n")
        git("add", "-N", ".env")
        self.assertEqual(self._review(repo, "--provider", "deepseek").returncode, 2)

    def test_review_base_compares_with_branch(self):
        repo, git = self._repo()
        git("checkout", "-q", "-b", "feature")
        (repo / "m.py").write_text("a = 3\n")
        git("commit", "-qam", "change")
        res = self._review(repo, "--provider", "deepseek", "--base", "master") if self._has_master(repo) else self._review(repo, "--provider", "deepseek", "--base", "main")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("+a = 3", (self.last_run() / "changes.patch").read_text())

    def _has_master(self, repo):
        return b"master" in subprocess.run(["git", "branch"], cwd=repo, capture_output=True).stdout

    def test_review_diff_too_large(self):
        from omni_agent import review
        with self.assertRaises(ConfigError):
            review.verify({"diff": "+x\n" * (review.MAX_CHARS // 2), "names": "M\tm.py", "new": [], "selector": "t"}, False)

    def test_status_command(self):
        self.run_cli("run", "--text", "x", "--provider", "deepseek")
        list_items = self.run_cli("status", "--json")
        doc = json.loads(list_items.stdout)
        self.assertEqual(doc[0]["state"], "done")
        single = self.run_cli("status", doc[0]["run"][:8], "--json")
        self.assertTrue(json.loads(single.stdout)["report"].endswith("report.md"))

    def test_setup_creates_key_file_with_600(self):
        self.run_cli("setup")
        data_file = self.home / "env"
        self.assertTrue(data_file.exists())
        self.assertEqual(stat.S_IMODE(data_file.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.home.stat().st_mode), 0o700)
        self.assertNotIn(FAKE_KEY, data_file.read_text())

    def test_setup_replaces_stale_link_with_forwarder_that_survives_updates(self):
        link_dir = Path(self.tmp.name) / ".local" / "bin"
        link_dir.mkdir(parents=True)
        (link_dir / "omni-agent").symlink_to(Path(self.tmp.name) / "gone" / "omni-agent")  # points to nothing
        self.run_cli("setup")
        link = link_dir / "omni-agent"
        self.assertFalse(link.is_symlink())
        self.assertTrue(os.access(link, os.X_OK))
        self.assertIn("omni-agent-shim", link.read_text())
        # Rebuild the plugin directory: the forwarder follows installed_plugins.json, not a fixed path
        plugins = Path(self.tmp.name) / ".claude" / "plugins"
        plugins.mkdir(parents=True)
        (plugins / "installed_plugins.json").write_text(json.dumps(
            {"plugins": {"omni-agent@omni-agent": [{"installPath": str(ROOT)}]}}))
        env = {"PATH": os.environ["PATH"], "HOME": self.tmp.name, "OMNI_AGENT_HOME": str(self.home)}
        res = subprocess.run([str(link), "--version"], capture_output=True, text=True, env=env)
        self.assertEqual(res.returncode, 0, res.stderr)
        from omni_agent import VERSION
        self.assertIn(VERSION, res.stdout)

    def test_setup_does_not_touch_foreign_command(self):
        link_dir = Path(self.tmp.name) / ".local" / "bin"
        link_dir.mkdir(parents=True)
        foreign = link_dir / "omni-agent"
        foreign.write_text("#!/bin/sh\necho foreign\n")
        os.chmod(foreign, 0o755)
        env = {"PATH": f"{link_dir}:{os.environ['PATH']}", "HOME": self.tmp.name, "OMNI_AGENT_HOME": str(self.home)}
        subprocess.run([sys.executable, str(BIN), "setup"], capture_output=True, text=True, env=env)
        self.assertIn("foreign", foreign.read_text())

    def test_doctor_never_names_the_key(self):
        res = self.run_cli("doctor")
        self.assertNotIn(FAKE_KEY, res.stdout + res.stderr)
        self.assertIn("deepseek", res.stdout)

    def test_working_directory_must_be_empty(self):
        full_dir = Path(self.tmp.name) / "full"
        full_dir.mkdir()
        (full_dir / "data_file").write_text("x")
        res = self.run_cli("run", "--text", "x", "--provider", "deepseek", "--dir", str(full_dir))
        self.assertEqual(res.returncode, 2)


# ---------------------------------------------------------------------------
# Version 1.1: subagent, commands, internal skills, hooks, detached runs, project mode, review gate
# ---------------------------------------------------------------------------

def _frontmatter(file_path: Path) -> dict:
    text = file_path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), file_path
    head = text.split("---\n", 2)[1]
    fields, key_values = {}, None
    for line in head.splitlines():
        if line.startswith("  - ") and key_values:
            fields.setdefault(key_values, []).append(line[4:].strip())
        elif ":" in line and not line.startswith(" "):
            key_values, _, value = line.partition(":")
            fields[key_values.strip()] = value.strip() or []
    return fields


def _bash_lines(file_path: Path) -> list:
    """Command lines `omni-agent ...` from code blocks and ! inserts of a plugin file."""
    import re
    text = file_path.read_text(encoding="utf-8")
    lines = re.findall(r"^!`(.+)`$", text, flags=re.M)
    for block in re.findall(r"```(?:bash)?\n(.*?)```", text, flags=re.S):
        lines += [z for z in block.splitlines() if z.strip()]
    return [z.strip() for z in lines if "omni-agent" in z]


class PluginLayout(unittest.TestCase):
    def test_agent_is_thin_forwarder(self):
        f = _frontmatter(ROOT / "agents" / "worker.md")
        self.assertEqual(f["name"], "worker")
        self.assertEqual(f["tools"], "Bash")
        self.assertIn("proactively", f["description"])
        for skill in f["skills"]:
            self.assertTrue((ROOT / "skills" / skill / "SKILL.md").is_file(), skill)
        text = (ROOT / "agents" / "worker.md").read_text()
        self.assertIn("--wait 540", text)
        self.assertIn("timeout: 600000", text)

    def test_internal_skills_are_not_callable(self):
        skills = sorted(p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md"))
        self.assertEqual(skills, ["omni-agent-results", "omni-agent-runtime", "omni-agent-task"])
        for name in skills:
            self.assertEqual(_frontmatter(ROOT / "skills" / name / "SKILL.md")["user-invocable"], "false", name)

    def test_commands_complete_and_only_setup_may_be_called_by_the_model(self):
        expected = {"run", "review", "adversarial-review", "status", "result", "cancel", "doctor", "accounts", "usage", "hosts", "setup"}
        existing = {p.stem for p in (ROOT / "commands").glob("*.md")}
        self.assertEqual(existing, expected)
        for name in expected:
            f = _frontmatter(ROOT / "commands" / f"{name}.md")
            self.assertTrue(f.get("description"), name)
            if name == "setup":
                self.assertNotIn("disable-model-invocation", f)
            else:
                self.assertEqual(f["disable-model-invocation"], "true", name)

    def test_run_command_calls_agent_not_skill(self):
        text = (ROOT / "commands" / "run.md").read_text()
        self.assertIn('subagent_type: "omni-agent:worker"', text)
        self.assertIn("Agent", _frontmatter(ROOT / "commands" / "run.md")["allowed-tools"])
        self.assertIn("AskUserQuestion", _frontmatter(ROOT / "commands" / "run.md")["allowed-tools"])
        self.assertIn("omni-agent resumable", text)

    def test_adversarial_command_forces_flag(self):
        self.assertIn("--adversarial", (ROOT / "commands" / "adversarial-review.md").read_text())
        self.assertIn("omni-agent review --preview", (ROOT / "commands" / "adversarial-review.md").read_text())

    def test_hooks_call_known_hook_names(self):
        doc = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]
        self.assertEqual(set(doc), {"SessionStart", "SessionEnd", "Stop"})
        commands = {event: doc[event][0]["hooks"][0]["command"] for event in doc}
        self.assertTrue(commands["SessionStart"].endswith("hook start"))
        self.assertTrue(commands["SessionEnd"].endswith("hook end"))
        self.assertTrue(commands["Stop"].endswith("hook stop"))
        for b in commands.values():
            self.assertIn('"${CLAUDE_PLUGIN_ROOT}/bin/omni-agent"', b)

    def test_documented_commands_are_real_commands(self):
        """Every `omni-agent ...` line named in commands, agent and skills must be accepted by the real parser (no invented flag)."""
        import re
        import shlex
        from omni_agent.cli import build_parser
        parser = build_parser()
        file_list = list((ROOT / "commands").glob("*.md")) + [ROOT / "agents" / "worker.md"] + list((ROOT / "skills").glob("*/SKILL.md"))
        verified = 0
        for data_file in file_list:
            for line in _bash_lines(data_file):
                m = re.search(r"omni-agent ((?:run|review|status|result|cancel|wait|resumable|account|doctor|setup|hook)\b[^\n|`]*)", line)
                if not m:
                    continue
                parts = shlex.split(m.group(1).replace("$ARGUMENTS", "").replace("…", "x").replace("[", "").replace("]", ""))
                parts = [t for t in parts if t not in ("|",) and not t.startswith("<")]
                # Placeholders in examples such as NAME, ID, RUN, M are valid values
                try:
                    parser.parse_args(parts)
                except SystemExit:
                    self.fail(f"{data_file.name}: Parser lehnt ab: omni-agent {m.group(1)}")
                verified += 1
        self.assertGreater(verified, 8)

    def test_skills_runtime_examples_parse(self):
        from omni_agent.cli import build_parser
        p = build_parser()
        a = p.parse_args(["run", "--wait", "540", "--account", "fbs", "--project", "--write", "--resume", "--text", "x"])
        self.assertEqual((a.wait_seconds, a.account, a.project, a.writable, a.resume), (540, "fbs", "", True, ""))
        w = p.parse_args(["wait", "20260101-000000", "--max", "540"])
        self.assertEqual((w.run_name, w.max), ("20260101-000000", 540))

    def test_no_old_skills_anymore(self):
        for old in ("run", "review", "status", "doctor", "setup", "delegieren"):
            self.assertFalse((ROOT / "skills" / old).exists(), old)


class DetachedRuns(FakeAgentCase):
    def test_background_reports_immediately_and_run_continues(self):
        (self.bin / "mode").write_text("short")
        t0 = time.time()
        res = subprocess.run([sys.executable, str(BIN), "run", "--background", "--text", "x", "--provider", "deepseek"],
                             env=dict(self.env), capture_output=True, text=True, timeout=30)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertLess(time.time() - t0, 5)
        self.assertIn("Started:", res.stdout)
        folder = self.last_run()
        self.assertEqual(json.loads((folder / "status.json").read_text())["state"], "running")
        for _ in range(60):
            time.sleep(0.5)
            if json.loads((folder / "status.json").read_text())["state"] != "running":
                break
        self.assertEqual(json.loads((folder / "status.json").read_text())["state"], "done")
        self.assertTrue((folder / "console.log").read_text().strip())  # the run console lives in the folder

    def test_wait_delivers_report_with_done_marker(self):
        res = self.run_cli("run", "--wait", "30", "--text", "Say hello", "--provider", "deepseek")
        self.assertEqual(res.returncode, 0, res.stderr)
        lines = res.stdout.splitlines()
        self.assertTrue(lines[0].startswith("Started:"))
        self.assertTrue(any(z.startswith("[done]") for z in lines))
        self.assertIn("# Report", res.stdout)
        self.assertIn("Follow up with the same agent", res.stdout)

    def test_wait_too_short_reports_still_running_and_wait_continues(self):
        (self.bin / "mode").write_text("short")
        res = subprocess.run([sys.executable, str(BIN), "run", "--wait", "0", "--text", "x", "--provider", "deepseek"],
                             env=dict(self.env), capture_output=True, text=True, timeout=30)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("[still running]", res.stdout)
        self.assertIn("omni-agent wait", res.stdout)
        second = subprocess.run([sys.executable, str(BIN), "wait", "--max", "30"], env=dict(self.env), capture_output=True, text=True, timeout=60)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("[done]", second.stdout)
        self.assertIn("Finished late", second.stdout)

    def test_wait_reports_error_with_reason_and_exit_1(self):
        res = self.run_cli("run", "--wait", "30", "--text", "x", "--provider", "deepseek", mode="none")
        self.assertEqual(res.returncode, 1)
        self.assertIn("[failed]", res.stdout)
        self.assertIn("Last lines of error.log", res.stdout)
        self.assertNotIn(FAKE_KEY, res.stdout)

    def test_early_error_is_passed_through(self):
        res = self.run_cli("run", "--background", "--text", "x", "--provider", "doesnotexist")
        self.assertEqual(res.returncode, 2)
        self.assertIn("Unknown provider", res.stderr)

    def test_cancel_a_detached_run(self):
        (self.bin / "mode").write_text("hangs")
        res = subprocess.run([sys.executable, str(BIN), "run", "--background", "--text", "x", "--provider", "deepseek", "--timeout", "60"],
                             env=dict(self.env), capture_output=True, text=True, timeout=30)
        self.assertEqual(res.returncode, 0, res.stderr)
        cancel_res = subprocess.run([sys.executable, str(BIN), "cancel"], env=dict(self.env), capture_output=True, text=True, timeout=60)
        self.assertIn("cancelled", cancel_res.stdout)
        self.assertEqual(json.loads((self.last_run() / "status.json").read_text())["state"], "cancelled")

    def test_without_flags_run_stays_blocking_without_started_line(self):
        res = self.run_cli("run", "--text", "x", "--provider", "deepseek")
        self.assertNotIn("Started:", res.stdout)


class SessionsAndHooks(FakeAgentCase):
    def test_run_remembers_claude_session_and_status_filters(self):
        self.env["OMNI_AGENT_SESSION"] = "session-a"
        self.run_cli("run", "--text", "first", "--provider", "deepseek")
        self.env["OMNI_AGENT_SESSION"] = "session-b"
        self.run_cli("run", "--text", "second", "--provider", "deepseek")
        status = json.loads(self.run_cli("status", "--json").stdout)
        self.assertEqual(len(status), 1)
        self.assertEqual(status[0]["task"], "second")
        show_all = json.loads(self.run_cli("status", "--json", "--all").stdout)
        self.assertEqual(len(show_all), 2)

    def test_status_without_session_shows_all_and_markdown_table(self):
        self.run_cli("run", "--text", "Table sample", "--provider", "deepseek")
        md = self.run_cli("status", "--md").stdout
        self.assertIn("| Run | State |", md)
        self.assertIn("Table sample", md)

    def test_result_and_cancel_default_to_own_session(self):
        self.env["OMNI_AGENT_SESSION"] = "a"
        self.run_cli("run", "--text", "Task A", "--provider", "deepseek")
        self.env["OMNI_AGENT_SESSION"] = "b"
        self.run_cli("run", "--text", "Task B", "--provider", "deepseek")
        self.env["OMNI_AGENT_SESSION"] = "a"
        self.assertIn("Task A", self.run_cli("result").stdout)  # newest run of a, not the newest overall
        self.env["OMNI_AGENT_SESSION"] = "brand-new"
        self.assertIn("Task B", self.run_cli("result").stdout)  # session without runs: falls back to the newest

    def test_resumable(self):
        self.env["OMNI_AGENT_SESSION"] = "a"
        self.assertEqual(json.loads(self.run_cli("resumable").stdout), {"available": False})
        self.run_cli("run", "--text", "First", "--provider", "deepseek")
        res = json.loads(self.run_cli("resumable").stdout)
        self.assertTrue(res["available"])
        self.assertEqual(res["provider"], "deepseek")
        self.env["OMNI_AGENT_SESSION"] = "other"
        self.assertEqual(json.loads(self.run_cli("resumable").stdout), {"available": False})

    def _hook(self, name, entry_text, env_extra=None):
        env = dict(self.env, **(env_extra or {}))
        return subprocess.run([sys.executable, str(BIN), "hook", name], env=env, input=json.dumps(entry_text),
                              capture_output=True, text=True, timeout=60)

    def test_hook_start_writes_session_to_env_file(self):
        data_file = Path(self.tmp.name) / "claude-env"
        res = self._hook("start", {"session_id": "abc-123"}, {"CLAUDE_ENV_FILE": str(data_file)})
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(data_file.read_text(), "export OMNI_AGENT_SESSION='abc-123'\n")

    def test_hook_without_env_file_or_inside_a_run_does_nothing(self):
        self.assertEqual(self._hook("start", {"session_id": "x"}).returncode, 0)
        data_file = Path(self.tmp.name) / "claude-env"
        res = self._hook("start", {"session_id": "x"}, {"CLAUDE_ENV_FILE": str(data_file), "OMNI_AGENT_RUN": "1"})
        self.assertEqual(res.returncode, 0)
        self.assertFalse(data_file.exists())

    def test_hook_end_ends_only_running_ones_of_this_session(self):
        (self.bin / "mode").write_text("hangs")
        env = dict(self.env, OMNI_AGENT_SESSION="s1")
        res = subprocess.run([sys.executable, str(BIN), "run", "--background", "--text", "x", "--provider", "deepseek", "--timeout", "60"],
                             env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(res.returncode, 0, res.stderr)
        folder = self.last_run()
        self._hook("end", {"session_id": "foreign-session"})
        self.assertEqual(json.loads((folder / "status.json").read_text())["state"], "running")
        self._hook("end", {"session_id": "s1", "reason": "clear"})
        self.assertEqual(json.loads((folder / "status.json").read_text())["state"], "running")
        self._hook("end", {"session_id": "s1", "reason": "other"})
        for _ in range(40):
            time.sleep(0.5)
            if json.loads((folder / "status.json").read_text())["state"] != "running":
                break
        self.assertEqual(json.loads((folder / "status.json").read_text())["state"], "cancelled")


class ProjectMode(FakeAgentCase):
    def setUp(self):
        super().setUp()
        self.env["OMNI_AGENT_ACCOUNT_TK"] = FAKE_KEY
        self.assertEqual(self.run_cli("account", "add", "tk", "--kind", "api").returncode, 0)
        self.project = Path(self.tmp.name) / "project"
        self.project.mkdir()
        (self.project / "code.py").write_text("x = 1\n")

    def _run_in(self, cwd, *args, mode="answer"):
        (self.bin / "mode").write_text(mode)
        return subprocess.run([sys.executable, str(BIN), *args], env=dict(self.env), cwd=cwd, capture_output=True, text=True, timeout=60)

    def test_agent_works_read_only_in_project_and_report_comes_from_final_answer(self):
        res = self._run_in(self.project, "run", "--account", "tk", "--project", "--text", "Read code.py")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual((self.bin / "cwd.log").read_text().strip(), str(self.project.resolve()))
        argv = json.loads((self.bin / "argv.log").read_text().splitlines()[-1])
        tool_list = argv[argv.index("--allowed-tools") + 1:]
        self.assertIn("Read", tool_list)
        self.assertNotIn("Write", tool_list)
        self.assertNotIn("Edit", tool_list)
        self.assertNotIn("Bash", tool_list)
        folder = self.last_run()
        self.assertIn("Final answer of the agent", (folder / "report.md").read_text())
        self.assertFalse((self.project / "report.md").exists())  # leave nothing in the project
        self.assertIn("read-only", res.stdout)
        status = json.loads((folder / "status.json").read_text())
        self.assertEqual((status["state"], status["project"], status["writable"]), ("done", str(self.project.resolve()), False))
        self.assertIn("project folder", (self.bin / "argv.log").read_text())  # project frame in the prompt

    def test_writable_enables_write_and_edit(self):
        res = self._run_in(self.project, "run", "--account", "tk", "--project", "--write", "--text", "Change code.py")
        self.assertEqual(res.returncode, 0, res.stderr)
        argv = json.loads((self.bin / "argv.log").read_text().splitlines()[-1])
        tool_list = argv[argv.index("--allowed-tools") + 1:]
        self.assertIn("Write", tool_list)
        self.assertIn("Edit", tool_list)
        self.assertNotIn("Bash", tool_list)

    def test_project_with_third_party_provider_is_allowed_and_read_only(self):
        res = self._run_in(self.project, "run", "--provider", "deepseek", "--project", "--text", "Read code.py")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual((self.bin / "cwd.log").read_text().strip(), str(self.project.resolve()))
        argv = json.loads((self.bin / "argv.log").read_text().splitlines()[-1])
        tool_list = argv[argv.index("--allowed-tools") + 1:]
        self.assertIn("Read", tool_list)
        for forbidden in ("Write", "Edit", "Bash"):
            self.assertNotIn(forbidden, tool_list)

    def test_writable_without_project_and_project_with_material_fail(self):
        self.assertEqual(self._run_in(self.project, "run", "--account", "tk", "--write", "--text", "x").returncode, 2)
        files = Path(self.tmp.name) / "files"
        files.mkdir()
        self.assertEqual(self._run_in(self.project, "run", "--account", "tk", "--project", "--files", str(files), "--text", "x").returncode, 2)

    def test_explicitly_requested_write_without_writable_fails(self):
        res = self._run_in(self.project, "run", "--account", "tk", "--project", "--tools", "read,write", "--text", "x")
        self.assertEqual(res.returncode, 2)
        self.assertIn("--write", res.stderr)

    def test_follow_up_stays_in_project(self):
        self._run_in(self.project, "run", "--account", "tk", "--project", "--text", "First question")
        res = self._run_in(Path(self.tmp.name), "run", "--resume", "--text", "Second question")
        self.assertEqual(res.returncode, 0, res.stderr)
        cwds = (self.bin / "cwd.log").read_text().split()
        self.assertEqual(cwds[0], cwds[1])  # the follow-up runs in the same project, not in the current directory

    def test_codex_sandbox_in_project_is_read_only(self):
        from omni_agent.runner.codex import CodexRunner
        from omni_agent.providers import get_provider
        project, folder = Path("/tmp/projekt"), Path("/tmp/run")
        ctx = RunContext(prompt="p", folder=folder, provider=get_provider("codex"), model="gpt-6.1-sol", base_url=None,
                          protocol="openai-responses", key_values={}, tool_list=("read",), max_turns=5, project=project)
        argv = CodexRunner().build(ctx).argv
        self.assertEqual(argv[argv.index("--sandbox") + 1], "read-only")
        self.assertEqual(argv[argv.index("--cd") + 1], str(project))
        ctx.writable = True
        argv = CodexRunner().build(ctx).argv
        self.assertEqual(argv[argv.index("--sandbox") + 1], "workspace-write")


class ReviewGate(FakeAgentCase):
    def setUp(self):
        super().setUp()
        self.env["OMNI_AGENT_ACCOUNT_TK"] = FAKE_KEY
        self.assertEqual(self.run_cli("account", "add", "tk", "--kind", "api").returncode, 0)
        self.assertEqual(self.run_cli("account", "default", "tk").returncode, 0)
        self.repo, self.git = self._repo()

    def _stop(self, mode="allow", **entry_text):
        (self.bin / "mode").write_text(mode)
        doc = {"session_id": "s1", "cwd": str(self.repo), "last_assistant_message": "Changed m.py", **entry_text}
        return subprocess.run([sys.executable, str(BIN), "hook", "stop"], env=dict(self.env), input=json.dumps(doc),
                              capture_output=True, text=True, timeout=60)

    def _gate(self, enabled=True):
        self.assertEqual(self.run_cli("setup", "--review-gate", "on" if enabled else "off").returncode in (0, 2), True)

    def test_off_is_default_and_passes_silently(self):
        (self.repo / "m.py").write_text("a = 2\n")
        res = self._stop()
        self.assertEqual((res.returncode, res.stdout.strip()), (0, ""))
        self.assertFalse((self.home / "runs").exists())

    def test_on_without_changes_calls_no_model(self):
        self._gate()
        res = self._stop()
        self.assertEqual((res.returncode, res.stdout.strip()), (0, ""))
        self.assertFalse((self.home / "runs").exists())

    def test_block_then_same_state_is_not_blocked_again(self):
        self._gate()
        (self.repo / "m.py").write_text("a = 2\n")
        first = self._stop("block")
        self.assertEqual(first.returncode, 0, first.stderr)
        decision = json.loads(first.stdout)
        self.assertEqual(decision["decision"], "block")
        self.assertIn("file m.py line 1 is broken", decision["reason"])
        second = self._stop("block")  # same diff: do not block a second time, no second run
        self.assertEqual(second.stdout.strip(), "")
        self.assertEqual(len(list((self.home / "runs").iterdir())), 1)
        (self.repo / "m.py").write_text("a = 3\n")  # changed diff: check again
        third = self._stop("block")
        self.assertEqual(json.loads(third.stdout)["decision"], "block")

    def test_allow_passes_and_gives_diff_and_answer_as_material(self):
        self._gate()
        (self.repo / "m.py").write_text("a = 2\n")
        res = self._stop("allow")
        self.assertEqual((res.returncode, res.stdout.strip()), (0, ""))
        folder = sorted((self.home / "runs").iterdir())[-1]
        self.assertTrue(folder.name.endswith("-gate"))
        self.assertIn("+a = 2", (folder / "changes.patch").read_text())
        self.assertIn("Changed m.py", (folder / "last_answer.md").read_text())
        self.assertEqual(json.loads((folder / "status.json").read_text())["kind"], "gate")

    def test_secret_in_diff_skips_the_gate(self):
        self._gate()
        (self.repo / "k.py").write_text('API_KEY = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"\n')
        self.git("add", "-N", "k.py")
        res = self._stop("block")
        self.assertEqual(res.stdout.strip(), "")
        self.assertIn("skipped", res.stderr)
        self.assertFalse((self.home / "runs").exists())

    def test_gate_inside_a_run_does_nothing(self):
        self._gate()
        (self.repo / "m.py").write_text("a = 2\n")
        self.env["OMNI_AGENT_RUN"] = "1"
        self.assertEqual(self._stop("block").stdout.strip(), "")

    def test_enabling_needs_default_account(self):
        self.assertEqual(self.run_cli("account", "default", "--delete").returncode, 0)
        self.assertEqual(self.run_cli("setup", "--review-gate", "on").returncode, 2)

    def test_stop_points_to_running_runs(self):
        (self.bin / "mode").write_text("hangs")
        env = dict(self.env, OMNI_AGENT_SESSION="s1")
        subprocess.run([sys.executable, str(BIN), "run", "--background", "--text", "x", "--account", "tk", "--timeout", "60"],
                       env=env, capture_output=True, text=True, timeout=30)
        try:
            res = self._stop()
            self.assertIn("still running", res.stderr)
        finally:
            subprocess.run([sys.executable, str(BIN), "cancel"], env=env, capture_output=True, text=True, timeout=60)


class ReviewContract(FakeAgentCase):
    def test_task_has_fixed_report_skeleton(self):
        repo, _ = self._repo()
        (repo / "m.py").write_text("a = 2\n")
        self.assertEqual(self._review(repo, "--provider", "deepseek").returncode, 0)
        task = (self.last_run() / "task.md").read_text()
        for marker in ("## Verdict", "approve", "needs-work", "## Findings", "### [critical|high|medium|low]", "- Confidence:", "## Next steps"):
            self.assertIn(marker, task)
        self.assertNotIn("<stance>", task)  # no stance without --adversarial

    def test_adversarial_adds_stance_and_attack_surface(self):
        repo, _ = self._repo()
        (repo / "m.py").write_text("a = 2\n")
        self._review(repo, "--provider", "deepseek", "--adversarial")
        task = (self.last_run() / "task.md").read_text()
        self.assertIn("<stance>", task)
        self.assertIn("<attack-surface>", task)

    def test_clean_tree_checks_the_branch_against_the_main_branch(self):
        repo, git = self._repo()
        git("branch", "-M", "main")
        git("checkout", "-qb", "feature")
        (repo / "m.py").write_text("a = 99\n")
        git("commit", "-qam", "feature")
        res = self._review(repo, "--provider", "deepseek")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("branch against main", res.stdout)
        self.assertIn("+a = 99", (self.last_run() / "changes.patch").read_text())

    def test_review_background_preview_starts_nothing(self):
        repo, _ = self._repo()
        (repo / "m.py").write_text("a = 2\n")
        res = self._review(repo, "--provider", "deepseek", "--background", "--preview")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("nothing sent", res.stdout)
        self.assertFalse((self.home / "runs").exists())


class RemoteHosts(WithHome):
    """--host forwards over ssh. A fake ssh logs what it receives."""

    def setUp(self):
        super().setUp()
        self.bin = Path(self.tmp.name) / "bin"
        self.bin.mkdir()
        fake = self.bin / "ssh"
        fake.write_text(textwrap.dedent(f"""\
            #!{sys.executable}
            import json, sys, pathlib
            d = pathlib.Path(__file__).parent
            with open(d / "ssh.log", "a") as f:
                f.write(json.dumps(sys.argv[1:]) + "\\n")
            code = int((d / "code").read_text()) if (d / "code").exists() else 0
            print("answer from target")
            sys.exit(code)
            """))
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        self.env = {**os.environ, "OMNI_AGENT_HOME": str(self.home), "PATH": f"{self.bin}:{os.environ['PATH']}"}
        self.env.pop("OMNI_AGENT_SESSION", None)

    def cli(self, *args, **env):
        return subprocess.run([sys.executable, str(BIN), *args], env={**self.env, **env}, capture_output=True, text=True, timeout=60)

    def last_ssh(self):
        return json.loads((self.bin / "ssh.log").read_text().splitlines()[-1])

    def test_host_add_validates_input_and_lists(self):
        self.assertEqual(self.cli("host", "add", "mini", "--ssh", "alex@100.64.0.7").returncode, 0)
        self.assertIn("alex@100.64.0.7", self.cli("host", "list").stdout)
        self.assertEqual(self.cli("host", "add", "mini", "--ssh", "x@y").returncode, 2)  # already exists
        self.assertEqual(self.cli("host", "add", "boese", "--ssh", "-oProxyCommand=x").returncode, 2)
        self.assertEqual(self.cli("host", "add", "empty", "--ssh", "a b").returncode, 2)
        self.assertEqual(self.cli("host", "add", "Gross", "--ssh", "x@y").returncode, 2)

    def test_run_is_forwarded_unchanged_without_host(self):
        self.cli("host", "add", "mini", "--ssh", "alex@mini")
        res = self.cli("run", "--host", "mini", "--provider", "codex", "--wait", "60", "--text", "Question with 'quote' and $VAR")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("answer from target", res.stdout)
        argv = self.last_ssh()
        self.assertEqual(argv[argv.index("--") + 1], "alex@mini")
        remote = argv[-1]
        self.assertTrue(remote.startswith("omni-agent run "))
        self.assertNotIn("--host", remote)
        self.assertIn("--wait 60", remote)
        self.assertIn("'Question with '\"'\"'quote'\"'\"' and $VAR'", remote)  # quoted, nothing is evaluated locally or remotely
        self.assertIn("BatchMode=yes", argv)

    def test_session_goes_along(self):
        self.cli("host", "add", "mini", "--ssh", "alex@mini")
        self.cli("status", "--host", "mini", OMNI_AGENT_SESSION="sess-1")
        self.assertTrue(self.last_ssh()[-1].startswith("OMNI_AGENT_SESSION=sess-1 omni-agent status"))

    def test_local_task_file_is_sent_along_as_text(self):
        self.cli("host", "add", "mini", "--ssh", "alex@mini")
        data_file = Path(self.tmp.name) / "task.md"
        data_file.write_text("Read everything and summarize")
        res = self.cli("run", "--host", "mini", str(data_file))
        self.assertEqual(res.returncode, 0, res.stderr)
        remote = self.last_ssh()[-1]
        self.assertNotIn(str(data_file), remote)
        self.assertIn("--text 'Read everything and summarize'", remote)

    def test_material_and_review_do_not_work_with_host(self):
        self.cli("host", "add", "mini", "--ssh", "alex@mini")
        files = Path(self.tmp.name) / "files"
        files.mkdir()
        self.assertEqual(self.cli("run", "--host", "mini", "--files", str(files), "--text", "x").returncode, 2)
        self.assertEqual(self.cli("review", "--host", "mini").returncode, 2)
        self.assertFalse((self.bin / "ssh.log").exists())

    def test_unknown_target_and_ssh_error(self):
        res = self.cli("run", "--host", "nirgends", "--text", "x")
        self.assertEqual(res.returncode, 2)
        self.assertIn("host add", res.stderr)
        self.cli("host", "add", "mini", "--ssh", "alex@mini")
        (self.bin / "code").write_text("255")
        res = self.cli("status", "--host", "mini")
        self.assertEqual(res.returncode, 255)
        self.assertIn("host test mini", res.stderr)

    def test_host_test_reports_missing_command(self):
        self.cli("host", "add", "mini", "--ssh", "alex@mini")
        (self.bin / "code").write_text("127")
        res = self.cli("host", "test", "mini")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("host install mini", res.stdout)


class Robustness(FakeAgentCase):
    """No compatibility layer: only the current names. Damaged run folders must not crash the readers."""

    def _run_dir(self, name, status):
        folder = self.home / "runs" / name
        folder.mkdir(parents=True)
        if status is not None:
            (folder / "status.json").write_text(status if isinstance(status, str) else json.dumps(status))
        return folder

    def test_status_json_without_expected_keys_crashes_nothing(self):
        self._run_dir("20250101-000001-deepseek", {})
        self._run_dir("20250101-000002-deepseek", [1, 2])
        self._run_dir("20250101-000003-deepseek", "{broken")
        self._run_dir("20250101-000004-deepseek", None)
        good = self._run_dir("20250101-000005-deepseek", {"state": "done", "provider": "deepseek", "model": "m"})
        (good / "report.md").write_text("# Result\nok\n")
        res = self.run_cli("status", "--all", "--json")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual([z["run"] for z in json.loads(res.stdout)], ["20250101-000005-deepseek"])
        self.assertEqual(self.run_cli("wait", "20250101-000005", "--max", "5").returncode, 0)
        self.assertIn("# Result", self.run_cli("result").stdout)
        self.assertEqual(self.run_cli("status").returncode, 0)

    def test_env_names(self):
        self.env.pop("OMNI_AGENT_NO_NETCHECK")
        (self.home / "providers.d").mkdir(parents=True)
        (self.home / "providers.d" / "tot.json").write_text(json.dumps([
            {"id": "tot", "protocols": ["anthropic"], "base_url": "http://127.0.0.1:9", "key_envs": [], "key_placeholder": "x", "models": {"default": "m"}}
        ]))
        self.assertEqual(self.run_cli("run", "--text", "x", "--provider", "tot", "--runner", "claude").returncode, 3)
        self.env["OMNI_AGENT_NO_NETCHECK"] = "1"
        self.assertEqual(self.run_cli("run", "--text", "x", "--provider", "tot", "--runner", "claude").returncode, 0)
        self.env["OMNI_AGENT_SESSION"] = "s-1"
        self.run_cli("run", "--text", "with session", "--provider", "deepseek")
        status = json.loads(sorted((self.home / "runs").glob("*-deepseek"))[-1].joinpath("status.json").read_text())
        self.assertEqual(status["claude_session"], "s-1")

    def test_review_gate_on_off_and_default(self):
        self.assertEqual(self.run_cli("account", "add", "tk", "--kind", "api").returncode, 0)
        self.assertEqual(self.run_cli("account", "default", "tk").returncode, 0)
        self.assertIn("none", (self.run_cli("account", "default", "--delete"), self.run_cli("account", "default"))[1].stdout)
        self.assertEqual(self.run_cli("account", "default", "tk").returncode, 0)
        self.assertIn(self.run_cli("setup", "--review-gate", "on").returncode, (0, 2))
        self.assertIs(json.loads((self.home / "config.json").read_text()).get("review_gate"), True)
        self.assertIn(self.run_cli("setup", "--review-gate", "off").returncode, (0, 2))
        self.assertFalse(json.loads((self.home / "config.json").read_text()).get("review_gate"))
        # German values are rejected by the parser
        self.assertEqual(self.run_cli("setup", "--review-gate", "an").returncode, 2)
        for name in ("stop", "end"):
            res = subprocess.run([sys.executable, str(BIN), "hook", name], env=dict(self.env), input=json.dumps({"session_id": "s"}),
                                 capture_output=True, text=True, timeout=60)
            self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(subprocess.run([sys.executable, str(BIN), "hook", "stopp"], env=dict(self.env), capture_output=True, text=True, timeout=60).returncode, 2)

    def test_hook_is_a_noop_inside_a_run(self):
        data_file = Path(self.tmp.name) / "claude-env"
        res = subprocess.run([sys.executable, str(BIN), "hook", "start"], env=dict(self.env, CLAUDE_ENV_FILE=str(data_file), OMNI_AGENT_RUN="1"),
                             input=json.dumps({"session_id": "x"}), capture_output=True, text=True, timeout=60)
        self.assertEqual(res.returncode, 0)
        self.assertFalse(data_file.exists())

    def test_old_names_are_no_longer_understood(self):
        self.assertNotEqual(self.run_cli("konto", "list").returncode, 0)
        self.assertNotEqual(self.run_cli("run", "--text", "x", "--anbieter", "deepseek").returncode, 0)
        self.assertNotEqual(self.run_cli("run", "--text", "x", "--provider", "deepseek", "--tools", "lesen").returncode, 0)

    def test_config_only_new_keys(self):
        from omni_agent import config
        self.home.mkdir(parents=True)
        (self.home / "config.json").write_text(json.dumps({"default_provider": "claude-fbs", "review_gate": True,
                                                           "review_gate_provider": "claude-fbs", "review_gate_model": "sonnet",
                                                           "standard_anbieter": "ignored"}))
        os.environ["OMNI_AGENT_HOME"] = str(self.home)
        self.assertEqual(config.default_provider(), "claude-fbs")
        self.assertTrue(config.review_gate_an())
        (self.home / "config.json").write_text(json.dumps({"standard_anbieter": "claude-fbs"}))
        self.assertIsNone(config.default_provider())

    def test_provider_json_only_english_keys(self):
        from omni_agent.providers import _from_dict
        a = _from_dict({"id": "a", "protocols": ["anthropic"], "base_url": "http://x", "key_envs": ["K"], "models": {"default": "m", "strong": "s"},
                       "note": "H", "verified": True, "model_required": True, "account_kind": "token", "runner_only": "claude",
                       "key_placeholder": "p", "empty_vars": ["V"]}, "test")
        self.assertEqual((a.pick_model("strong"), a.pick_model("default"), a.pick_model("frei")), ("s", "m", "frei"))
        self.assertEqual((a.note, a.verified, a.account_kind, a.only_runner, a.empty_vars), ("H", True, "token", "claude", ("V",)))
        with self.assertRaises(ConfigError):
            _from_dict({"id": "a", "protocols": ["anthropic"], "key_envs": [], "models": {"standard": "m"}}, "test")
        self.assertEqual(a.pick_model("stark"), "stark")  # no tier of that name: taken as a free model name


class UsageAndCredits(unittest.TestCase):
    def test_codex_line_shows_plan_window_reset_and_credits(self):
        from omni_agent import usage
        text = usage.codex_text({
            "ordinaryUsageAllowed": True,
            "rateLimits": {"planType": "prolite", "primary": {"usedPercent": 42, "windowDurationMins": 10080, "resetsAt": 1794846023},
                           "secondary": {"usedPercent": 7, "windowDurationMins": 300, "resetsAt": 1794846023},
                           "credits": {"hasCredits": True, "unlimited": False, "balance": "12.5"}},
            "rateLimitResetCredits": {"availableCount": 2},
        })
        for part in ("Plan prolite", "7 days 42% used", "5 h 7% used", "credits 12.5", "2 reset credits"):
            self.assertIn(part, text)

    def test_codex_reports_block(self):
        from omni_agent import usage
        text = usage.codex_text({"ordinaryUsageAllowed": False, "rateLimits": {"rateLimitReachedType": "rate_limit_reached"}})
        self.assertIn("STATUS", text)
        self.assertIn("normal usage blocked", text)

    def test_deepseek_kimi_and_credits(self):
        from omni_agent import usage
        ds = usage._deepseek("k", lookup=lambda u, k: {"is_available": True, "balance_infos": [{"currency": "USD", "total_balance": "9.18", "granted_balance": "0.00", "topped_up_balance": "9.18"}]})
        self.assertIn("Balance 9.18 USD", ds)
        empty = usage._deepseek("k", lookup=lambda u, k: {"is_available": False, "balance_infos": []})
        self.assertIn("STATUS", empty)
        kimi = usage._kimi("k", lookup=lambda u, k: {"data": {"available_balance": 3.5, "voucher_balance": 1, "cash_balance": 2.5}})
        self.assertIn("available 3.50", kimi)
        cr = usage._credits("https://x/api/v1", "EUR")("k", lookup=lambda u, k: {"data": {"total_credits": 10, "total_usage": 2.5}})
        self.assertIn("Balance 7.50 EUR", cr)

    def test_credits_are_honest_without_query_and_without_key(self):
        from omni_agent import usage
        self.assertEqual(usage.balance("nvidia", "k"), "no query known")
        self.assertEqual(usage.balance("deepseek", None), "key missing")
        self.assertIn("locally", usage.balance("ollama", None))

        def broken(key_values):
            raise ConfigError("HTTP 401")
        self.assertIn("HTTP 401", usage.balance("deepseek", "k", {"deepseek": broken}))


if __name__ == "__main__":
    unittest.main()
