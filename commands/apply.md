---
description: Shows the changes an agent made to a project copy on a host and, with --yes, writes them into your project
argument-hint: '[--host NAME] [--project DIR] [--yes] [--force]'
disable-model-invocation: true
allowed-tools: Bash(omni-agent:*)
---

!`omni-agent apply $ARGUMENTS`

Pass the output on briefly. Without `--yes` nothing was written: say so and show the changed files. Ask the user before you run the command again with `--yes`. Files reported as SKIPPED were changed locally since they were sent; only `--force` overwrites them, and only if the user says so.
