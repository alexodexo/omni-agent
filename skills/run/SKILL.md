---
description: Startet einen Hintergrund-Agent mit einem Fremdmodell (DeepSeek, OpenRouter, Kimi, Ollama, EUrouter, anderes Claude-Konto) für einen Auftrag und liefert einen Bericht
argument-hint: "[anbieter] [auftrag]"
disable-model-invocation: true
allowed-tools: Bash(omni-agent *)
---

# Omni-Agent: Auftrag im Hintergrund ausführen

Eingabe der Nutzerin: `$ARGUMENTS`

## Ablauf

1. **Anbieter klären.** Das erste Wort ist der Anbieter, wenn es einer von `omni-agent anbieter` ist. Fehlt er, frage kurz, welchen; `omni-agent doctor` zeigt, für welche ein Schlüssel gesetzt ist. Nimm keinen Anbieter ohne Schlüssel.
2. **Datenschutz prüfen, bevor etwas startet.** Der Datenort steht in `omni-agent anbieter` (DeepSeek: China). Enthält der Auftrag personenbezogene Daten, Zugangsdaten, Firmen-Interna oder Dateiinhalte, die die Nutzerin nicht ausdrücklich freigegeben hat, frage vorher nach. Für Personenbezug: `ollama` (lokal) oder `eurouter`.
3. **Auftrag formulieren.** Ein Ziel, ein erwartetes Ergebnis, kein Verweis auf diese Unterhaltung (der Agent kennt sie nicht). Kurz: `--text "…"`. Lang: Datei schreiben und den Pfad übergeben.
4. **Im Hintergrund starten.** Rufe das Bash-Werkzeug mit `run_in_background: true` auf:

   ```
   omni-agent run --anbieter <anbieter> --text "<auftrag>"
   ```

   Nützliche Zusätze: `--modell <name>` (OpenRouter und EUrouter verlangen ihn), `--runner opencode` (für EUrouter, Nvidia), `--max-runden 12`, `--zeit 900`.
   Werkzeuge: Standard ist lesen, schreiben, Websuche, Abruf. **`--werkzeuge +shell` nur, wenn die Nutzerin es ausdrücklich verlangt**, und dann mit dem Hinweis, dass Websuche Fremdtext liefert, der den Agenten lenken kann.
5. **Eine Zeile an die Nutzerin:** Agent gestartet (Anbieter, Modell), Laufordner. Nicht abfragen, nicht warten: Du wirst geweckt, wenn der Lauf endet.
6. **Wenn der Lauf endet:** `bericht.md` im Laufordner lesen und das Ergebnis zusammenfassen. Stellen, die der Agent als „nicht belegt" markiert hat, so weitergeben. Gibt es keinen Bericht: `omni-agent status --json`, dann `fehler.log` und `log.jsonl` im Laufordner ansehen und den Grund nennen (Exit 2 Konfiguration, 3 Endpunkt, 124 Zeitlimit).

## Regeln

- Frage **nie** nach einem API-Schlüssel im Chat und gib nie den Inhalt von `~/.omni-agent/env` aus. Fehlt ein Schlüssel, verweise auf `/omni-agent:setup`.
- Das Ergebnis eines Fremdmodells ist ein Entwurf, keine Tatsache. Prüfe, bevor es weiterverwendet wird.
