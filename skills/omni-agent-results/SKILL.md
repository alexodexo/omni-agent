---
name: omni-agent-results
description: Internal rules for how reports, reviews and status messages from Omni-Agent are shown to the user. Load as soon as there is output from omni-agent.
user-invocable: false
---

# Passing on results from Omni-Agent

When `omni-agent` or the subagent `omni-agent:worker` returns output:

- Keep structure, verdict, findings and next steps as they arrive. No rewrite, no shortening without reason.
- For reviews, findings first, ordered by severity. File names and lines exactly as reported.
- Keep the limits of evidence: what the agent marks as conjecture, "not verified", assumption or open question stays recognizable.
- If there are no findings, say so explicitly and keep the residual-risk sentence short.
- If the agent changed files (project mode with `--write`), say so and name the files when the report names them.
- A third-party model delivers claims. Check a finding against the code before you confirm it as a defect.
- **After showing review findings, stop.** Change nothing and fix nothing until the user has said which findings they want fixed. Not even when the fix is obvious.
- If a run fails (`[failed]`, `[cancelled]`, no report): name the most useful lines and stop. Do not turn it into your own implementation attempt. If the agent was never started successfully, do not invent a substitute answer.
- If the output asks for setup or login: point to `/omni-agent:setup` and do not improvise another login path. Never ask for a key in chat.
- Follow-ups to the same agent: `/omni-agent:run --resume …`. Cancel: `/omni-agent:cancel`.
