# Omni-Agent: architecture

As of 28 Oct 2026. Basis: [`01-plugin-handbook.md`](01-plugin-handbook.md) and the verified facts in
[`research/providers-and-runners.md`](research/providers-and-runners.md). Implementation status: stages 1 to 8 are built (core, providers, `doctor`/`setup`, plugin, runners `opencode`, `codex`, `dsh`, extra LiteLLM). Only the runner `claude` with the provider `deepseek` and the plugin installation have been tested live; everything else follows the vendor docs and is covered by tests of the command construction. Stage 9 (publication) is still open.

## 1. The idea in one sentence

Omni-Agent is a **core program** that hands a task to a **runner** (agent CLI) with a **provider** (model source)
and returns a **report**. The Claude Code plugin is only the **shell** that makes the core convenient.

```
 Orchestrator (Claude Code, later Codex ...)
   │  Slash command / skill (text only)
   ▼
 omni-agent run task.md --provider deepseek
   │
   ├─ Provider  ← providers.json   (protocol, URL, key name, models)
   ├─ Runner    ← lib/runner/*     (claude · opencode · codex · dsh)
   ├─ Fit       ← protocol of the provider × protocols of the runner
   └─ optional  ← Extra LiteLLM    (translator for chat completions)
   ▼
 ~/.omni-agent/runs/<time>-<provider>/
   task.md · report.md · log.jsonl · error.log · status.json
```

Two layers, two points of exchange:

| Layer | Replaceable by | Question it answers |
|---|---|---|
| **Provider** | Entry in `providers.json` | "Whose model, where, with which key?" |
| **Runner** | Adapter class in `lib/runner/` | "Which agent CLI executes the task?" |

Claude Code is the **default runner**, but not one you are tied to.

## 2. Why a core program and not an MCP server

| Decision | Reasoning |
|---|---|
| `bin/omni-agent` as an ordinary command | Runs without the plugin, without Claude, under Codex, in the terminal. The plugin is then only a convenience |
| Background through the **Bash tool** | Claude starts the blocking command in the background and is woken when it ends. No daemon needed |
| Python 3, standard library only | JSON, process groups, time limits without installing packages. Bash fails at JSON and `stat -f` (macOS only). Target platforms: macOS, Linux, WSL |
| Keys from the environment, then `~/.omni-agent/env` | `userConfig` does not reach `bin/` (handbook, section 7) |

## 3. Providers (`providers.json`)

Each entry: `id`, `protocols` (`anthropic` / `openai-chat` / `openai-responses`), `base_url`, `key_envs`, `models`
(alias -> name; tiers `default`, `strong`, `small`), `region`, `note`. The values below were checked against the vendor pages on 2026-10-28, unless
"not documented" is stated.

| Provider | Protocol | Base URL | Key variable | Default model | Data location / note |
|---|---|---|---|---|---|
| **deepseek** | anthropic | `https://api.deepseek.com/anthropic` | `DEEPSEEK_API_KEY` | `deepseek-flash` (strong: `deepseek-v4-pro`) | **China**, training use intended. Search/fetch API chargeable from 2026-11-01 (0.75 $ / 1,000). A model name without the `claude` prefix and without a DeepSeek name gives 400 |
| **openrouter** | anthropic | `https://openrouter.ai/api` | `OPENROUTER_API_KEY` | freely selectable | Location not documented. Claude Code docs: only Anthropic is promised as a provider. `ANTHROPIC_API_KEY` must be empty. Web search not documented |
| **kimi** | anthropic | `https://api.moonshot.ai/anthropic` | `MOONSHOT_API_KEY` | `kimi-k3[1m]`, Haiku tier `kimi-k2.7-code` | Location and prices not documented. Set all tier variables, otherwise background tasks fail silently |
| **ollama** | anthropic | `http://localhost:11434` | none (`ollama` as placeholder) | e.g. `qwen3.5` | **local, data stays on the machine.** Model needs tools and >= 64k context. No `tool_choice`, no web search. Minimum version not documented |
| **eurouter** | openai-chat (+ responses) | `https://api.eurouter.ai/api/v1` | `EUROUTER_API_KEY` | catalog | Processing in the EU according to the provider. **No Anthropic path documented** → runner `opencode`/`codex` or extra LiteLLM |
| **claude-account** | anthropic | default | `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY` | `sonnet`, `haiku`, `opus` | A different account has its own quotas. **See section 8 (conditions)** |
| **nvidia** | openai-chat | `https://integrate.api.nvidia.com/v1` | `NVIDIA_API_KEY` | `z-ai/glm-5.3-flash` and others | Chat completions only. Free tier and location not documented. Runner `opencode` or extra LiteLLM |
| *zai*, *minimax* | anthropic | `https://api.z.ai/api/anthropic`, `https://api.minimax.io/anthropic` | `ZAI_API_KEY`, `MINIMAX_API_KEY` | `glm-5.3`, `MiniMax-M3.1-Flash[1m]` | later, prices and location not documented |

Custom providers go into `~/.omni-agent/providers.d/*.json` (same schema), without changing the repo.

## 4. Runners and fit

| Runner | Command | Speaks | Permission control | Output | Status |
|---|---|---|---|---|---|
| **claude** | `claude -p` | anthropic | `--allowed-tools`, `dontAsk` (fine-grained) | `stream-json`, exit 0/non-0 | **Default**, best documented |
| **opencode** | `opencode run` | openai-chat, openai-responses, anthropic | `permission` config, `--auto` | `--format json` | second choice. Two version lines (V1/V2), exit codes not documented, recent security incidents: pin the version |
| **codex** | `codex exec` | **only** openai-responses | sandbox modes, no per-tool allowlist | `--json`, `-o` | second world (OpenAI). `wire_api="chat"` removed |
| **dsh** | `dsh --profile headless` | OpenAI-compatible (headless config not documented) | not documented | plain text | **experimental**, developer preview with announced breaking changes |
| *agy*, Crush, Goose, Aider | - | - | - | - | later. `agy`: soft deny returns exit 0, third-party providers not documented |

**Fit rule:** A run needs a runner that speaks the protocol of the provider.

| Provider | claude | opencode | codex |
|---|---|---|---|
| deepseek, openrouter, kimi, ollama, claude-account | yes | yes | only if Responses |
| eurouter | only with LiteLLM | **yes** | yes (Responses compatibility not verified) |
| nvidia | only with LiteLLM | **yes** | no |

Without `--runner`, `omni-agent run` picks the first **installed** runner in the order claude → opencode → codex
that fits. If none fits, it says clearly why and what is missing (install a runner or extra LiteLLM). `omni-agent doctor`
shows the same matrix for your own machine.

## 5. The contract between core and runner

**Input to the adapter:** task file, run folder, provider, model, neutral tool list, limits.

**Neutral tools:** `read`, `write`, `web_search`, `web_fetch`, `shell`.
Default: **without** `shell`. Each adapter translates:

| Neutral | claude | opencode | codex |
|---|---|---|---|
| read | `Read Glob Grep` | `permission.read/glob/grep` | sandbox readable |
| write | `Write Edit` | `permission.edit` | `workspace-write` |
| web_search, web_fetch | `WebSearch`, `WebFetch` | `websearch`, `webfetch` | not documented |
| shell | `Bash` | `permission.bash` | sandbox |

What a runner cannot do is named by `doctor`, and the run **refuses** instead of silently doing less.

**Output in the run folder:**

| File | Content |
|---|---|
| `report.md` | Result. **Present = done.** This is the only binding proof of completion |
| `log.jsonl` | Raw output of the runner |
| `error.log` | stderr |
| `status.json` | `state` (`running`/`done`/`failed`/`cancelled`), `kind`, `start`, `end`, `exitcode`, `runner`, `provider`, `model`, `turns`, `task`, `session`, `claude_session`, `run_dir`, `pid` |

The exit code of the runner is only a secondary signal: it is documented differently per runner, and for `agy` 0 also means "refused".

**Exit code of `omni-agent`:** 0 done · 1 error in the run · 2 configuration (key or runner missing) · 3 endpoint unreachable · 124 time limit.

**Task frame** that the core prepends to every task (from the local test: without a limit 232 s and 33 tool calls, with a limit 16 s):

- Write the result to `report.md` in the working folder, sources with URL.
- At most *N* tool calls (default 12, adjustable).
- Mark claims without evidence as "not documented".
- Read or write nothing outside the working folder.

## 6. Commands

| Command | Purpose |
|---|---|
| `omni-agent setup` | Guide: choose a provider, create and open the file `~/.omni-agent/env`, check runners, put the core on the PATH (`~/.local/bin`) |
| `omni-agent doctor` | What is there, what is missing: runners, keys (only whether set, never the value), reachability, fit matrix |
| `omni-agent run <task.md> [--provider] [--model] [--runner] [--tools] [--max-turns] [--timeout] [--dir]` | Execute a task, blocking, live progress |
| `omni-agent status [run]` | Runs, state, report |
| `omni-agent providers`, `omni-agent runners` | Lists |
| `omni-agent extras litellm install | start | stop` | optional translator, section 7 |

**Plugin shell (since 1.1.1):** Commands in `commands/` (`run`, `review`, `adversarial-review`, `status`, `result`, `cancel`, `accounts`, `usage`, `hosts`, `doctor`, `setup`), the
subagent `agents/worker.md` (`omni-agent:worker`, model Sonnet, tool Bash only, thin forwarder), three internal skills and three hooks.
`:run` calls the subagent through the Agent tool (never through Skill, that would call the command again); Claude can also call the subagent
itself, the description in the agent file is the trigger. The subagent starts exactly one run with `omni-agent run --wait 540`
(detached process, waits at most 540 s so that the Bash limit of 10 minutes is never hit), on `[still running]` keeps waiting with
`omni-agent wait` and returns the output unchanged. Hooks: `SessionStart` writes `OMNI_AGENT_SESSION` into `CLAUDE_ENV_FILE`
(so that Bash commands of the subagents also know the session), `SessionEnd` ends running runs of the session (not on `/clear`), `Stop` reports
running runs and, if switched on, executes the review gate (`lib/omni_agent/hooks.py`).

## 7. Extra: LiteLLM (optional)

Only for OpenAI-compatible providers, when the desired runner does not speak them itself (for example `claude` against EUrouter or Nvidia).

| Rule | Reason |
|---|---|
| Never mandatory, only `omni-agent extras litellm install` | Two supply-chain incidents in seven months |
| Version **pinned**, hash lock, own virtual environment under `~/.omni-agent/extras/litellm` | `litellm==1.107.0` was compromised on 2026-10-21 (PyPI **and** official Docker images), the vendor recommends pin 1.106.2. The locally used 1.106.3 predates it |
| Only 127.0.0.1, its own access key, **only one** provider key in the environment of the proxy | Limit the damage |
| Read the vendor's incident page before every pin change | The malicious code ran at Python startup, an `import` was not needed |
| Alternative `claude-code-router` not chosen | Large Node supply chain, security status not verified |

Always preferred: **another runner instead of a translator** (EUrouter and Nvidia with `opencode`).

## 8. Security and conditions

| Topic | Rule |
|---|---|
| Keys | Never in the repo, never in the chat, never in the log. File `~/.omni-agent/env` with mode 600 (the core refuses otherwise). The core hands the runner **only the one** key it needs |
| Environment | `env -i` plus the bare minimum. For `claude`: `ANTHROPIC_API_KEY` empty, `--setting-sources project`, `--strict-mcp-config`, empty run folder (since 0.4.0 the session is stored so that `--resume` works). Without this, `-p` executes hooks and MCP of the working folder |
| All model variables | Set `ANTHROPIC_MODEL`, Opus/Sonnet/Haiku, `CLAUDE_CODE_SUBAGENT_MODEL`, otherwise background tiers fail silently |
| Default without shell | `shell` only explicitly (`--tools +shell`) with a warning. Web search can deliver prompt injection; an agent with a shell and third-party web content is an invitation |
| Data protection | The README names the data location per provider. **DeepSeek: China.** No participant data or internal material in tasks. For personal data: ollama (local) or eurouter |
| **claude-account** | Anthropic allows `claude setup-token` for scripts, but refers developers of products to API keys, and forbids collecting, storing or passing on subscription credentials. Whether an unattended run with your **own** subscription token is "ordinary use" is **not documented**. Therefore: Omni-Agent **never stores this token** (only the user's environment variable), starts the unmodified `claude` binary, recommends the API key and warns in the README |
| Time limit | The process group is ended on expiry (exit 124) |
| Before publication | Secret scan of the working tree **and** the Git history, rotate the test key |

## 9. Migration from the current wrapper

| Today | New |
|---|---|
| `fbs/agent-love/tools/fremdagent` (Bash) | `bin/omni-agent` + `lib/` (Python) |
| `~/.fremdagent/` | `~/.omni-agent/` (runs are taken over, keys only moved with your OK) |
| `status.json` contract, `fortschritt.py` | stay, move into the core |
| LiteLLM venv in `~/.fremdagent/litellm-venv` | `~/.omni-agent/extras/litellm` (newly pinned) |
| Name `fremdagent` | `omni-agent`. For old users an alias script `fremdagent` |

## 10. Order (order and gates only, no time estimates)

| Stage | Content | Gate |
|---|---|---|
| 1 | Core + runner `claude` + provider `deepseek`: port of the current wrapper | Run with report, `status.json` is correct |
| 2 | `providers.json` complete, `doctor`, `setup`, fit matrix | `doctor` shows the matrix, a missing key is reported cleanly |
| 3 | Plugin shell: manifests, agent, commands, internal skills, hooks | `claude plugin validate --strict` green, `/omni-agent:run` starts a run in `claude --plugin-dir` |
| 4 | `INSTALL.md`, `AGENTS.md`, README with data-protection table | A fresh Claude session installs and verifies using only `INSTALL.md` |
| 5 | Runner `opencode` | Run against EUrouter or Nvidia without a proxy |
| 6 | Runner `codex` | Run against a Responses endpoint |
| 7 | Extra LiteLLM | `claude` against Nvidia through the pinned proxy |
| 8 | Runner `dsh` (experimental) | only once a release without `rc`/`alpha` exists, otherwise only with a warning label |
| 9 | Secret scan, key rotation, **publication after your yes** | Scan clean |

Realistic for tomorrow: stages 1 to 4 with DeepSeek (key available). Further providers are registered,
but **only tested live where you have a key**; everything else carries the note "per vendor docs, not tested" in the README.

## 11. Decisions (made)

1. **Key route:** environment plus file `~/.omni-agent/env` instead of MCP.
2. **Core:** Python 3 (macOS, Linux, WSL; native Windows later).
3. **Name:** `omni-agent` (the older `omniagent` is taken on npm by another project).
4. **GitHub account:** `alexodexo`.
5. **Claude account** is a provider, with the warning from section 8.
6. **Default provider:** none, the user chooses on every run.
