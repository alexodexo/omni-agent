---
description: Zeigt Omni-Agent-Läufe (arbeitet, fertig, fehler) und liest auf Wunsch den Bericht eines Laufs
argument-hint: "[lauf]"
allowed-tools: Bash(omni-agent status*)
---

# Omni-Agent-Läufe ansehen

Eingabe: `$ARGUMENTS`

- Ohne Angabe: `omni-agent status` zeigt die letzten Läufe mit Zustand, Anbieter, Modell und Dauer.
- Mit Angabe (Teil des Laufnamens): `omni-agent status <lauf>` zeigt Zustand und den Pfad zum Bericht.
- Auf Wunsch den Bericht (`bericht.md`) lesen und zusammenfassen. Stellen, die der Agent als „nicht belegt" markiert hat, so weitergeben.
- Ein Lauf im Zustand `fehler`: `fehler.log` und `log.jsonl` im Laufordner ansehen und den Grund nennen.
