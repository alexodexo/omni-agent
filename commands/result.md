---
description: Zeigt den gespeicherten Bericht eines fertigen Omni-Agent-Laufs (ohne Angabe: der neueste dieser Sitzung)
argument-hint: '[lauf]'
disable-model-invocation: true
allowed-tools: Bash(omni-agent:*)
---

!`omni-agent result $ARGUMENTS`

Gib die gesamte Ausgabe unverändert wieder, ohne Zusammenfassung oder Kürzung. Behalte Urteil, Befunde, Belege, Annahmen, Dateipfade und Zeilen exakt bei, ebenso die Folgebefehle am Ende (Nachfrage, Status).
Danach nicht von dir aus Änderungen am Code vornehmen. Die Nutzerin sagt, was übernommen wird.
