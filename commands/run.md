---
description: Hands a task to an Omni-Agent run (another model, another Claude account or Codex), in the background by default
argument-hint: '[--foreground|--background] [--resume|--new] [--account NAME | --provider ID] [--model M] [--effort low|medium|high] [--project] [--write] [--host NAME] [task]'
disable-model-invocation: true
allowed-tools: Bash(omni-agent:*), AskUserQuestion, Agent
---

Call the subagent `omni-agent:worker` through the `Agent` tool (`subagent_type: "omni-agent:worker"`) and pass the raw request on as the prompt.
`omni-agent:worker` is a subagent, not a skill: do not call `Skill(omni-agent:worker)` or `Skill(omni-agent:run)` (that would invoke this command again and hang the session). The command runs inline so that the `Agent` tool stays available.
The final answer to the user is the subagent's output, unchanged.

Raw request:
$ARGUMENTS

Execution mode:

- `--background`: start the subagent with `run_in_background: true`. Afterwards say in one line: started, you will be notified, check progress with `/omni-agent:status`.
- `--foreground`: run the subagent in the foreground.
- Without a flag: background, unless the request is small and clearly bounded (one question, a comparison in a few lines); then foreground.
- `--foreground` and `--background` only control Claude Code. Do not pass them to the subagent and do not count them as task text.
- `--account`, `--provider`, `--model`, `--effort`, `--runner`, `--project`, `--write` stay in the request; the subagent puts them on the command.

Resume or new:

- If the request contains `--resume` or `--new`, do not ask. The user has decided.
- Otherwise check before starting:

```bash
omni-agent resumable
```

- If it reports `"available": true`, ask exactly once with `AskUserQuestion` whether to continue with the last agent or start a new one. Two answers: `Follow up with the last agent` and `Start a new run`. If the request sounds like a continuation ("keep going", "go deeper", "implement the best fix"), put the first answer first with `(Recommended)`, otherwise the second.
- If the user chooses to follow up, add `--resume`; if they choose new, add `--new`.
- If it reports `"available": false`, do not ask.

Rules:

- The subagent is a pure forwarder. Do not let it read files, query the status or do its own work.
- Do not pick a third-party provider yourself. If the user named none, their default applies. If none is set and the user named none, ask (`omni-agent account list`, `omni-agent providers`).
- Never ask for a key in chat. If setup is missing, point to `/omni-agent:setup`.
- If the user gave no task, ask what should be done.
- Pass the output on verbatim. Apply the rules of the skill `omni-agent-results`: results from a third-party model are claims; do not change code before the user has said what to adopt.
