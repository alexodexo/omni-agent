---
description: Shows the named Claude accounts with usage (5 hours, 7 days) and the default account
argument-hint: '[--no-usage]'
disable-model-invocation: true
allowed-tools: Bash(omni-agent:*)
---

!`omni-agent account list $ARGUMENTS`

Pass the output on briefly. For each account state usage and reset time, and say which account currently has the most headroom. The user adds or changes accounts in the terminal (`omni-agent account add NAME --kind api|token`), never in chat.
