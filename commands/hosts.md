---
description: Zeigt die Fernziele (Mac mini, Server per ssh/Tailscale), auf denen Omni-Agent Läufe mit --host ausführen kann
argument-hint: '[test NAME]'
disable-model-invocation: true
allowed-tools: Bash(omni-agent:*)
---

!`omni-agent host $ARGUMENTS`

Gib die Ausgabe knapp wieder. Ziele anlegen oder installieren macht die Nutzerin selbst im Terminal (`omni-agent host add NAME --ssh benutzer@adresse`, `omni-agent host install NAME`); Schlüssel und Anmeldungen richtet sie auf dem Ziel selbst ein, nie im Chat. Ohne Argument zeigt der Befehl die Liste (`list`); für `test NAME` sagt er, was auf dem Ziel fehlt.
