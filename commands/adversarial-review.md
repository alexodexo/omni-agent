---
description: Adversarial review of the git changes by another model or account: challenges the chosen solution. The diff leaves this machine.
argument-hint: '[--foreground|--background] [--base REF] [--account NAME | --provider ID] [focus, e.g. permissions, retries, data loss]'
disable-model-invocation: true
allowed-tools: Bash(omni-agent:*), Bash(git:*), AskUserQuestion
---

Start an **adversarial** review through Omni-Agent: it does not only look for bugs, it challenges the assumptions, the design and the failure modes of the chosen solution. **Always** append `--adversarial` to the commands of `/omni-agent:review`, including `--preview`.

Raw arguments:
`$ARGUMENTS`

Ground rule: this command **only reviews**. Do not fix anything, do not apply patches and do not announce changes. Your only job is to start the review and hand the result to the user.

Procedure (same as `/omni-agent:review`, only with `--adversarial`):

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
- The text after the options is the focus the review should pay particular attention to. Without a focus it reviews broadly.
