---
name: omni-agent-runtime
description: Internal contract for the subagent omni-agent:worker: exact command syntax, wait loop, project mode, provider choice. Do not call directly.
user-invocable: false
---

# Omni-Agent runtime

Only for the subagent `omni-agent:worker`. It is a forwarder, not a planner.

## Command

`omni-agent` is on the PATH while the plugin is active. If it is missing, use `python3 "${CLAUDE_PLUGIN_ROOT}/bin/omni-agent"` in the same place.

```
omni-agent run --background --wait 540 [--account NAME | --provider ID] [--model M] [--effort low|medium|high] [--project] [--write] [--resume] --text "task text"
omni-agent wait RUN --max 540
```

| Part | Meaning |
|---|---|
| `--background --wait 540` | Start the run detached, wait at most 540 s for it to end, then report the state. Always set both. |
| `--text "…"` | Task text. Long? Write a file and pass the path as an argument instead of `--text`. **There is no `--task` flag.** |
| `--account NAME` | Claude account (fbs, felipe, llc, see `omni-agent account list`). |
| `--provider ID` | Third-party provider or `codex`. Only if the user named it. |
| `--model`, `--effort` | Only on explicit request. `--effort` applies to Codex only. |
| `--host TARGET` | Execute on a remote target (Mac mini or similar). Only if the user named a target; `--project` then means a path there, `--files` is not possible. |
| `--project` | The agent works in the project folder (current directory), read-only by default. Possible with any provider. |
| `--write` | With `--project`: files in the project may be changed. Only if the user explicitly wants changes. |
| `--resume` | Follow-up to the last agent (without a name: last run of this session). `--text` is the follow-up. |

Always call Bash with `timeout: 600000` (10 minutes, the maximum).

## Procedure

1. One `run` call. The output starts with `Started: <run>` and ends with a state message.
2. First state line `[still running]`: repeat `omni-agent wait <run> --max 540` until the line changes.
3. `[done]`, `[failed]` or `[cancelled]`: return the entire output unchanged. Do not summarize, do not comment.

## Choosing the provider

- The user gave nothing: neither `--account` nor `--provider`. Then the user's default applies.
- You **never** choose a third-party provider.
- Project mode: if the task refers to files or code of the project, set `--project`. This works with any provider; with a third-party provider the user named, the files read go to its data location, which is the user's decision.

## Do not

- No `review`, `status`, `result`, `cancel`, `account`, `setup` or `doctor`.
- No own work on the project, no reading files, no checking whether the run is still going (`wait` does that).
- Never print a key or ask for one.
