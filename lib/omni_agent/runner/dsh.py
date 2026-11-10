"""Runner `dsh`: DeepSeek Harness (`@deepseek-ai/dsh`). EXPERIMENTAL, never picked automatically.

The developer preview (0.1.x, with announced breaking changes) can be called as `dsh --profile headless "<task>"`.
How the profile reads its key is not documented; Omni-Agent passes DEEPSEEK_API_KEY through and
relies on report.md as the only proof of completion.
"""
from __future__ import annotations

from .base import Command, RunContext, Runner, base_env, shorten


class DshRunner(Runner):
    name = "dsh"
    binary = "dsh"
    protocols = ("anthropic", "openai-chat")
    can = frozenset({"read", "write", "shell"})
    cannot_forbid = frozenset({"shell"})
    experimental = True
    note = "EXPERIMENTAL (developer preview). Only on explicit choice with --runner dsh. DeepSeek provider only."

    def build(self, ctx: RunContext) -> Command:
        env = base_env()
        env.update(ctx.key_values)
        argv = [self.file_path() or self.binary, "--profile", "headless", ctx.prompt]
        return Command(argv=argv, env=env)

    def progress(self, line: str, state: dict) -> list:
        return [shorten(line, 160)] if line.strip() else []
