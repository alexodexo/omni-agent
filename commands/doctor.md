---
description: Checks what is available for Omni-Agent and what is missing (agent CLIs, keys, login, fit, review gate)
argument-hint: '[--network]'
disable-model-invocation: true
allowed-tools: Bash(omni-agent:*)
---

!`omni-agent doctor $ARGUMENTS`

Summarize in a few lines: Which agent CLIs are installed? For which providers is a key set or a login active, and which runner fits? What blocks a run, and what is the next step (`/omni-agent:setup`)?
Never state key values. The output only says "set" or "missing".
