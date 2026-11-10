"""Runner `claude`: Claude Code in headless mode (`claude -p`). The default and the best documented."""
from __future__ import annotations

import json

from .base import Command, RunContext, Runner, base_env, shorten

# neutral -> Claude Code tool names
TOOL_MAP = {
    "read": ("Read", "Glob", "Grep"),
    "write": ("Write", "Edit"),
    "web_search": ("WebSearch",),
    "web_fetch": ("WebFetch",),
    "shell": ("Bash",),
}


class ClaudeRunner(Runner):
    name = "claude"
    binary = "claude"
    protocols = ("anthropic",)
    can = frozenset(TOOL_MAP)
    note = "Default. Fine-grained tool permissions, stream-json output."

    def build(self, ctx: RunContext) -> Command:
        a = ctx.provider
        env = base_env()
        env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"

        if ctx.base_url:
            # Third-party provider or local translator: set address, access and ALL model tiers,
            # otherwise background tiers (Haiku, subagents) fail silently.
            env["ANTHROPIC_BASE_URL"] = ctx.base_url
            token = next(iter(ctx.key_values.values()), None) or a.key_placeholder or ""
            env["ANTHROPIC_AUTH_TOKEN"] = token
            for name in a.empty_vars:
                env[name] = ""
            # The provider's small tier only when the default model runs; an explicitly
            # chosen model applies to all tiers.
            small = a.models.get("small") if ctx.model == a.models.get("default") else None
            env["ANTHROPIC_MODEL"] = ctx.model
            env["ANTHROPIC_DEFAULT_OPUS_MODEL"] = ctx.model
            env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = ctx.model
            env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = small or ctx.model
            env["CLAUDE_CODE_SUBAGENT_MODEL"] = ctx.model
        else:
            # Another Claude account: key under its own name, no base URL change.
            if a.account_kind and ctx.key_values:
                value = next(iter(ctx.key_values.values()))
                env["CLAUDE_CODE_OAUTH_TOKEN" if a.account_kind == "token" else "ANTHROPIC_API_KEY"] = value
            else:
                env.update(ctx.key_values)
            env["ANTHROPIC_MODEL"] = ctx.model

        tools = []
        for neutral in ctx.tool_list:
            tools.extend(TOOL_MAP[neutral])

        argv = [
            self.file_path() or self.binary, "-p", ctx.prompt,
            "--output-format", "stream-json", "--verbose",
            "--strict-mcp-config", "--setting-sources", "project",
            "--permission-mode", "dontAsk",
        ]
        session = ctx.extra.get("resume")
        if session:
            argv += ["--resume", session]
        if tools:
            argv += ["--allowed-tools", *tools]
        return Command(argv=argv, env=env)

    def progress(self, line: str, state: dict) -> list:
        try:
            o = json.loads(line)
        except ValueError:
            return []
        etype = o.get("type")
        out = []
        if etype == "system" and o.get("subtype") == "init":
            if o.get("session_id"):
                state["session"] = o["session_id"]
            out.append(f"Start, model: {o.get('model')}")
        elif etype == "assistant":
            for c in (o.get("message") or {}).get("content") or []:
                if c.get("type") == "text" and (c.get("text") or "").strip():
                    out.append(f"Agent: {shorten(c['text'])}")
                elif c.get("type") == "tool_use":
                    state["turns"] = state.get("turns", 0) + 1
                    entry_text = c.get("input") or {}
                    detail = entry_text.get("query") or entry_text.get("url") or entry_text.get("file_path") or ""
                    out.append(f"Tool {state['turns']}: {c.get('name')} {shorten(detail)}")
        elif etype == "result":
            state["final_answer"] = o.get("result")
            out.append(
                f"DONE ({o.get('subtype')}), {o.get('num_turns')} turns, "
                f"{(o.get('duration_ms') or 0) // 1000}s, cost per CLI: ${o.get('total_cost_usd')}"
            )
        return out
