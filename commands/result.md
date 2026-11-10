---
description: Shows the stored report of a finished Omni-Agent run (without an argument: the newest one of this session)
argument-hint: '[run]'
disable-model-invocation: true
allowed-tools: Bash(omni-agent:*)
---

!`omni-agent result $ARGUMENTS`

Pass the entire output on unchanged, without summary or shortening. Keep verdict, findings, evidence, assumptions, file paths and lines exactly, and the follow-up commands at the end (follow-up, status).
Afterwards do not change code on your own. The user says what to adopt.
