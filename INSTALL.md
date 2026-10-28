# Installation durch einen Agenten

**Für Claude Code (oder einen anderen Agenten), wenn die Nutzerin sagt „Installiere mir Omni-Agent" oder „Geh mit mir die Installation durch".**
Arbeite die Schritte in dieser Reihenfolge ab. Führe nichts aus, was hier nicht steht. Schlüssel fragst du **nie** im Chat ab.

## 1. Voraussetzungen prüfen

```bash
python3 --version      # 3.10 oder neuer nötig
claude --version       # Standard-Runner
```

- Python fehlt oder ist zu alt: sage es der Nutzerin und stoppe. Plattformen: macOS, Linux, WSL.
- `claude` fehlt: Claude Code muss installiert sein, sonst gibt es keinen Standard-Runner. Alternative Runner (opencode, codex) nur auf Wunsch.

## 2. Plugin installieren (empfohlen)

```bash
claude plugin marketplace add alexodexo/omni-agent
claude plugin install omni-agent@omni-agent
```

Danach in Claude Code `/reload-plugins` (oder neu starten). Prüfe: `claude plugin list` zeigt `omni-agent@omni-agent` als enabled.

*Ohne Plugin:* Repo klonen und `bin/omni-agent` direkt benutzen. Alle Befehle unten gelten gleich.

## 3. Einrichten

```bash
omni-agent setup
```

(Falls `omni-agent` noch nicht im PATH ist: `"<Plugin- oder Repo-Ordner>/bin/omni-agent" setup`. Im Plugin ist das `${CLAUDE_PLUGIN_ROOT}/bin/omni-agent`.)

Der Befehl legt `~/.omni-agent/` und die Schlüsseldatei `~/.omni-agent/env` (Rechte 600) an, verlinkt `omni-agent` nach `~/.local/bin` und prüft den Rechner. Fasse das Ergebnis für die Nutzerin kurz zusammen.

## 4. Anbieter wählen und Schlüssel eintragen

Frage die Nutzerin, welchen Anbieter sie nutzen will (`omni-agent anbieter` listet sie mit Datenort). Nenne vor der Wahl den **Datenort** (zum Beispiel DeepSeek: China) und dass nichts Personenbezogenes oder Internes in Aufträge gehört.

```bash
omni-agent setup --anbieter <anbieter>
```

Das druckt, welche Zeile in `~/.omni-agent/env` fehlt. **Die Nutzerin trägt den Schlüssel selbst ein**, in ihrem Editor. Du schreibst ihn nicht, liest die Datei nicht aus und fragst nicht im Chat danach.

## 5. Prüfen

```bash
omni-agent doctor
```

Erwartet: der gewählte Anbieter zeigt „Schlüssel: gesetzt" und einen installierten passenden Runner. Zeigt der Anbieter „keiner davon installiert" (zum Beispiel EUrouter oder Nvidia), brauchen sie `opencode` oder das Extra LiteLLM (`omni-agent extras litellm install`, nur auf Wunsch).

## 6. Probelauf

Mit Zustimmung der Nutzerin einen kleinen, harmlosen Auftrag:

```bash
omni-agent run --anbieter <anbieter> --text "Nenne in drei Stichpunkten, wofür ein Hintergrund-Agent nützlich ist." --max-runden 3 --werkzeuge lesen,schreiben
```

Erfolg: Exit 0 und `Bericht: …/bericht.md`. Lies den Bericht und zeige ihn kurz. Misserfolg: Exit-Code lesen (2 Konfiguration, 3 Endpunkt nicht erreichbar, 124 Zeitlimit) und `fehler.log` im Laufordner ansehen.

## 7. Fertig

Sage der Nutzerin, wie es weitergeht: `/omni-agent:run <anbieter> <auftrag>`, `/omni-agent:status`, `/omni-agent:doctor`. Erwähne, dass Ergebnisse von Fremdmodellen Entwürfe sind.

## Was du nicht tust

- Keinen Schlüssel erfragen, ausgeben, in eine Datei schreiben oder in einen Befehl einsetzen.
- `--werkzeuge +shell` nur auf ausdrücklichen Wunsch.
- Keinen Abo-Token (`CLAUDE_CODE_OAUTH_TOKEN`) empfehlen: ob unbeaufsichtigte Läufe damit zulässig sind, ist nicht belegt. Empfohlen ist ein API-Schlüssel.
- Das Extra LiteLLM nur installieren, wenn die Nutzerin es will.
