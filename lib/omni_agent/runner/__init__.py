"""Runner registry and matching rule (provider protocol x runner protocols)."""
from __future__ import annotations

from ..config import ConfigError
from .base import DEFAULT_TOOLS, TOOLS, Runner
from .claude import ClaudeRunner
from .codex import CodexRunner
from .dsh import DshRunner
from .opencode import OpencodeRunner

RUNNER = {r.name: r for r in (ClaudeRunner(), OpencodeRunner(), CodexRunner(), DshRunner())}
AUTO_ORDER = ("claude", "opencode", "codex")  # dsh is never picked automatically


def effective_protocol(provider, runner: Runner, via_litellm: bool) -> str | None:
    """Which protocol runner and provider both speak, or None."""
    if via_litellm:
        # The local translator turns an OpenAI provider into an Anthropic endpoint.
        if "openai-chat" in provider.protocols and runner.speaks("anthropic"):
            return "anthropic"
        return None
    for protocol in provider.protocols:
        if runner.speaks(protocol):
            return protocol
    return None


def fits(provider, runner: Runner, via_litellm: bool = False) -> bool:
    if runner.name == "dsh" and provider.id != "deepseek":
        return False
    forced = provider.runner_only
    if forced and runner.name != forced:
        return False  # accounts without an address only run through their own agent CLI
    if forced and forced == runner.name:
        return True
    return effective_protocol(provider, runner, via_litellm) is not None


def choose_runner(provider, requested: str | None, via_litellm: bool = False) -> Runner:
    """Without a request: the first INSTALLED runner of claude, opencode, codex that fits."""
    if requested:
        if requested not in RUNNER:
            raise ConfigError(f"Unknown runner '{requested}'. Known: {', '.join(RUNNER)}")
        runner = RUNNER[requested]
        if not runner.file_path():
            raise ConfigError(f"Runner '{requested}' is not installed (command '{runner.binary}' not on PATH)")
        if not fits(provider, runner, via_litellm):
            raise ConfigError(explain_mismatch(provider, runner, via_litellm))
        return runner

    installed = [RUNNER[n] for n in AUTO_ORDER if RUNNER[n].file_path()]
    if not installed:
        raise ConfigError("No runner installed. At least one agent CLI is needed: claude, opencode or codex")
    for runner in installed:
        if fits(provider, runner, via_litellm):
            return runner
    raise ConfigError(
        f"No installed runner fits '{provider.id}' (protocol: {', '.join(provider.protocols)}). "
        + explain_mismatch(provider, installed[0], via_litellm)
    )


def explain_mismatch(provider, runner: Runner, via_litellm: bool) -> str:
    if runner.name == "dsh" and provider.id != "deepseek":
        return "Runner 'dsh' is only meant for the provider 'deepseek'."
    forced = provider.runner_only
    if forced and runner.name != forced:
        return f"Provider '{provider.id}' (account of the agent CLI) only runs through the runner '{forced}'."
    speaks_text = ", ".join(provider.protocols)
    text = f"Provider '{provider.id}' speaks {speaks_text}, runner '{runner.name}' speaks {', '.join(runner.protocols)}."
    if "openai-chat" in provider.protocols and runner.speaks("anthropic") and not via_litellm:
        text += " Options: --runner opencode, or Claude Code through the LiteLLM extra (--via-litellm)."
    elif "openai-responses" not in provider.protocols and runner.name == "codex":
        text += " Codex only speaks the Responses API."
    else:
        text += " Pick another runner (omni-agent runners)."
    return text


def resolve_tools(requested: str | None, runner: Runner) -> tuple:
    """Turn --tools into a list of neutral tools. Refuses what the runner cannot do.

    Without a value: the default (no shell), reduced to what the runner can do.
    Syntax: 'read,write' replaces the default, '+shell' adds, '-web_search' removes.
    """
    current = set(DEFAULT_TOOLS)
    named = set()  # what the user explicitly asked for
    if requested:
        parts = [t for t in requested.replace(",", " ").split() if t]
        replaced = False
        for part in parts:
            op, name = (part[0], part[1:]) if part[0] in "+-" else ("=", part)
            if name not in TOOLS:
                raise ConfigError(f"Unknown tool '{name}'. Known: {', '.join(TOOLS)}")
            if op == "=":
                if not replaced:
                    current = set()
                    replaced = True
                current.add(name)
                named.add(name)
            elif op == "+":
                current.add(name)
                named.add(name)
            else:
                current.discard(name)

    missing = current - runner.can
    requested_but_impossible = missing & named
    if requested_but_impossible:
        raise ConfigError(
            f"Runner '{runner.name}' cannot control {', '.join(sorted(requested_but_impossible))}. "
            f"Refused instead of silently doing less. It can: {', '.join(sorted(runner.can))}"
        )
    current -= missing  # only default tools shrink, when nobody asked for them

    not_forbidden = runner.cannot_forbid - current
    if not_forbidden and runner.in_sandbox:
        current |= not_forbidden  # runs inside the runner's sandbox; the run's tools line shows it openly
        not_forbidden = set()
    if not_forbidden:
        raise ConfigError(
            f"Runner '{runner.name}' always has {', '.join(sorted(not_forbidden))}. "
            f"Please allow it explicitly: --tools +{sorted(not_forbidden)[0]}"
        )
    return tuple(w for w in TOOLS if w in current)
