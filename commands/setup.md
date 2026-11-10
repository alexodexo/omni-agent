---
description: Sets up Omni-Agent (folder, key file, command, check) and, on request, turns the review gate before exit on or off
argument-hint: '[--provider ID] [--review-gate on|off]'
allowed-tools: Bash(python3:*), AskUserQuestion
---

!`python3 "${CLAUDE_PLUGIN_ROOT}/bin/omni-agent" setup $ARGUMENTS`

Explain the result briefly: which agent CLI was found, which providers have a key or login, what is missing.

Rules:

- **The user enters keys themselves.** Give them the path `~/.omni-agent/env` and the line `NAME=value` (the name is in the output of `setup --provider ID`). Never ask for the key in chat, never write it to a file yourself, never read the file.
- If no agent CLI is installed, say so clearly and name `claude`, `codex` or `opencode` as options. Install nothing without an explicit request.
- If Codex is installed but not logged in, point to `codex login` in the terminal (for example `!codex login` in chat) and do not improvise another way.
- Several Claude accounts: each gets a name (`omni-agent account add NAME --kind api|token`). The user enters the key in the terminal. A subscription token for unattended runs is not explicitly permitted by Anthropic: say so before the user decides on it.
- **Review gate** (`--review-gate on`): before a Claude session ends, every new state of unreviewed changes is sent to the default account and can hold up the exit once. This costs usage and the diff leaves this machine. Turn it on only on explicit request and say so.
- If Python 3.10 or newer is missing, say so clearly: Omni-Agent needs it (macOS, Linux, WSL).
- Providers without the Claude format (EUrouter, Nvidia) run with `--runner opencode` or through the LiteLLM extra (`omni-agent extras litellm install`, only on request).
