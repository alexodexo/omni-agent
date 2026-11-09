---
description: Startet einen Hintergrund-Agent über Omni-Agent für einen Auftrag und liefert einen Bericht. Nur nutzen, wenn die Nutzerin Omni-Agent, einen Anbieter (DeepSeek, OpenRouter, Kimi, Ollama, EUrouter, Codex) oder ein Claude-Konto (fbs, felipe, llc) ausdrücklich nennt oder verlangt; auch in einem /goal erlaubt, wenn das Ziel es so vorgibt
argument-hint: "[anbieter] [auftrag]"
allowed-tools: Bash(omni-agent *)
---

# Omni-Agent: Auftrag im Hintergrund ausführen

Eingabe der Nutzerin: `$ARGUMENTS`

## Ablauf

1. **Anbieter oder Konto klären.** Nennt die Nutzerin ein Claude-Konto (`fbs`, `felipe`, `llc`, siehe `omni-agent konto list`), nimm `--konto <name>`. Nennt sie einen Fremdanbieter, nimm `--anbieter <id>` (Liste: `omni-agent anbieter`). Nennt sie **Codex** oder OpenAI, nimm `--anbieter codex` (nutzt die Anmeldung der Codex-CLI; `omni-agent doctor` zeigt, ob sie angemeldet ist; `--aufwand low|medium|high` steuert den Denkaufwand). Nennt sie nichts, **frage nicht nach**: Prüfe mit `omni-agent konto standard`, ob ein Standard gesetzt ist, und lass `--konto`/`--anbieter` weg, dann läuft der Standard. Nur wenn dort „keiner gesetzt“ steht, frage kurz. Nimm keinen Anbieter ohne Schlüssel (`omni-agent doctor`). Ein Fremdanbieter wird nie stillschweigend als Standard gewählt.
   Vor einem Lauf auf einem Abo-Konto kann `omni-agent konto list` die Auslastung zeigen: Ist ein Konto fast an seiner Grenze, nenne das und schlage ein anderes vor.
2. **Datenschutz prüfen, bevor etwas startet** (bei einem Claude-Konto genügt der Gedanke an fremde Kontingente; Datenort ist Anthropic wie hier). Der Datenort steht in `omni-agent anbieter` (DeepSeek: China). Enthält der Auftrag personenbezogene Daten, Zugangsdaten, Firmen-Interna oder Dateiinhalte, die die Nutzerin nicht ausdrücklich freigegeben hat, frage vorher nach. Für Personenbezug: `ollama` (lokal) oder `eurouter`.
3. **Auftrag formulieren.** Ein Ziel, ein erwartetes Ergebnis, kein Verweis auf diese Unterhaltung (der Agent kennt sie nicht). Kurz: `--text "…"`. Lang: Datei schreiben und den Pfad übergeben.
4. **Im Hintergrund starten.** Rufe das Bash-Werkzeug mit `run_in_background: true` auf:

   ```
   omni-agent run [--konto <name> | --anbieter <id>] --text "<auftrag>"
   ```

   Nützliche Zusätze: `--modell <name>` (OpenRouter und EUrouter verlangen ihn), `--runner opencode` (für EUrouter, Nvidia), `--max-runden 12`, `--zeit 900`.
   Werkzeuge: Standard ist lesen, schreiben, Websuche, Abruf. **`--werkzeuge +shell` nur, wenn die Nutzerin es ausdrücklich verlangt**, und dann mit dem Hinweis, dass Websuche Fremdtext liefert, der den Agenten lenken kann.
5. **Eine Zeile an die Nutzerin:** Agent gestartet (Anbieter, Modell), Laufordner. Nicht abfragen, nicht warten: Du wirst geweckt, wenn der Lauf endet.
6. **Wenn der Lauf endet:** `omni-agent result` zeigt `bericht.md` (oder die Datei im Laufordner lesen). Fasse das Ergebnis zusammen. Stellen, die der Agent als „nicht belegt" markiert hat, und seine Annahmen gibst du so weiter. Gibt es keinen Bericht: `omni-agent status --json`, dann `fehler.log` und `log.jsonl` ansehen und den Grund nennen (Exit 2 Konfiguration, 3 Endpunkt, 124 Zeitlimit). Führe den Auftrag in dem Fall **nicht selbst als Ersatz** aus; berichte den Fehler und halte an.
7. **Nachfragen und Abbrechen.**
   - Nachfrage an denselben Agenten (er behält seinen Verlauf): `omni-agent run --fortsetzen --text "Nachfrage"` (der letzte Lauf) oder `--fortsetzen <Teil des Laufnamens>`; Anbieter, Modell und Ordner bleiben, `bericht.md` wird aktualisiert.
   - Abbrechen: `omni-agent cancel` (der laufende Lauf) oder mit Teil des Laufnamens.

## Regeln

- Frage **nie** nach einem API-Schlüssel im Chat und gib nie den Inhalt von `~/.omni-agent/env` aus. Fehlt ein Schlüssel, verweise auf `/omni-agent:setup`.
- Das Ergebnis eines Fremdmodells ist ein Entwurf, keine Tatsache. Prüfe, bevor es weiterverwendet wird.
- Wendet ein Bericht Änderungen am Code oder an Daten nahe, führe sie nicht von dir aus durch. Frage zuerst, welche gewünscht sind.
- Für eine Zweitmeinung zu Codeänderungen gibt es `/omni-agent:review`.
