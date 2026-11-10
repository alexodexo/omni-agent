---
description: Shows usage and balance of all providers (Claude accounts, Codex, DeepSeek, Kimi, OpenRouter, EUrouter), as far as the provider reports it
argument-hint: '[accounts|codex|deepseek|kimi|openrouter|eurouter]'
disable-model-invocation: true
allowed-tools: Bash(omni-agent:*)
---

!`omni-agent usage $ARGUMENTS`

Pass the output on briefly, one provider per line. At the end say where there is the most headroom (percent or balance) and where something is getting tight or a STATUS is shown. Do not convert or estimate numbers from the output; if a value is missing, say so.
