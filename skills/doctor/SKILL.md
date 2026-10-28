---
description: Prüft, was für Omni-Agent da ist und was fehlt (Agent-CLIs, Schlüssel, Passung von Anbieter und Runner)
allowed-tools: Bash(omni-agent doctor*)
---

# Omni-Agent prüfen

Führe `omni-agent doctor` aus (mit `--netz`, wenn die Nutzerin Erreichbarkeit wissen will) und fasse zusammen:

- Welche Agent-CLIs sind installiert?
- Für welche Anbieter ist ein Schlüssel gesetzt, und welcher Runner passt dazu?
- Was blockiert einen Lauf, und was ist der nächste Schritt (`/omni-agent:setup`)?

Gib **nie** Schlüsselwerte aus. Der Befehl nennt nur „gesetzt" oder „fehlt".
