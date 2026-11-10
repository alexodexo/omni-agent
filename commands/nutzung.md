---
description: Zeigt Nutzung und Guthaben aller Anbieter (Claude-Konten, Codex, DeepSeek, Kimi, OpenRouter, EUrouter), soweit sie der Anbieter hergibt
argument-hint: '[konten|codex|deepseek|kimi|openrouter|eurouter]'
disable-model-invocation: true
allowed-tools: Bash(omni-agent:*)
---

!`omni-agent nutzung $ARGUMENTS`

Gib die Ausgabe knapp wieder, ein Anbieter pro Zeile. Sage am Ende, wo am meisten Luft ist (Prozent oder Guthaben) und wo etwas knapp wird oder ein STATUS steht. Zahlen aus der Ausgabe nicht umrechnen oder schätzen; fehlt eine Angabe, sage das.
