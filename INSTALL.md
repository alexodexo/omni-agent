# Installation by an agent

**For Claude Code (or another agent) when the user says "Install Omni-Agent for me" or "Walk me through the installation".**
Work through the steps in this order. Do not run anything that is not listed here. You **never** ask for keys in the chat.

## 1. Check the requirements

```bash
python3 --version      # 3.9 or newer required
claude --version       # default runner
```

- Python is missing or too old: tell the user and stop. Platforms: macOS, Linux, WSL.
- `claude` is missing: Claude Code must be installed, otherwise there is no default runner. Alternative runners (opencode, codex) only on request.

## 2. Install the plugin (recommended)

```bash
claude plugin marketplace add alexodexo/omni-agent
claude plugin install omni-agent@omni-agent
```

Then run `/reload-plugins` in Claude Code (or restart). Check: `claude plugin list` shows `omni-agent@omni-agent` as enabled.

*Without the plugin:* clone the repo and use `bin/omni-agent` directly. All commands below work the same.

## 3. Set up

```bash
omni-agent setup
```

(If `omni-agent` is not in the PATH yet: `"<plugin or repo folder>/bin/omni-agent" setup`. Inside the plugin that is `${CLAUDE_PLUGIN_ROOT}/bin/omni-agent`.)

The command creates `~/.omni-agent/` and the key file `~/.omni-agent/env` (mode 600), links `omni-agent` into `~/.local/bin` and checks the machine. Summarize the result briefly for the user.

## 4. Choose a provider and enter the key

Ask the user which provider they want to use (`omni-agent providers` lists them with their data location). Before the choice, state the **data location** (for example DeepSeek: China) and that nothing personal or internal belongs in tasks.

```bash
omni-agent setup --provider <provider>
```

This prints which line is missing in `~/.omni-agent/env`. **The user enters the key themselves**, in their own editor. You do not write it, do not read the file and do not ask for it in the chat.

## 5. Check

```bash
omni-agent doctor
```

Expected: the chosen provider shows "key: set" and an installed matching runner. If the provider shows "none installed" (for example EUrouter or Nvidia), it needs `opencode` or the LiteLLM extra (`omni-agent extras litellm install`, only on request).

## 6. Trial run

With the user's consent, a small, harmless task:

```bash
omni-agent run --provider <provider> --text "Name in three bullet points what a background agent is useful for." --max-turns 3 --tools read,write
```

Success: exit 0 and `Report: …/report.md`. Read the report and show it briefly. Failure: read the exit code (2 configuration, 3 endpoint unreachable, 124 timeout) and look at `error.log` in the run folder.

## 7. Done

Tell the user what comes next: `/omni-agent:run <task>` (with `--account NAME` or `--provider ID`), `/omni-agent:review`, `/omni-agent:status`, `/omni-agent:doctor`. Claude can also delegate on its own through the subagent `omni-agent:worker`. Mention that results from third-party models are drafts.

## What you do not do

- Do not ask for, print, write to a file or insert into a command any key.
- `--tools +shell` only on explicit request.
- Do not recommend a subscription token (`CLAUDE_CODE_OAUTH_TOKEN`): whether unattended runs with it are allowed is not documented. An API key is recommended.
- Install the LiteLLM extra only if the user wants it.
