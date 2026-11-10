---
description: Gibt einen Auftrag an einen Omni-Agent-Lauf (anderes Modell, anderes Claude-Konto oder Codex), standardmäßig im Hintergrund
argument-hint: '[--vordergrund|--hintergrund] [--fortsetzen|--neu] [--konto NAME | --anbieter ID] [--modell M] [--aufwand low|medium|high] [--projekt] [--schreibend] [Auftrag]'
disable-model-invocation: true
allowed-tools: Bash(omni-agent:*), AskUserQuestion, Agent
---

Rufe den Subagenten `omni-agent:lauf` über das `Agent`-Werkzeug auf (`subagent_type: "omni-agent:lauf"`) und gib die rohe Anfrage als Prompt weiter.
`omni-agent:lauf` ist ein Subagent, kein Skill: Rufe weder `Skill(omni-agent:lauf)` noch `Skill(omni-agent:run)` auf (das ruft diesen Befehl erneut auf und hängt die Sitzung). Der Befehl läuft inline, damit das `Agent`-Werkzeug im Zugriff bleibt.
Die endgültige Antwort an die Nutzerin ist die Ausgabe des Subagenten, unverändert.

Rohe Anfrage:
$ARGUMENTS

Ausführungsmodus:

- `--hintergrund`: Subagent mit `run_in_background: true` starten. Sage danach in einer Zeile: gestartet, du wirst benachrichtigt, Stand mit `/omni-agent:status`.
- `--vordergrund`: Subagent im Vordergrund laufen lassen.
- Ohne Flag: Hintergrund, außer die Anfrage ist klein und klar begrenzt (eine Frage, ein Vergleich in wenigen Zeilen), dann Vordergrund.
- `--vordergrund` und `--hintergrund` steuern nur Claude Code. Gib sie nicht an den Subagenten weiter und zähle sie nicht zum Auftragstext.
- `--konto`, `--anbieter`, `--modell`, `--aufwand`, `--runner`, `--projekt`, `--schreibend` bleiben in der Anfrage; der Subagent setzt sie am Befehl ein.

Fortsetzen oder neu:

- Enthält die Anfrage `--fortsetzen` oder `--neu`, frage nicht. Die Nutzerin hat entschieden.
- Sonst prüfe vor dem Start:

```bash
omni-agent fortsetzbar
```

- Meldet das `"available": true`, frage genau einmal mit `AskUserQuestion`, ob der letzte Agent fortgesetzt oder ein neuer gestartet werden soll. Zwei Antworten: `Beim letzten Agenten nachhaken` und `Neuen Lauf starten`. Klingt die Anfrage nach Fortsetzung („mach weiter", „geh tiefer", „setz die beste Korrektur um"), stelle die erste Antwort mit `(Empfohlen)` nach vorn, sonst die zweite.
- Wählt sie das Nachhaken, füge `--fortsetzen` hinzu, wählt sie neu, füge `--neu` hinzu.
- Meldet es `"available": false`, frage nicht.

Regeln:

- Der Subagent ist ein reiner Weiterleiter. Lass ihn weder Dateien lesen noch den Stand abfragen noch eigene Arbeit machen.
- Wähle selbst keinen Fremdanbieter. Hat die Nutzerin keinen genannt, gilt ihr Standard. Ist keiner gesetzt und sie hat keinen genannt, frage nach (`omni-agent konto list`, `omni-agent anbieter`).
- Frage nie im Chat nach einem Schlüssel. Fehlt Einrichtung, verweise auf `/omni-agent:setup`.
- Hat die Nutzerin keinen Auftrag mitgegeben, frage, was erledigt werden soll.
- Gib die Ausgabe wörtlich weiter. Wende die Regeln des Skills `omni-agent-ergebnis` an: Fremdmodell-Ergebnisse sind Behauptungen, ändere nichts am Code, bevor die Nutzerin gesagt hat, was sie übernommen haben will.
