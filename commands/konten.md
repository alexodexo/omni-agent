---
description: Zeigt die benannten Claude-Konten mit Auslastung (5 Stunden, 7 Tage) und dem Standardkonto
argument-hint: '[--ohne-nutzung]'
disable-model-invocation: true
allowed-tools: Bash(omni-agent:*)
---

!`omni-agent konto list $ARGUMENTS`

Gib die Ausgabe knapp wieder. Nenne bei jedem Konto Auslastung und Reset-Zeit und sage, welches Konto aktuell am meisten Luft hat. Konten anlegen oder ändern macht die Nutzerin selbst im Terminal (`omni-agent konto add NAME --art api|token`), nie im Chat.
