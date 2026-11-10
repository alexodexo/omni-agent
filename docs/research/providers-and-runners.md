# Omni-Agent: model providers and agent CLIs (facts as of 2026-10-28)

Rules of this file: Primary sources only (vendor docs, vendor repos). Every statement carries a URL and a retrieval date. **28 Oct** = fetched live today (2026-10-28). **25 Oct (local)** = local raw copy (not in the repo), fetched earlier from the vendor URL, not re-fetched today. **not documented** = could not be confirmed from a primary source. No keys entered, nothing installed, no accounts created.

Abbreviations: CC = Claude Code. `AUTH_TOKEN` = `ANTHROPIC_AUTH_TOKEN` (Bearer header). `API_KEY` = `ANTHROPIC_API_KEY` (x-api-key header).

---

## Up front: one thing applies to all providers in part A

Auth precedence in CC (https://code.claude.com/docs/en/authentication, 28 Oct): cloud provider variables > `ANTHROPIC_AUTH_TOKEN` > `ANTHROPIC_API_KEY` > `apiKeyHelper` > `CLAUDE_CODE_OAUTH_TOKEN` > Anthropic profiles > subscription login. In `-p` mode an existing `ANTHROPIC_API_KEY` is **always** used (in interactive mode only after confirmation). Consequence for Omni-Agent: when starting against a third-party endpoint, set only `AUTH_TOKEN` and leave `API_KEY` empty or unset (OpenRouter explicitly requires `ANTHROPIC_API_KEY=""`; Kimi: "remove it to avoid conflicts"). The existing wrapper with `env -i` meets this.

---

## PART A - Model providers for the runner "claude"

### A1. Overview

| Provider | Anthropic endpoint (`ANTHROPIC_BASE_URL`) | Auth variable | Default models (per provider docs) | Source (retrieved) |
|---|---|---|---|---|
| **DeepSeek** | `https://api.deepseek.com/anthropic` | `AUTH_TOKEN` | `deepseek-flash` (V4.1-Flash-1017), `deepseek-v4-pro` (V4-Pro-0813); both 1M context, 384K output. The docs set `ANTHROPIC_MODEL=deepseek-flash[1m]`, Opus/Sonnet likewise, Haiku and `CLAUDE_CODE_SUBAGENT_MODEL=deepseek-flash`, plus `CLAUDE_CODE_EFFORT_LEVEL=max`, `CLAUDE_CODE_AUTO_COMPACT_WINDOW=786432` | https://api-docs.deepseek.com/quick_start/pricing (28 Oct), https://api-docs.deepseek.com/guides/anthropic_api (28 Oct), Claude Code page local 25 Oct from https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code |
| **OpenRouter** | `https://openrouter.ai/api` (full URL with scheme) | `AUTH_TOKEN` = OpenRouter key; set `ANTHROPIC_API_KEY` to an **empty string** | Any OpenRouter models; examples in the docs use `~anthropic/claude-*-latest` aliases, `[1m]` for 1M context. Variables: `ANTHROPIC_DEFAULT_{FABLE,OPUS,SONNET,HAIKU}_MODEL`, `CLAUDE_CODE_SUBAGENT_MODEL`, optional `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1` | https://openrouter.ai/docs/guides/coding-agents/claude-code-integration (28 Oct) |
| **Kimi / Moonshot** | `https://api.moonshot.ai/anthropic` | `AUTH_TOKEN` | `kimi-k3[1m]` (main/Opus/Sonnet/Fable/subagent), `kimi-k2.7-code` (Haiku tier, thinking enforced), optional `kimi-k2.6` | https://platform.kimi.ai/docs/guide/claude-code-kimi.md (28 Oct) |
| **Ollama (local)** | `http://localhost:11434` | `AUTH_TOKEN=ollama` (placeholder), `API_KEY=""` | Doc example local `qwen3.5`; model must support tools, context >= 64k. Can also be started with `ollama launch claude` | https://docs.ollama.com/integrations/claude-code (28 Oct) |
| **Ollama Cloud (direct)** | `https://ollama.com` | `AUTH_TOKEN=$OLLAMA_API_KEY`, `API_KEY=""` | Examples: `glm-5.3-flash`, `gemma4:cloud`, `kimi-k2.7-code:cloud` | same page (28 Oct) |
| **EUrouter** | **no Anthropic endpoint documented.** Base `https://api.eurouter.ai/api/v1`, OpenAI style (`/chat/completions`, `/completions`, `/responses`) | Bearer key | Model catalog separate (Claude and Mistral models listed) | https://www.eurouter.ai/docs , https://www.eurouter.ai/llms.txt , https://www.eurouter.ai/api/openapi.json (all 28 Oct) |
| **Claude, other account** | Default (`api.anthropic.com`), no base URL needed | `ANTHROPIC_API_KEY` (Console key) **or** `CLAUDE_CODE_OAUTH_TOKEN` (subscription, via `claude setup-token`) | `sonnet`/`opus`/`haiku`/`fable` or full names via `--model` | https://code.claude.com/docs/en/authentication (28 Oct) |
| **Nvidia NIM** | **no Anthropic endpoint documented.** Base `https://integrate.api.nvidia.com`, `POST /v1/chat/completions` | NVIDIA key (Bearer) | Local model list: `sources/nvidia-model-list-2026-10-25.txt` (model names there not re-checked against the Nvidia page) | https://docs.api.nvidia.com/nim/reference/llm-apis (28 Oct) |
| **Z.ai GLM** | `https://api.z.ai/api/anthropic` | `AUTH_TOKEN` | Default mapping: `GLM-5.3-Flash` for Opus/Sonnet/Haiku; manual example: `glm-5.3[1m]` (Sonnet/Opus), `glm-5.3-flash[1m]` (Haiku); `API_TIMEOUT_MS=3000000`, `CLAUDE_CODE_AUTO_COMPACT_WINDOW=1000000` | https://docs.z.ai/devpack/tool/claude (28 Oct) |
| **MiniMax** | `https://api.minimax.io/anthropic` (China: `api.minimaxi.com`, per search-result summary, page itself not opened) | `AUTH_TOKEN` = "Subscription Key" | `MiniMax-M3.1-Flash[1m]` for main/Opus/Sonnet/Haiku; thinking always on; `CLAUDE_CODE_AUTO_COMPACT_WINDOW=524288` | https://platform.minimax.io/docs/token-plan/claude-code.md (28 Oct). Other MiniMax pages name different model names (M3, M3[1m], M3.1-Flash-Preview): version drift, check the respective plan page each time |

### A2. Tool calls, WebSearch/WebFetch, prices, data location, pitfalls

| Provider | Tools / WebSearch / WebFetch | Prices (rough) | Data location / GDPR | Known pitfalls |
|---|---|---|---|---|
| **DeepSeek** | Tools: `tool_choice` none/auto/any/tool supported, `disable_parallel_tool_use` ignored. Images (base64/url/file) yes. `web_search` blocks (`server_tool_use`, `web_search_tool_result`) listed as supported; search/fetch API: 0.75 $ per 1,000 successful requests, **currently free via harness, Claude Code or Codex, billing from 2026-11-01 00:00 Beijing**. Own practical test (25 Oct, local `knowledge.md`): web search, load page, write file work | flash: 0.15/0.30 $ input (miss, off-peak/peak), 0.60/1.20 $ output per 1M; v4-pro: 0.66/1.32 $ and 1.98/3.96 $. Off-peak = half price. Peak: 01-04 and 06-10 UTC, Mon-Fri excluding Chinese holidays | Privacy policy (dated 2026-02-10, local 25 Oct from https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html): provider based in China, storage in the PRC, use for model training intended. Critical for personal data from the EU, legal assessment **not documented** | Model name without the prefix `claude` and not a real DeepSeek name: HTTP 400. `claude-opus*` maps to v4-pro, `claude-sonnet*`/`claude-haiku*`/other `claude*` to flash. Ignored: `cache_control`, `mcp_servers`, `top_k`; `redacted_thinking`, `document` blocks not supported. Without a call limit in the task the agent runs away (local test: 33 tool calls, 232 s) |
| **OpenRouter** | Native tool use and thinking blocks are passed through. Web search: **not mentioned** on the page | Billing via OpenRouter credit; model prices per model, **not retrieved** | Docs: source-code prompts are only logged if you enable prompt logging. Anything further on location/GDPR **not documented** | Docs: compatibility only promised with the Anthropic 1P provider, recommended: Anthropic 1P as top priority; CC "may not work correctly" with others. Without `[1m]` in the name CC assumes 200k context. After an earlier Anthropic login run `/logout` |
| **Kimi** | Messages API described as "Anthropic-compatible". WebSearch **not documented** | no prices on the page; **not documented** | **not documented** | `env` in `~/.claude/settings.json` overrides shell variables. An unset tier variable makes background/subagent tasks fail silently. `kimi-k2.7-code` without thinking: 400 "only type=enabled is allowed". `AUTO_COMPACT_WINDOW` too large: context error. npm install needs Node 22+ (page) |
| **Ollama local** | Anthropic interface `/v1/messages`: streaming, system prompts, tools incl. tool results, vision (base64 only), thinking (`budget_tokens` accepted, not enforced). **Not supported:** `tool_choice`, hosted web search, deferred tools, `count_tokens`, prompt caching, batches, citations, PDF `document` blocks (https://docs.ollama.com/api/anthropic-compatibility, 28 Oct) | free locally (hardware); cloud prices **not documented** | local: data does not leave the machine (follows from the setup, not quoted from the docs). Cloud: **not documented** | **Minimum Ollama version for the Anthropic API: not documented** (neither page names one). Model needs tool support and >= 64k context. CC asks for permissions by default; direct connection to the cloud does not fully support hosted WebSearch |
| **EUrouter** | Chat completions and Responses format; Anthropic format not documented | Prices in the catalog, **not retrieved** | Page: "All inference traffic is processed inside the EU", "GDPR-aligned by design", configurable routing and retention controls (marketing statement, details **not documented**) | A translator becomes necessary for CC (see A3). The OpenAPI file (278,743 characters) was only read up to the first 100,000 characters: no `/messages` path there; path `/api/v1/chat/completions` present. A full exclusion of a Messages path is therefore **not documented**, but `llms.txt` lists 16 API reference pages without Messages |
| **Claude other account** | full tool and web functions (first party) | Subscription or API billing, prices **not retrieved** | **not documented** (not checked) | `--bare` reads **no** `CLAUDE_CODE_OAUTH_TOKEN` and no Keychain login; there `ANTHROPIC_API_KEY` or `apiKeyHelper` is needed. A token from `setup-token` can only do model requests, no Remote Control sessions, no claude.ai connectors |
| **Nvidia NIM** | only OpenAI format (chat completions) documented | Free tier/limits/terms of use **not documented** (page says nothing about it) | **not documented** | Translator needed (LiteLLM). Local practice: `drop_params: true`, otherwise errors on unknown Anthropic fields |
| **Z.ai GLM** | Tools/WebSearch/MCP: page says nothing, **not documented** | Page names no prices (refers to coding plan pages), **not documented** | **not documented** | Docs verified with CC 2.0.14 (outdated against current 2.1.312). Setup script macOS/Linux only; coding helper `npx @z_ai/coding-helper` |
| **MiniMax** | **not documented** | **not documented** | **not documented** | `ANTHROPIC_AUTH_TOKEN`/`BASE_URL` in the shell override `settings.json`. Thinking cannot be switched off. `xhigh` is sent as `high` by some CC versions |

### A3. LiteLLM as an OPTIONAL extra

| Point | Finding | Source (retrieved) |
|---|---|---|
| Current version | PyPI: `litellm` **1.106.5** (published 2026-10-27 19:44 UTC, Python `>=3.10,<3.15`); after that only `1.109.0.dev1` (28 Oct). 1.104.8, 1.103.10, 1.105.6 were also republished on 27 Oct (backports). A local note from 25 Oct named 1.106.3 | https://pypi.org/pypi/litellm/json (28 Oct), local `sources/litellm-1.106.3-pypi-2026-10-25.json` |
| **Security incident October 2026** | `litellm==1.107.0` compromised. PyPI: all seven wheels live 11:39:51 to 13:23 UTC on 2026-10-21. **Docker also affected:** Docker Hub tags `v1.107.0`, `latest`, `main-latest`, `main-stable` pointed to a compromised image from 11:46:56 to 14:20 UTC; GHCR (`litellm`, `litellm-database`, `litellm-non_root`) similar until 13:51 UTC. Malicious code: credential stealer plus a loader for remote code execution; indicators `cook.pth`, `cook.py`, `sitecustomize.py`, daemon with `/tmp/remote_code_loader.lock`; runs at Python startup, an `import litellm` is not needed. The GitHub tag `v1.107.0` does not contain the malicious files. Vendor: all earlier versions safe, pin to `1.106.2`. Status "contained", maintainer access revoked, investigation ongoing; the update of 23 Oct corrected earlier assumptions | https://docs.litellm.ai/blog/security-incident-oct-21-2026 (28 Oct) |
| **Security incident March 2026** | `1.82.7` and `1.82.8` on PyPI on 2026-03-24 (about 10:39 UTC, about 40 minutes until quarantine). Stole environment variables, SSH/cloud keys, K8s tokens, DB passwords; 1.82.8 with a `.pth` file. The official proxy Docker image and GitHub source installation were not affected at the time. Clean: 1.83.0 through a new CI pipeline | https://docs.litellm.ai/blog/security-update-march-2026 (28 Oct) |
| Assessment | Two supply-chain incidents in seven months, in the second **also the official Docker images**. A CVE/GitHub advisory for the October incident had, according to secondary sources (Datadog, Microsoft), not been assigned at press time; OSV entry MAL-2026-2144 per search result. Whether 1.106.4 and 1.106.5 (built after the incident) are explicitly confirmed as verified by the vendor: **not documented** | Secondary: https://www.microsoft.com/en-us/security/blog/2026/10/23/inside-the-litellm-1-107-0-supply-chain-compromise-credential-theft-through-python-startup-hooks/ , https://securitylabs.datadoghq.com/articles/litellm-compromised-pypi-docker/ (only seen via search result, not opened) |
| Minimal configuration `/v1/messages` | `config.yaml` with `model_list` (`model_name` = name the client sends; `litellm_params.model` = target, `api_key: os.environ/KEY`), start `litellm --config <path>`, Anthropic call `POST /v1/messages` with headers `x-api-key`, `anthropic-version: 2023-06-01`. Vendor: "follows the Anthropic messages specification". Restrictions per the page: `max_tokens` > 1; `thinking.budget_tokens` at least 1024 and < `max_tokens` | https://docs.litellm.ai/docs/anthropic_unified (28 Oct) |
| Claude Code against LiteLLM | The vendor page does **not** cover Claude Code. Working practice locally: `ANTHROPIC_BASE_URL=http://127.0.0.1:4000`, `AUTH_TOKEN` = proxy master key, all model variables set to one `model_name`; `litellm_settings: {telemetry: false, drop_params: true}`; liveness `GET /health/liveliness` | local `tools/fremdagent`, `tools/litellm/config.yaml` (own experience, not a vendor source) |
| Codex against LiteLLM | Current Codex versions support **only** Responses API endpoints (`wire_api="chat"` removed). Whether LiteLLM delivers `/v1/responses` for Nvidia/others: **not documented** | https://learn.chatgpt.com/docs/models (local 25 Oct) |

**Recommendation on LiteLLM (assessment, not a source):** Only as an opt-in, never as a mandatory dependency. If used anyway: pin the version (e.g. 1.106.2 per the vendor, or a later one you checked yourself), hash pinning, Docker only by digest and built yourself or from the GitHub tag, in its own virtual environment or container with **only one** provider key in the environment, no access to SSH/cloud keys, restricted outbound traffic. Read the incident page before every update.

### A4. Alternatives to LiteLLM

| Option | Finding | Assessment |
|---|---|---|
| **claude-code-router** (musistudio) | Local gateway `127.0.0.1:3456`, UI `:3458`; protocols: OpenAI Chat/Responses, Anthropic Messages, Gemini; routing, retries, fallbacks; MIT; v3.1.3 (npm, 28 Oct); 37.9k stars; Node 22+; installation desktop app, `npm i -g @musistudio/claude-code-router`, Docker. Configuration schema not documented on the repo page; Security tab shows "1" with no content; 944 open issues (https://github.com/musistudio/claude-code-router, 28 Oct) | Usable alternative, but a Node package with a large supply chain and a door for the same attack class; security status **not verified** |
| **Native Anthropic endpoints of the providers** | DeepSeek, Kimi, Z.ai, MiniMax, OpenRouter, Ollama deliver Anthropic format themselves (table A1) | **Prefer:** no translator, smaller attack surface |
| Other translator proxies | not examined | **not documented** |
| Another runner instead of a proxy | OpenCode, Codex, dsh speak OpenAI format or Responses directly (part B) | For pure OpenAI providers (EUrouter, Nvidia) often the cleaner route than "Claude Code + translator" |

### A5. Terms of use: subscription token in automated runs

| Statement | Source (retrieved 28 Oct 2026) |
|---|---|
| `claude setup-token` creates a one-year OAuth token "for CI pipelines, scripts, or other environments where interactive browser login isn't available". It applies to Pro/Max/Team/Enterprise, can only do model requests. Set as `CLAUDE_CODE_OAUTH_TOKEN`, rank 5 in the auth order | https://code.claude.com/docs/en/authentication |
| OAuth login is "intended exclusively for purchasers" of the subscription plans and "designed to support ordinary use of Claude Code and other native Anthropic applications" | https://code.claude.com/docs/en/legal-and-compliance |
| Developers who build products or services (explicitly incl. the Agent SDK) should use API key authentication. Third-party developers may not offer claude.ai login and may not route requests through subscription credentials for their users; credentials and session tokens may not be collected, stored or brokered | same page |
| Announced Pro/Max limits assume "ordinary, individual usage of Claude Code and the Agent SDK"; Anthropic may enforce without notice | same page |
| Explicitly allowed: customer configures their own API keys for their own users, provided billing stays with the key holder; the end user may sign in with their own subscription in the **unmodified** CC binary | same page |
| Anyone shipping CC in products/hosted environments: Commercial Terms, binary unmodified, no auth method removed, do not pay for or resell to end users | same page |

**Interpretation for Omni-Agent (assessment, not legal advice):** That `setup-token` is described for scripts in the auth docs while the legal page refers developers of "products or services" to API keys is an open point of tension. Whether an unattended background run with the **own** subscription token on the **own** machine counts as "ordinary, individual usage" is **not documented**. Safely on the right side: Omni-Agent **never** collects, stores or brokers tokens (the user sets `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY` in their own environment), starts the unmodified `claude` binary, and warns in the README about the subscription-token case. Asking Anthropic Sales would be the only reliable way.

---

## PART B - Interchangeable agent CLIs ("runners")

### B1. Claude Code (`claude -p`)

| Point | Finding | Source (retrieved 28 Oct 2026) |
|---|---|---|
| Version | npm `@anthropic-ai/claude-code` **2.1.312** (2026-10-27) | https://registry.npmjs.org/@anthropic-ai/claude-code |
| Headless | `claude -p "..."`; input also via pipe (stdin max. 10 MB); `--input-format text|stream-json` | https://code.claude.com/docs/en/headless , https://code.claude.com/docs/en/cli-reference |
| Model/provider | Only via environment variables (part A) or `--model`, `--settings <file|json>`, `settings.json` with an `env` block. **Caution:** `env` in `settings.json` overrides shell variables (Kimi/MiniMax page). `--fallback-model` available | cli-reference; Kimi page |
| Permissions | `--allowed-tools` (rules without prompt, syntax `Bash(git diff *)`), `--tools` (restrict availability, `""` = none), `--disallowed-tools`, `--permission-mode` = `default`/`manual`, `acceptEdits`, `plan`, `auto`, `dontAsk`, `bypassPermissions`; `--permission-prompts none` (since v2.1.259). `dontAsk` denies everything that would otherwise prompt. **Since v2.1.302, `-p` without a set mode starts in manual mode** (not a grant) | cli-reference, headless |
| Isolation | `--setting-sources project` (or `user,project,local`), `--strict-mcp-config` (+ `--mcp-config`), `--no-session-persistence`, `--bare` (recommendation of the docs for scripts, will become the default; loads nothing from hooks/skills/MCP/CLAUDE.md, reads **no** OAuth/Keychain). Without `--bare`, `-p` executes hooks from `.claude/settings.json` and MCP servers from `.mcp.json` of the working folder, also in folders never confirmed, and shows no trust dialog | headless |
| Limits | `--max-turns` (error when reached), `--max-budget-usd` (estimate, may be exceeded), `--json-schema` (field `structured_output`) | cli-reference |
| Output | `text`, `json` (with `result`, `session_id`, `total_cost_usd`), `stream-json` (line by line, with `--verbose`; `--include-partial-messages` for deltas). Last line = `result` message; first = `system/init` (model, tools, MCP status, `plugin_errors`, `mcp_server_errors`); `system/api_retry` with `error_status`; `permission_denied` messages and `permission_denials` in the result | headless |
| Done/error | Exit 0 = success, non-0 = failure; errors in the run (e.g. missing auth) appear as a result on stdout. SIGTERM → exit **143**, no result for the running turn. The exact field names of the `result` object (e.g. `is_error`, `subtype`) are **not** on the retrieved page → **not documented** | headless |
| Working folder | Inherits the current directory; `--add-dir` for more. If the folder is deleted mid-run, the session continues and reports a warning in the stream | headless |
| Background work | After the turn, the run waits for background commands/subagents up to 10 minutes of idle time (`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS`) | headless |
| Installation | `curl -fsSL https://claude.ai/install.sh | bash`, PowerShell/CMD installer, `brew install --cask claude-code`, npm `@anthropic-ai/claude-code` | local 25 Oct https://code.claude.com/docs/en/setup |
| Windows | Yes: Windows 10 1809+, Server 2019+; Bash, Zsh, PowerShell or CMD. Git for Windows recommended (otherwise PowerShell as shell tool); DeepSeek/Z.ai pages name Git for Windows as a prerequisite | setup (local 25 Oct) |
| Security | 35 published GitHub advisories (count local 25 Oct); content not evaluated | local `sources/claude-code/github-security-advisories-2026-10-25.json` |

### B2. OpenAI Codex CLI (`codex exec`)

| Point | Finding | Source |
|---|---|---|
| Version | npm `@openai/codex` **0.165.0** (28 Oct), Apache-2.0, Rust (local note) | https://registry.npmjs.org/@openai/codex (28 Oct) |
| Headless | `codex exec "<prompt>"` (short form `codex e`); progress on stderr, **only the last agent message on stdout**; piped stdin is taken as additional context; subcommands `resume`, `fork` | https://learn.chatgpt.com/docs/non-interactive-mode.md (local 25 Oct), https://learn.chatgpt.com/docs/developer-commands.md (28 Oct) |
| Sandbox/permissions | Default in `exec`: **read-only**. `--sandbox workspace-write` (edit in the folder), `--sandbox danger-full-access` (only in an isolated environment). `--full-auto` **no longer supported**; replacement `--approve-for-me` (per local docs) or `--sandbox workspace-write`. Approval values per the sandbox page: `on-request`, `never` (`untrusted` removed). `--add-dir` instead of full access. `--ignore-user-config`, `--ignore-rules`. **No per-tool allowlist** like CC; control via sandbox mode and execpolicy `.rules` | non-interactive-mode (local), https://learn.chatgpt.com/docs/sandboxing.md (28 Oct). The `exec` flag table is rendered by a component on the page and could not be retrieved; `--approve-for-me` only appeared in the local copy |
| Output | `--json`: JSONL events `thread.started`, `turn.started`, `turn.completed` (with `usage`), `turn.failed`, `item.*`, `error`. `-o/--output-last-message <file>` writes the final message to a file. `--output-schema <file>` enforces a JSON schema | non-interactive-mode (local 25 Oct) |
| Done/error | Event `turn.completed` or `turn.failed`; `exec` aborts with an error if an MCP server with `required = true` does not start. **Exit codes: not documented** | as above |
| Provider/key | Default: stored login or `CODEX_API_KEY` (set only for the one call, not job-wide). Custom providers in `config.toml` (`$CODEX_HOME`, default `~/.codex`): `[model_providers.<id>]` with `name`, `base_url`, `env_key`, `http_headers`, `env_http_headers`, `auth{command...}`; selection `model_provider = "<id>"`, override with `-c key=value`. **Custom providers must speak the Responses API; `wire_api = "chat"` and pure chat-completions endpoints are no longer supported.** Ollama example from the docs: `base_url = "http://localhost:11434/v1"` without `env_key` | https://learn.chatgpt.com/docs/config-file/config-advanced.md (28 Oct), models (local 25 Oct), auth (local 25 Oct) |
| Working folder | Current directory; `-C/--cd` (flag only indirectly confirmed, `resume` shows `-C`); `--worktree` creates a managed Git worktree. `--skip-git-repo-check`: **not documented** on the page | developer-commands (28 Oct) |
| Installation | `curl -fsSL https://chatgpt.com/codex/install.sh | sh`, Windows `irm https://chatgpt.com/codex/install.ps1 | iex`, npm `@openai/codex` | cli (local 25 Oct) |
| Windows | Yes: native Windows sandbox in PowerShell, WSL2 uses the Linux sandbox | sandboxing (28 Oct) |
| Security | 3 CVEs (local NVD copies: CVE-2025-61260, CVE-2026-19591, CVE-2026-19592); not evaluated. Note in the docs: do not set `OPENAI_API_KEY`/`CODEX_API_KEY` as job environment when repo code runs | auth/non-interactive (local) |

### B3. OpenCode (`opencode run`)

| Point | Finding | Source |
|---|---|---|
| Repo/version | `anomalyco/opencode` (sst/opencode redirects there), MIT, about 221k stars. **Two lines:** V1 npm `opencode-ai` **1.19.5** (28 Oct), V2 npm `@opencode/cli` **2.1.4** (25 Oct). `brew install opencode` = V2, `brew install anomalyco/tap/opencode` = V1; installer script and npm = V1 | https://github.com/anomalyco/opencode , npm (28 Oct), https://opencode.ai/docs/ (28 Oct) |
| Headless | `opencode run "<prompt>"`; flags: `--model/-m provider/model`, `--agent`, `--file/-f`, `--format default|json` (raw JSON events), `--dir`, `--continue/-c`, `--session/-s`, `--fork`, `--attach <url>` (running `opencode serve`), `--variant`, `--thinking`, `--auto`, `--port`, `--title` | https://opencode.ai/docs/cli/ (28 Oct) |
| Permissions | Config key `permission` with `allow`/`ask`/`deny` per tool (`read`, `edit`, `bash`, `webfetch`, `websearch`, `task`, `external_directory`, ...) and glob patterns (last matching rule wins); `"permission": "allow"` for everything. Default mostly `allow`, `external_directory` and `doom_loop` `ask`, reading `.env` `ask`. Non-interactive: `--auto` (everything except explicit `deny`), `OPENCODE_PERMISSION` (inline JSON), `OPENCODE_CONFIG_CONTENT` (whole config inline). How `ask` is handled without `--auto`: **not documented** | https://opencode.ai/docs/permissions/ , cli (28 Oct) |
| Provider/key | Catalog via `/connect`, keys in `~/.local/share/opencode/auth.json`. Custom provider in `opencode.json`: `provider.<id>.npm = "@ai-sdk/openai-compatible"` (chat completions) or `@ai-sdk/openai` (Responses), `options.baseURL`, `options.apiKey = "{env:VAR}"`, `models`. `baseURL` for `provider.anthropic` can be overridden (proxy). Config path via `OPENCODE_CONFIG`, `OPENCODE_CONFIG_DIR` | https://opencode.ai/docs/providers/ (28 Oct); V2: `@opencode/ai/providers/openai-compatible` package (local 25 Oct) |
| Done/error | Output `--format json`; **exit codes not documented** | cli (28 Oct) |
| Windows | Native Windows via Chocolatey, Scoop, npm, Mise, Docker, binaries; docs **recommend WSL** (performance, feature set) | https://opencode.ai/docs/ (28 Oct) |
| Security | Advisories (local 25 Oct): GHSA-632h-h47v-g4x4 (high, up to 1.18.21, 2026-09-24), GHSA-c83v-7274-4vgp (critical, XSS in the web UI, fixed 1.1.10), GHSA-vxw4-wv6m-9hhh (high, unauthenticated HTTP server, fixed 1.0.216). Press (secondary source, 2026-10-20): silently patched RCE via MCP OAuth on Windows/WSL, versions 1.0.137 to 1.18.32, fixed in 1.18.33; the vendor sees malicious MCP servers as "outside their threat model" | local `sources/opencode/github-security-advisories-api-2026-10-25.json`, `infosecurity-opencode-rce-2026-10-25.html` (https://www.infosecurity-magazine.com/news/opencode-quietly-patched-critical/) |

### B4. DeepSeek's own agent CLI: **DeepSeek Harness, command `dsh`**

| Point | Finding | Source |
|---|---|---|
| Official? | **Yes.** Repo `deepseek-ai/deepseek-harness` (MIT, created 2026-08-13), npm `@deepseek-ai/dsh`. The DeepSeek docs list "DeepSeek Harness" under "Agent Integrations" and call it a "developer preview". The abbreviation "dsh" is not named by the integration page itself, but appears in the README and the npm name | https://github.com/deepseek-ai/deepseek-harness (local 25 Oct), https://api-docs.deepseek.com/quick_start/agent_integrations/deepseek_harness (28 Oct) |
| Maturity | README: "Developer preview ... THERE WILL BE COMPATIBILITY-BREAKING CHANGES". SAFETY.md: no security review, not production ready, sandbox without guarantee, run in a throwaway VM/container. npm `latest` = `0.2.1-rc.2`, `next` = `0.2.1-rc.3`, `alpha` = `0.2.1-alpha.5` (25 Oct). Installed locally: 0.1.5-rc.1. No published advisories (25 Oct) | local 25 Oct |
| Headless | **`dsh --profile headless "job"`**: one fresh, stored session, prints the final answer to stdout and exits. Reasoning deltas go to stderr (`dsh: reasoning:`). Opens no ports. **Exit 0 = task done, 1 = aborted or error** (message `dsh: <code>: <message>` on stderr); an empty task is rejected before start; one task per call. The user docs of the main README (https://github.com/deepseek-ai/deepseek-harness/blob/master/apps/cli/README.md, 28 Oct) say "gives no numeric exit codes"; the exit statement comes from the package README `dsh-headless` of the installed version | installed package `~/.nvm/versions/node/v24.19.0/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai/dsh-headless/README.md` (read locally 28 Oct) |
| Other profiles | `web` (web UI, port 3080), `acp` (ACP over stdio), `sdk`/`sdk-minimal` (JSON-RPC over stdio), `plugin` | apps/cli README (28 Oct) |
| Working folder | "The invoking directory is the default workspace root" | README (28 Oct) |
| Model/provider/key | Keys in `$DSH_HOME/.credentials.yaml` (web UI writes them; "write-only"), settings in YAML patches (`cordis.patch.yml`, profile level, home level, `--patch` overlay); `--dump-config` shows the result. Bundled provider IDs include `anthropic`, `openai`, `moonshotai` (Kimi), `zai` (GLM), `openai-codex`; environment variables as a fallback for keys; custom providers via adapter plugin (`LlmAdapter`) or "custom OpenAI-compatible endpoints". Exact **environment variable names** and the **config lines for headless** (choose model/provider): **not documented** | docs/user/guide/providers.md (local 25 Oct), llm-adapter.md (local 25 Oct) |
| Permissions/sandbox | Packages `dsh-permission-presets` (`workspace-write` with `approval: ask`, `danger-full-access` with `approval: never`), `dsh-sandbox-local`, `dsh-fs-sandbox`, `dsh-bash-sandbox`, `dsh-pwsh-sandbox`, `dsh-sandbox-windows-acl`. Whether **headless** runs without prompts and how to set a tool allowlist: **not documented** | installed package directory (28 Oct) |
| Output | Plain text of the final answer only; no JSON mode for headless documented (SDK profile delivers JSON-RPC) | see above |
| Installation | `npx @deepseek-ai/dsh web` or npm global; Node.js required; from source `pnpm` | README |
| Windows | Windows sandbox packages exist (`dsh-pwsh-sandbox`, `dsh-sandbox-windows-acl`); the CLI docs contain "no Windows-specific guidance" → **official Windows support not documented** | apps/cli README (28 Oct) |

### B5. Antigravity CLI (`agy`)

| Point | Finding | Source |
|---|---|---|
| Classification | Google product family (app, CLI, IDE, SDK). Gemini CLI is being replaced by `agy` per Google docs (migration page: `agy plugin import gemini`, configuration moves from `~/.gemini/settings.json` to `mcp_config.json`). Antigravity app v2.26.0 (2026-10-22) | https://antigravity.google/docs/cli/gcli-migration (local 25 Oct) |
| Headless | **`agy -p "<prompt>"`** (alias `--print`, `--prompt`). Flags: `--output-format text|json|stream-json`, `--input-format text|stream-json`, `--json-schema`, `--model <slug>` (`agy models`), `--effort low|medium|high`, `--agent`, `--dangerously-skip-permissions`, `--continue/-c`, `--conversation <id>`, `--print-timeout` (default 5 min), `--sandbox` | https://antigravity.google/docs/cli/headless/ (28 Oct) |
| Working folder | Example on the best-practices page: `agy -p "..." --cwd $(pwd)`; the headless page lists no cwd flag; contradiction, **not conclusively documented** | https://antigravity.google/docs/cli/best-practices (28 Oct) |
| Permissions | Without `--dangerously-skip-permissions`, tools that need approval are "soft-denied": **the run ends with exit 0 and a note on stderr**. Pre-approvals: `permissions.allow` with `action(target)` in `~/.gemini/antigravity-cli/settings.json`; `toolPermission` = `request-review` (default), `proceed-in-sandbox`, `strict`. Rule priority deny > ask > allow. Sandbox: macOS `sandbox-exec`, Linux namespaces (docs index, local) | headless, best-practices (28 Oct); permissions/sandbox (local 25 Oct) |
| Output | JSON: `conversation_id`, `status` (`SUCCESS`, `ERROR`, `CANCELED`, `INTERRUPTED`, `INVALID`, `WAITING`, `RUNNING`), `response`, `error`, `duration_seconds`, `num_turns`, `usage{...}`, `structured_output`. Stream: `init` (with `cwd`, `tools`, `permission_mode`), `step_update`, `result` | headless (28 Oct) |
| Exit codes | 0 success; non-0 = no answer (examples: 1 unknown model/invalid input, 2 control events in stream input). Not logged in, non-interactive: error `authentication required`, no hang | headless (28 Oct) |
| Provider/key | Login by Google account, Gemini Enterprise/Cloud, ADC, keychain or "Using a Gemini API key" (section title of the installation page, local). Headless uses **cached credentials** (log in interactively once); `GEMINI_API_KEY` for the CLI **not mentioned** on the headless page (documented only for the SDK). **Non-Google model endpoints in `agy`: not documented** (no evidence that it works) | headless (28 Oct); docs-install, sdk-overview (local 25 Oct) |
| ToS | FAQ: access to Antigravity with third-party tools under an Antigravity login "is a violation of our Terms of Service" (suspension possible); for third-party agents a Gemini Enterprise or AI Studio API key is recommended; embedding `agy` in third-party applications or rotating accounts is "not supported" under private plans. Headless is meant for "direct scripting and CI workflows" | https://antigravity.google/docs/faq (28 Oct) |
| Installation/Windows | Installer per surface (details not evaluated); Windows detection exists on the page, **Windows support of the CLI not documented** | docs-install (local 25 Oct) |
| Repo | `google-antigravity/antigravity-cli`: no license registered according to the GitHub API; SDK Apache-2.0 | local 25 Oct |

### B6. Optional: Aider, Goose, Crush

| CLI | Headless | Provider/permissions | Output/exit | Windows | Source (28 Oct) |
|---|---|---|---|---|---|
| **Aider** | `--message/-m "..."` (or `--message-file/-f`, environment variable `AIDER_MESSAGE`) applies and exits; `--yes` confirms everything; `--commit`, `--dry-run`, `--no-auto-commits` | `--model`, `--openai-api-base`, key variables: **not documented** on the page | No JSON documented, exit codes **not documented**; Python API explicitly "not officially supported" | **not documented** | https://aider.chat/docs/scripting.html |
| **Goose** (now under AAIF) | `goose run -t "..."` / `-i <file>` / `-i -`; exits after the task; `--no-session`; `--provider`, `--model`; `--with-*-extension`; `--recipe` | Permissions (`GOOSE_MODE`): **not documented** | `--output-format json|stream-json`; exit codes **not documented** | `NUL` mentioned, otherwise **not documented** | https://goose-docs.ai/docs/guides/running-tasks |
| **Crush** (Charm) | Page does **not** show `crush run` (there "not in the page"); flags `--yolo`, `--debug`, `--cwd` | Pre-approval/blocking via `permissions allow view ls grep edit` / `permissions deny bash sourcegraph`; providers: `openai-compat` with `--base-url`, `--type anthropic` with base URL; DeepSeek example `https://api.deepseek.com/v1`. License **FSL-1.1-MIT** | Output/exit **not documented** | Yes: PowerShell and WSL, `winget install charmbracelet.crush`, Scoop | https://github.com/charmbracelet/crush |

### B7. Table runner × capability

Legend: **yes** = documented, **partly** = documented with restrictions, **nd** = not documented.

| Runner | Headless command | Own provider selectable | Tool allowlist | JSON/stream output | Exit code documented | Working folder | Windows |
|---|---|---|---|---|---|---|---|
| **claude** (CC) | `claude -p` yes | yes, Anthropic format only (env or `settings.json`) | yes (`--allowed-tools`, `--tools`, `dontAsk`) | yes (`json`, `stream-json`) | yes (0 / non-0, SIGTERM 143) | current directory, `--add-dir` | yes (Git for Windows recommended) |
| **codex** | `codex exec` yes | yes, Responses API endpoints only | partly (sandbox modes and execpolicy, no single-tool list) | yes (`--json`, `-o`, `--output-schema`) | nd | current directory, `-C`/`--cd` partly, `--worktree` | yes (native sandbox, WSL2) |
| **opencode** | `opencode run` yes | yes (catalog, OpenAI-compatible, Anthropic baseURL) | yes (`permission` rules, `--auto`, `OPENCODE_PERMISSION`) | yes (`--format json`) | nd | `--dir` | yes, docs advise WSL |
| **dsh** | `dsh --profile headless "..."` yes | yes (Kimi, GLM, OpenAI, Anthropic, custom adapters); headless configuration nd | nd (sandbox/approval presets exist) | no (plain text of the final answer) | partly (0/1 in the package README, main README "no numeric codes") | invoking directory | nd |
| **agy** | `agy -p` yes | nd (Google login/Gemini key; no third-party endpoints documented) | partly (`permissions.allow`, soft deny, `--sandbox`) | yes (`json`, `stream-json`) | yes, but soft deny returns exit 0 | `--cwd` documented contradictorily | nd |
| aider | `aider -m` yes | nd | no | nd | nd | nd | nd |
| goose | `goose run -t` yes | partly (`--provider`, `--model`) | nd | yes | nd | nd | nd |
| crush | `crush run` nd | yes (openai-compat, anthropic type) | yes (`permissions allow/deny`) | nd | nd | `--cwd` | yes |

---

## Recommendation: which runners first

| Rank | Runner | Reasoning |
|---|---|---|
| 1 | **claude** | Best-documented headless route with exit code, stream JSON, the finest tool allowlist and isolation (`--setting-sources`, `--strict-mcp-config`, `--bare`). Covers seven of the nine providers via base URL without a translator (DeepSeek, OpenRouter, Kimi, Ollama, Z.ai, MiniMax, Anthropic). The current wrapper is already built on it. |
| 2 | **codex** | Clean `exec` with JSONL, `-o`, schema, sandbox, Windows sandbox. Custom providers only with a Responses endpoint: covers OpenAI and potentially EUrouter (lists `/responses`; compatibility with Codex gateway requirements **not verified**). Brings a second model ecosystem. |
| 3 | **opencode** | Provider-neutral (catalog plus any OpenAI-compatible endpoints incl. Nvidia, EUrouter without a proxy), permissions as configuration, JSON output. Gaps: exit codes not documented, two version lines (V1/V2), recent security incidents; therefore pin the version and evaluate completion through `report.md` instead of the exit code. |
| 4 | **dsh** (marked "experimental") | Official DeepSeek harness with a simple `--profile headless`, but a developer preview with announced breaking changes, configuration for headless not documented, no JSON, Windows not documented. Add only once the interface is stable (release without `rc`/`alpha`). |
| later | agy | Third-party providers not documented, soft deny with exit 0 is a trap, ToS notes on third-party tools; only sensible as a pure Gemini runner with an API key. |
| later | Crush, Goose, Aider | Gaps in how well headless behavior can be documented (Crush `run` not documented; Aider without JSON/exit docs). |

### Common adapter interface

**Basic principle:** The truth about "done" is neither the exit code nor the output of the runner, but the **contract `report.md`** in the run folder (this is how the wrapper does it today). The exit code is only a secondary signal because it is documented differently per runner (agy: soft deny = 0; opencode/codex: not documented).

**Input (`task.json` or CLI arguments to the adapter):**

| Field | Meaning |
|---|---|
| `task` | Path to the task file (`task.md`), copied into the run folder |
| `workdir` | Empty run folder (default) or a specified project folder; the adapter sets cwd itself (`cd`, `--dir`, `-C`, `--cwd`) |
| `runner` | `claude` / `codex` / `opencode` / `dsh` |
| `provider` | Entry from the own provider list: `id`, `protocols` (`anthropic` / `openai-chat` / `openai-responses`), `base_url`, `key_name`, model table |
| `model` | Name or alias from that table |
| `tools` | Neutral list, e.g. `read`, `write`, `shell`, `web_search`, `web_fetch`; the adapter translates (CC: `--allowed-tools` plus `dontAsk`; OpenCode: `permission` JSON; Codex: `--sandbox read-only|workspace-write`; dsh: preset) |
| `limit` | `max_turns`, `max_cost`, `timeout_s` (CC: `--max-turns`, `--max-budget-usd`; otherwise adapter timeout per process group) |

**Output (always in the run folder):**

| File | Content |
|---|---|
| `report.md` | Result, written by the agent according to the task. Present = done |
| `log.jsonl` | Raw output of the runner (CC `stream-json`, Codex `--json`, OpenCode `--format json`, agy `stream-json`; dsh plain text) |
| `error.log` | stderr |
| `status.json` | `zustand` (`running` / `done` / `failed` / `cancelled`), `start`, `ende`, `exitcode`, `runner`, `anbieter`, `modell`, optional `kosten`, `runden` |
| Exit code of the adapter | 0 = `report.md` present and runner exit 0; 1 = runner error; 2 = configuration error (missing key, runner not installed); 3 = proxy/endpoint unreachable; 124 = time limit |

**Adapter duties (from the documented pitfalls):**

1. Clean the environment (`env -i` plus the bare minimum), hand over only the **one** needed key per runner; for CC keep `ANTHROPIC_API_KEY` empty; for Codex `CODEX_API_KEY` only for the call.
2. CC with `--setting-sources project`, `--strict-mcp-config`, `--no-session-persistence`, empty folder (or `--bare` + API key where no OAuth is needed), because `-p` otherwise executes hooks and MCP of the working folder.
3. Set all model variables (`ANTHROPIC_MODEL`, `*_OPUS/SONNET/HAIKU_MODEL`, `CLAUDE_CODE_SUBAGENT_MODEL`), otherwise background tiers fail silently (Kimi page).
4. Always give the task text a call limit and a result format (local DeepSeek test: without a limit 232 s, with a limit 16 s).
5. Done = `report.md`; in addition evaluate the runner signal: CC last `result` line, Codex `turn.completed`/`turn.failed`, agy `status`, dsh exit 0/1.
6. Supply-chain caution: pin runner versions; LiteLLM/proxy only optional and with a pin (section A3).
7. Never store or pass on tokens (section A5).

---

## Full list: not documented

- Ollama: minimum version for the Anthropic API (both doc pages name none; GitHub releases not checked).
- EUrouter: existence of a Messages path finally excluded (OpenAPI only read for 100,000 of 278,743 characters); Codex compatibility via `/responses`; prices; retention periods.
- Kimi, Z.ai, MiniMax: prices, data location/GDPR, WebSearch/WebFetch function in Claude Code.
- OpenRouter: prices, data location, web search via the Anthropic interface.
- Nvidia NIM: Anthropic endpoint (only "not mentioned"), free-tier limits and terms of use, data location.
- DeepSeek: legal GDPR assessment (only storage location China and training use from the privacy policy).
- LiteLLM: whether 1.106.4/1.106.5 are explicitly confirmed clean by the vendor; Claude Code guide from the vendor; `/v1/responses` for non-OpenAI targets.
- claude-code-router: configuration schema, content of the Security tab, date of the last commit; other translator proxies not examined.
- Claude Code: field names of the `result` object (`is_error`/`subtype`) on the retrieved pages; behavior of `--bare` with `ANTHROPIC_AUTH_TOKEN`; whether unattended runs with a subscription token are permitted.
- Codex: exit codes, full `exec` flag table (`--model`, `--cd`, `--skip-git-repo-check`, `--approve-for-me` only seen locally).
- OpenCode: exit codes, handling of `ask` without `--auto`, config path.
- dsh: environment variable names for keys, headless model configuration, tool allowlist, Windows support, JSON output.
- agy: `--cwd` behavior, Windows, third-party endpoints, `GEMINI_API_KEY` in the CLI.
- Aider, Goose, Crush: exit codes, permissions, Windows details partly not documented; Crush `run` not documented.
- All statements marked "(local 25 Oct)" were not re-checked against the vendor URL today.
