"""Runner `codex`: OpenAI Codex CLI (`codex exec`). Speaks only the Responses API.

Two kinds:
- Provider `codex` (account kind "login"): the sign-in of the Codex CLI itself (ChatGPT account or API key
  from `codex login`). Verified live with the ChatGPT account. The user's personal config.toml and rules
  are NOT loaded (--ignore-user-config, --ignore-rules); only the sign-in is used.
- Third-party provider with a Responses API (e.g. EUrouter): its own empty CODEX_HOME. Not verified live.

Codex cannot forbid individual tools; its shell is always there (limited only by the sandbox).
That is why the core explicitly requires `--tools +shell` here.
"""
from __future__ import annotations

import json
import os
import shutil

from .base import Command, RunContext, Runner, base_env, shorten


class CodexRunner(Runner):
    name = "codex"
    binary = "codex"
    protocols = ("openai-responses",)
    can = frozenset({"read", "write", "shell"})
    cannot_forbid = frozenset({"shell"})
    in_sandbox = True  # --sandbox workspace-write: write only in the run folder, no network
    note = "Responses API only. Shell is always there (sandbox workspace-write). Verified live with provider 'codex' (sign-in)."

    # Places where Codex lives without being on PATH (e.g. shipped with the ChatGPT app)
    LOCATIONS = (
        "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex",
        "/Applications/Codex.app/Contents/Resources/codex",
    )

    def file_path(self) -> str | None:
        if os.environ.get("OMNI_AGENT_CODEX") and os.access(os.environ["OMNI_AGENT_CODEX"], os.X_OK):
            return os.environ["OMNI_AGENT_CODEX"]
        found = shutil.which(self.binary)
        if found:
            return found
        for location in self.LOCATIONS:
            if os.access(location, os.X_OK):
                return location
        return None

    def build(self, ctx: RunContext) -> Command:
        a = ctx.provider
        env = base_env()
        exe = self.file_path() or self.binary
        session = ctx.extra.get("resume")
        effort = ctx.extra.get("effort")
        options = ["--json", "--skip-git-repo-check"]
        # In a project read-only, unless the user allows writing; in the run folder the agent may write report.md.
        sandbox = "read-only" if (ctx.project and not ctx.writable) else "workspace-write"
        # `resume` knows neither --sandbox nor --cd: same effect via -c, the folder is the current directory
        options += ["-c", f'sandbox_mode="{sandbox}"'] if session else ["--sandbox", sandbox]

        if a.account_kind == "login":
            # The CLI's own sign-in; the user's own settings and rules stay out.
            if os.environ.get("CODEX_HOME"):
                env["CODEX_HOME"] = os.environ["CODEX_HOME"]
            options += ["--ignore-user-config", "--ignore-rules"]
            model_options = ["--model", ctx.model]
        else:
            key_env = a.key_envs[0] if a.key_envs else "OMNI_AGENT_KEY"
            if key_env in ctx.key_values:
                env[key_env] = ctx.key_values[key_env]
            env["CODEX_HOME"] = str(ctx.folder / ".codex-home")  # own, empty configuration
            provider_toml = (
                '{ name = "%s", base_url = "%s", env_key = "%s", wire_api = "responses" }'
                % (a.name, ctx.base_url, key_env)
            )
            options += ["-c", f"model_provider={json.dumps(a.id)}", "-c", f"model_providers.{a.id}={provider_toml}"]
            model_options = ["--model", ctx.model]
        if effort:
            options += ["-c", f"model_reasoning_effort={json.dumps(effort)}"]

        if session:
            argv = [exe, "exec", "resume", *options, *model_options, session, ctx.prompt]
        else:
            argv = [exe, "exec", *options, "--cd", str(ctx.work_dir), *model_options, ctx.prompt]
        return Command(argv=argv, env=env)

    def progress(self, line: str, state: dict) -> list:
        try:
            o = json.loads(line)
        except ValueError:
            return [shorten(line, 160)] if line.strip() else []
        if o.get("type") == "thread.started" and o.get("thread_id"):
            state["session"] = o["thread_id"]
            return []
        item = o.get("item") or {}
        kind = item.get("type") or o.get("type") or ""
        if kind in ("command_execution", "file_change", "web_search", "mcp_tool_call") and o.get("type") == "item.started":
            state["turns"] = state.get("turns", 0) + 1
            return [f"Tool {state['turns']}: {kind}"]
        if kind == "agent_message" and item.get("text"):
            state["final_answer"] = item["text"]  # last answer: in project mode it becomes the report
            return [f"Agent: {shorten(item['text'])}"]
        return []
