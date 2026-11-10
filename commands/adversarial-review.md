---
description: Gegnerisches Review der Git-Änderungen durch ein anderes Modell oder Konto: stellt die gewählte Lösung infrage. Der Diff verlässt den Rechner.
argument-hint: '[--vordergrund|--hintergrund] [--base REF] [--konto NAME | --anbieter ID] [Schwerpunkt, z. B. Rechte, Wiederholungen, Datenverlust]'
disable-model-invocation: true
allowed-tools: Bash(omni-agent:*), Bash(git:*), AskUserQuestion
---

Starte ein **gegnerisches** Review durch Omni-Agent: Es prüft nicht nur auf Fehler, sondern stellt Annahmen, Entwurf und Fehlermodi der gewählten Lösung infrage. Hänge **immer** `--adversarial` an die Befehle von `/omni-agent:review` an, auch an `--vorschau`.

Rohe Argumente:
`$ARGUMENTS`

Grundregel: Dieser Befehl **prüft nur**. Behebe nichts, wende keine Patches an und kündige keine Änderungen an. Deine einzige Aufgabe ist, das Review zu starten und das Ergebnis der Nutzerin zu geben.

Ablauf (wie bei `/omni-agent:review`, nur mit `--adversarial`):

1. **Vorschau, ohne etwas zu senden.** Führe `omni-agent review --vorschau` aus, mit den Optionen der Nutzerin ohne `--vordergrund`/`--hintergrund` (also `--base`, `--konto`, `--anbieter`, `--adversarial`, Schwerpunkt-Text). Die Vorschau nennt Ziel (Arbeitsbaum oder Branch gegen den Hauptzweig), Dateien, Größe und Warnungen. Meldet sie „Geheimnisse" oder „Keine Änderungen", sende **nichts** und sage der Nutzerin den Grund.
2. **Gehen die Daten an einen Fremdanbieter?** Nur wenn die Nutzerin `--anbieter` mit einem Fremdanbieter nennt (nicht Codex, nicht `claude-…`): Sage in zwei Zeilen, welche Dateien an welchen Anbieter gehen und wo dessen Daten liegen (`omni-agent anbieter`). Hat die Nutzerin den Anbieter ausdrücklich genannt, ist das die Freigabe, frage nicht erneut.
3. **Modus.** `--vordergrund`: im Vordergrund. `--hintergrund` oder ohne Flag: im Hintergrund.
4. **Start.** Im Hintergrund mit dem `Bash`-Werkzeug und `run_in_background: true`, im Vordergrund normal mit `timeout: 600000`:

```bash
omni-agent review OPTIONEN
```

   Im Hintergrund sage in einer Zeile: gestartet, du wirst benachrichtigt, Stand mit `/omni-agent:status`. Frage nicht ab, rufe die Ausgabe nicht ab, warte nicht in diesem Zug.
5. **Wenn der Lauf endet:** `omni-agent result` zeigt den Bericht. Gib ihn wörtlich weiter (Skill `omni-agent-ergebnis`): Urteil, Befunde nach Schwere mit Datei und Zeile, nächste Schritte.

Danach **anhalten.** Behebe keinen Befund. Frage die Nutzerin, welche Befunde sie behoben haben will, bevor du eine Datei anfasst. Auch dann nicht automatisch, wenn die Lösung offensichtlich ist.

Argumente:

- Gib die Argumente der Nutzerin unverändert weiter, außer `--vordergrund`/`--hintergrund`.
- Ohne `--konto`/`--anbieter` gilt der Standard der Nutzerin (`omni-agent konto standard`).
- Ohne `--base` prüft Omni-Agent die Änderungen gegen HEAD; ist der Arbeitsbaum sauber, den Branch gegen den Hauptzweig.
- Der Text nach den Optionen ist der Schwerpunkt, auf den das Review besonders achten soll. Ohne Schwerpunkt prüft es breit.
