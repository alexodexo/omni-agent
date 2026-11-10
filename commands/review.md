---
description: Has another model or account review the git changes in the current repo (second opinion). The diff leaves this machine.
argument-hint: '[--foreground|--background] [--base REF] [--account NAME | --provider ID] [--adversarial] [focus]'
disable-model-invocation: true
allowed-tools: Bash(omni-agent:*), Bash(git:*), AskUserQuestion
---

Start a review through Omni-Agent.

Raw arguments:
`$ARGUMENTS`

Ground rule: this command **only reviews**. Do not fix anything, do not apply patches and do not announce changes. Your only job is to start the review and hand the result to the user.

Procedure:

1. **Preview, sending nothing.** Run `omni-agent review --preview` with the user's options minus `--foreground`/`--background` (that is `--base`, `--account`, `--provider`, `--adversarial`, focus text). The preview names the target (working tree, or branch against the main branch), files, size and warnings. If it reports "secrets" or "no changes", send **nothing** and tell the user why.
2. **Does the data go to a third-party provider?** Only if the user names `--provider` with a third-party provider (not Codex, not `claude-…`): say in two lines which files go to which provider and where its data is stored (`omni-agent providers`). If the user named the provider explicitly, that is the approval; do not ask again.
3. **Mode.** `--foreground`: run in the foreground. `--background` or no flag: run in the background.
4. **Start.** In the background with the `Bash` tool and `run_in_background: true`, in the foreground normally with `timeout: 600000`:

```bash
omni-agent review OPTIONS
```

   In the background, say in one line: started, you will be notified, check progress with `/omni-agent:status`. Do not poll, do not fetch the output, do not wait in this turn.
5. **When the run ends:** `omni-agent result` shows the report. Pass it on verbatim (skill `omni-agent-results`): verdict, findings by severity with file and line, next steps.

Then **stop.** Do not fix any finding. Ask the user which findings they want fixed before you touch a file. Not automatically even when the fix is obvious.

Arguments:

- Pass the user's arguments on unchanged, except `--foreground`/`--background`.
- Without `--account`/`--provider` the user's default applies (`omni-agent account default`).
- Without `--base`, Omni-Agent reviews the changes against HEAD; if the working tree is clean, it reviews the branch against the main branch.
- For adversarial review (challenging the chosen solution) use `/omni-agent:adversarial-review`.
