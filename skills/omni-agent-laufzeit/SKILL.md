---
name: omni-agent-laufzeit
description: Interner Vertrag für den Subagenten omni-agent:lauf: exakte Befehlssyntax, Warteschleife, Projektmodus, Anbieterwahl. Nicht direkt aufrufen.
user-invocable: false
---

# Omni-Agent-Laufzeit

Nur für den Subagenten `omni-agent:lauf`. Er ist ein Weiterleiter, kein Planer.

## Befehl

`omni-agent` liegt im PATH, solange das Plugin aktiv ist. Fehlt es, nimm `python3 "${CLAUDE_PLUGIN_ROOT}/bin/omni-agent"` an derselben Stelle.

```
omni-agent run --warten 540 [--konto NAME | --anbieter ID] [--modell M] [--aufwand low|medium|high] [--projekt] [--schreibend] [--fortsetzen] --text "Auftragstext"
omni-agent warte LAUF --max 540
```

| Teil | Bedeutung |
|---|---|
| `--warten 540` | Lauf losgelöst starten, höchstens 540 s auf das Ende warten, dann den Stand melden. Immer setzen. |
| `--text "…"` | Auftragstext. Lang? Datei schreiben und den Pfad als Argument statt `--text` übergeben. **Es gibt kein `--auftrag`.** |
| `--konto NAME` | Claude-Konto (fbs, felipe, llc, siehe `omni-agent konto list`). |
| `--anbieter ID` | Fremdanbieter oder `codex`. Nur, wenn die Nutzerin ihn genannt hat. |
| `--modell`, `--aufwand` | Nur auf ausdrücklichen Wunsch. `--aufwand` gilt nur für Codex. |
| `--projekt` | Der Agent arbeitet im Projektordner (aktuelles Verzeichnis), standardmäßig nur lesend. Nur mit Claude-Konten und Codex. |
| `--schreibend` | Mit `--projekt`: Dateien im Projekt dürfen geändert werden. Nur, wenn die Nutzerin Änderungen ausdrücklich will. |
| `--fortsetzen` | Nachfrage an den letzten Agenten (ohne Namen: letzter Lauf dieser Sitzung). `--text` ist die Nachfrage. |

Bash-Aufrufe immer mit `timeout: 600000` (10 Minuten, das Maximum).

## Ablauf

1. Ein `run`-Aufruf. Die Ausgabe beginnt mit `Gestartet: <lauf>` und endet mit einer Meldung.
2. Erste Meldungszeile `[läuft noch]`: `omni-agent warte <lauf> --max 540` wiederholen, bis sich die Zeile ändert.
3. `[fertig]`, `[fehler]` oder `[abgebrochen]`: gesamte Ausgabe unverändert zurückgeben. Nicht zusammenfassen, nicht kommentieren.

## Anbieterwahl

- Keine Angabe der Nutzerin: weder `--konto` noch `--anbieter`. Dann gilt der Standard der Nutzerin.
- Ein Fremdanbieter wird **nie** von dir gewählt.
- Projektmodus: Bezieht sich der Auftrag auf Dateien oder Code des Projekts und der Anbieter ist ein Claude-Konto, Codex oder der Standard, setze `--projekt`. Mit einem Fremdanbieter geht das nicht (der Befehl verweigert es).

## Nicht tun

- Kein `review`, `status`, `result`, `cancel`, `konto`, `setup` oder `doctor`.
- Keine eigene Arbeit am Projekt, keine Datei lesen, nicht nachsehen, ob der Lauf läuft (das macht `warte`).
- Nie einen Schlüssel ausgeben oder nach einem fragen.
