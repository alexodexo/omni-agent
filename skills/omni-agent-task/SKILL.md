---
name: omni-agent-task
description: Internal guide for writing a task for an Omni-Agent run (goal, context, done criterion, limits). Only for sharpening the task text, not for solving the task yourself.
user-invocable: false
---

# Writing a task for an Omni-Agent run

The agent knows neither this conversation nor what you have already read. Sharpen the user's request only far enough that the agent can finish it alone. Do not solve it yourself and do not investigate the project for it.

## Building blocks

Take only what the task needs, as short sections (XML-like tags or headings):

| Block | Content |
|---|---|
| Goal | One sentence: what should exist at the end? |
| Context | Only facts the agent cannot find itself: error message, location, what has been tried. In project mode, give file paths instead of file contents. |
| Done when | The checkable criterion: "names the three most likely causes with file and line". |
| Limits | What it must not do: change nothing, delete nothing, make no assumptions about data outside the task. |
| Form | Only if needed: table, order by weight. The run's report frame already gives the basic structure. |

## Rules

- One task, one goal. Two independent questions are two runs.
- Phrase positively ("name the cause with evidence") instead of "do not guess".
- Ask for evidence and for observation to be separated from conjecture. The run's frame already does this; do not repeat it.
- No credentials and no personal data in the text. In project mode, point to files instead of copying them.
- Keep the user's words where they are precise. Add to them, do not replace them.
- Write long tasks to a file and pass the path.

## Example

User request: "Find out why the login sometimes hangs."

Task: "Goal: find causes for the sporadically hanging login. Context: the hang appeared after the session handling was changed; `app/auth/` and `lib/session.ts` are probably relevant. Done when: up to three causes are named with file and line and one way to verify each. Limits: read only, change nothing."
