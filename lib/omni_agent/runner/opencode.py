"""Runner `opencode`: speaks OpenAI-compatible providers itself, without a translator.

State: built from the vendor docs, NOT verified live (opencode was not installed).
Two version lines exist and exit codes are not documented: the proof of completion is report.md.
"""
from __future__ import annotations

import json

from .base import Command, RunContext, Runner, base_env, shorten


class OpencodeRunner(Runner):
    name = "opencode"
    binary = "opencode"
    protocols = ("openai-chat", "openai-responses", "anthropic")
    can = frozenset({"read", "write", "web_search", "web_fetch", "shell"})
    note = "Second choice. Speaks OpenAI formats directly (EUrouter, Nvidia). Not verified live."

    def build(self, ctx: RunContext) -> Command:
        a = ctx.provider
        env = base_env()
        key_env = a.key_envs[0] if a.key_envs else None
        if key_env and key_env in ctx.key_values:
            env[key_env] = ctx.key_values[key_env]

        npm = "@ai-sdk/anthropic" if ctx.protocol == "anthropic" else "@ai-sdk/openai-compatible"
        options = {"baseURL": ctx.base_url}
        if key_env:
            options["apiKey"] = "{env:%s}" % key_env
        allowed = set(ctx.tool_list)
        config = {
            "$schema": "https://opencode.ai/config.json",
            "autoupdate": False,
            "share": "disabled",
            "provider": {a.id: {"npm": npm, "name": a.name, "options": options, "models": {ctx.model: {"name": ctx.model}}}},
            "permission": {
                "read": "allow" if "read" in allowed else "deny",
                "list": "allow" if "read" in allowed else "deny",
                "glob": "allow" if "read" in allowed else "deny",
                "grep": "allow" if "read" in allowed else "deny",
                "edit": "allow" if "write" in allowed else "deny",
                "bash": "allow" if "shell" in allowed else "deny",
                "webfetch": "allow" if "web_fetch" in allowed else "deny",
                "websearch": "allow" if "web_search" in allowed else "deny",
                "external_directory": "deny",
            },
        }
        env["OPENCODE_CONFIG_CONTENT"] = json.dumps(config)
        argv = [self.file_path() or self.binary, "run", "--format", "json", "--model", f"{a.id}/{ctx.model}", ctx.prompt]
        return Command(argv=argv, env=env)

    def progress(self, line: str, state: dict) -> list:
        try:
            o = json.loads(line)
        except ValueError:
            return [shorten(line, 160)] if line.strip() else []
        etype = str(o.get("type", ""))
        if "tool" in etype:
            state["turns"] = state.get("turns", 0) + 1
            part = o.get("part") or {}
            return [f"Tool {state['turns']}: {part.get('tool') or etype}"]
        if etype == "text":
            text = (o.get("part") or {}).get("text") or ""
            if text.strip():
                state["final_answer"] = text  # last answer: in project mode it becomes the report
                return [f"Agent: {shorten(text)}"]
            return []
        return []
