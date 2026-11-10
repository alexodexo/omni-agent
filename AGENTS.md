# Omni-Agent: notes for agents working on this repo

Omni-Agent is a Python core (`bin/omni-agent`, `lib/omni_agent/`, standard library only) with a thin Claude Code plugin shell (`.claude-plugin/`, `agents/`, `commands/`, `skills/`, `hooks/`). Language in the repo, in commits and tests: English.

## Layout

| Location | Contents |
|---|---|
| `bin/omni-agent` | Entry point. Finds `lib/` through its own file path (also via symlink); `${CLAUDE_PLUGIN_ROOT}` is not set in Bash commands |
| `lib/omni_agent/engine.py` | Run: choose, start, monitor, `status.json` |
| `lib/omni_agent/runner/` | One adapter per agent CLI (`claude`, `opencode`, `codex`, `dsh`), matching rule in `__init__.py` |
| `lib/omni_agent/providers.py` + `providers.json` | Providers as data |
| `lib/omni_agent/extras.py` + `extras/litellm/` | Optional translator, pinned with a hash lock |
| `lib/omni_agent/hooks.py` | Hook entry points (`hook start|end|stop`) and review gate |
| `agents/worker.md` | Subagent `omni-agent:worker`, a thin forwarder; its description triggers delegation |
| `commands/*.md` | Slash commands (text for Claude, no code); `status`/`result`/`cancel`/`doctor`/`accounts` via `!` inline execution |
| `skills/omni-agent-*/SKILL.md` | Internal skills (`user-invocable: false`): runtime contract, writing a task, passing on results |
| `hooks/hooks.json` | SessionStart, SessionEnd, Stop |
| `tests/` | `python3 -m unittest discover -s tests -v` |

## Rules

- **New provider:** an entry in `providers.json` (no code); set `verified` to `true` only if a real run succeeded. Be honest about the data location in `region` and the README table: unknown means "not documented".
- **New runner:** a class in `runner/`, register it in `RUNNER`, cover the command building with a test. Never put experimental runners in `AUTO_ORDER`.
- **Keys** never in the repo, in the log, in the chat. A runner gets only the keys from `RunContext.key_values` (exactly one). The environment is rebuilt (`base_env()`), never inherited.
- **Done means `report.md` exists.** The exit code of the runner is only an additional signal.
- **What a runner cannot do is refused**, not silently dropped (`resolve_tools`). Only default tools may shrink silently.
- **Documented commands are tested:** every `omni-agent …` line in `commands/`, `agents/` and `skills/` must be accepted by the real parser (`PluginAufbau.test_dokumentierte_befehle_sind_echte_befehle`). New flag? First in the parser, then in the docs.
- **The subagent only forwards.** New logic belongs in the core (`lib/`), not in `agents/worker.md`. Hooks never do anything when `OMNI_AGENT_RUN=1` is set (runs do not start runs).
- **Naming:** the user-facing interface (commands, flags, files, env vars, config keys) is English. The German spellings are gone: no aliases, no fallbacks.
- **Version:** `lib/omni_agent/__init__.py` (`VERSION`) and `.claude-plugin/plugin.json` (`version`) stay equal (test). If you do not raise `version`, users get no update.
- **LiteLLM pin:** change it only after reading the vendor's incident page; regenerate the lock file with hashes (`uv pip compile --generate-hashes`).
- Before every commit: tests and `claude plugin validate --strict .`. Before every release: a secrets scan of the tree **and** of the git history.
- No time estimates in plans; only order and gates.
