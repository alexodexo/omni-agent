---
description: Zeigt die Omni-Agent-Läufe dieser Sitzung (oder aller) und den Stand eines Laufs
argument-hint: '[lauf] [--alle]'
disable-model-invocation: true
allowed-tools: Bash(omni-agent:*)
---

!`omni-agent status --md $ARGUMENTS`

Ohne Laufname: Gib die Tabelle unverändert aus, ohne zusätzlichen Text. Mit Laufname: Gib die Ausgabe vollständig und unverändert aus, ohne Zusammenfassung.
