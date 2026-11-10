# Changelog

## 1.3.0

- **Clean break: 1.3.0 keeps no compatibility with the German names.** Old subcommands, flags, hook names, tool names (`lesen`, `schreiben`, `web_suche`, `web_laden`), `an`/`aus`, env vars (`OMNI_AGENT_KONTO_<NAME>`, `OMNI_AGENT_LAUF`, `OMNI_AGENT_SITZUNG`, ...), config keys, `providers.json` keys and tier names, `konto-*.json`, old report file names and old run states are no longer read. Users on older versions set things up again.
- **The whole plugin is English now.** Docs, command texts, CLI help and messages, prompts sent to models, report headings and the schema keys of `providers.json` are English.
- **Renamed commands, flags, files, env vars and config keys.** For example `konto` is `account`, `nutzung` is `usage`, `warte` is `wait`, `anbieter` is `providers`; `--anbieter` is `--provider`, `--konto` is `--account`, `--projekt` is `--project`, `--schreibend` is `--write`, `--hintergrund` is `--background`, `--warten` is `--wait`, `--fortsetzen` is `--resume`. Env vars follow (`OMNI_AGENT_ACCOUNT_<NAME>`, `OMNI_AGENT_RUN`, `OMNI_AGENT_SESSION`), as do the `config.json` keys (`default_provider`, `review_gate_provider`, `review_gate_model`). Slash commands: `/omni-agent:accounts` and `/omni-agent:usage`.
- **Subagent renamed to `omni-agent:worker`** (was `omni-agent:lauf`). The internal skills are now `omni-agent-runtime`, `omni-agent-task` and `omni-agent-results`.
- **Report files renamed:** `report.md`, `task.md`, `error.log`, `console.log`, `changes.patch` (were `bericht.md`, `auftrag.md`, `fehler.log`, `konsole.log`, `aenderungen.patch`). The directories under `~/.omni-agent` are now `runs` and `accounts`.
- **The code is English too.** Modules (`engine`, `providers`, `config`, `accounts`, `hooks`, `usage`), functions, variables and the `status.json` keys (`state`, `provider`, `model`, `turns`, ...). The accounts folder is not used any more; accounts live in `providers.d/account-<name>.json`. A static check (pyflakes) runs in CI next to the tests, on Python 3.9, 3.12 and 3.13.
- **Run states** are `running`, `done`, `failed` and `cancelled`; `wait` and `result` start with `[still running]`, `[done]`, `[failed]` or `[cancelled]`.
- **Review reports** use the headings `## Verdict` (`approve` or `needs-work`), `## Findings` with `[critical|high|medium|low]`, `Location:` and `Confidence:`. The agent answers in the language of the task.

## 1.2.0

- **Project mode for every provider.** The block for third-party providers is gone; `--project` and `--write` apply with DeepSeek, Kimi, Ollama and all others. The decision which data goes where is the user's. With opencode, the final answer now also becomes the report.
- **Usage and balance:** `omni-agent usage` and `/omni-agent:usage`. Codex (plan, usage per window, reset, credits, reset credits via `codex app-server`), DeepSeek, Kimi, OpenRouter and EUrouter (balance), Claude accounts as before.
- **Remote targets:** `omni-agent host add|list|remove|test|install|setup` and `--host NAME` for `run`, `status`, `result`, `cancel`, `wait`, `usage`, `doctor`. Runs over ssh, also over Tailscale. `/omni-agent:hosts`.
- **Python 3.9** is enough now (the version macOS ships).

## 1.1.1

Biggest change since the start: Omni-Agent now works on the model of the Codex plugin. **Breaking change:** The skills `run`, `review`, `status`, `doctor`, `setup` and `delegieren` became commands and the subagent. Calls such as `/omni-agent:run` stay the same, but `run` now starts through the subagent `omni-agent:worker`, and runs start detached.

New:

- **Subagent `omni-agent:worker`** (a thin forwarder). Claude can call it on its own, also in `/goal`; the main chat stays clean, and Claude Code reports the end.
- **Commands** instead of skills: `run`, `review`, `adversarial-review`, `status`, `result`, `cancel`, `accounts`, `doctor`, `setup`. Status, result, cancel, check and accounts run with no model in between.
- **Internal skills** for the runtime contract, writing a task and passing on results.
- **Detached runs:** `omni-agent run --background` / `--wait SEC`, `omni-agent wait`. Runs outlive the command that started them.
- **Sessions:** hooks assign runs to the Claude session; `status`, `result`, `cancel` and `resumable` refer to it first. `SessionEnd` stops still-running runs of the session.
- **Follow-up question "resume or start new?"** in `/omni-agent:run`.
- **Project mode:** `--project` (read-only) and `--write` for every provider; Codex then runs in the sandbox `read-only` or `workspace-write`.
- **Review contract:** fixed report skeleton (verdict, findings with severity, location, confidence, recommendation, next steps); adversarial stance modelled on Codex; with a clean working tree, branch against main branch.
- **Review gate (off):** `setup --review-gate on` checks new changes before a session ends.
- Status table as Markdown (`status --md`).
