---
description: Prüft, was für Omni-Agent da ist und was fehlt (Agent-CLIs, Schlüssel, Anmeldung, Passung, Review-Gate)
argument-hint: '[--netz]'
disable-model-invocation: true
allowed-tools: Bash(omni-agent:*)
---

!`omni-agent doctor $ARGUMENTS`

Fasse in wenigen Zeilen zusammen: Welche Agent-CLIs sind installiert? Für welche Anbieter ist ein Schlüssel gesetzt oder ein Login aktiv, und welcher Runner passt? Was blockiert einen Lauf, und was ist der nächste Schritt (`/omni-agent:setup`)?
Nenne nie Schlüsselwerte. Die Ausgabe sagt nur „gesetzt" oder „fehlt".
