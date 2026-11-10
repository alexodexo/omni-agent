---
description: Shows the Omni-Agent runs of this session (or all) and the state of one run
argument-hint: '[run] [--all]'
disable-model-invocation: true
allowed-tools: Bash(omni-agent:*)
---

!`omni-agent status --md $ARGUMENTS`

Without a run name: output the table unchanged, with no extra text. With a run name: output the full text unchanged, without summary.
