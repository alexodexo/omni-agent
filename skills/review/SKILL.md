---
description: Lässt die Git-Änderungen im aktuellen Repo von einem anderen Modell oder Konto prüfen (Zweitmeinung, optional gegnerisch). Nur nutzen, wenn die Nutzerin ein Review, eine Zweitmeinung oder Omni-Agent für Code ausdrücklich verlangt. Der Diff verlässt den Rechner.
argument-hint: "[konto|anbieter] [--base main] [--adversarial] [Schwerpunkt]"
allowed-tools: Bash(omni-agent *)
---

# Omni-Agent: Zweitmeinung zu den Codeänderungen

Eingabe der Nutzerin: `$ARGUMENTS`

## Ablauf

1. **Vorschau, ohne etwas zu senden.** Rufe `omni-agent review --vorschau` mit den Optionen der Nutzerin auf (`--base main` für einen Branch, sonst alle Änderungen gegen HEAD). Es nennt Dateien, Größe und Warnungen. Meldet es „Geheimnisse", sende **nichts** und sage der Nutzerin, welche Datei betroffen ist.
2. **Freigabe holen, außer sie ist schon erteilt.** Sage in zwei Zeilen: wie viele Dateien an welchen Anbieter oder welches Konto gehen und wo dessen Daten liegen (`omni-agent anbieter`; Claude-Konten und Codex: beim jeweiligen Hersteller). Hat die Nutzerin Anbieter und Review ausdrücklich verlangt, ist das die Freigabe.
3. **Konto oder Anbieter.** Nennt sie `fbs`, `felipe`, `llc`: `--konto <name>`. Nennt sie Codex: `--anbieter codex`. Nennt sie nichts: nichts angeben, dann läuft der Standard (`omni-agent konto standard`).
4. **Im Hintergrund starten** (Bash mit `run_in_background: true`):

   ```
   omni-agent review [--konto <name> | --anbieter <id>] [--base <ref>] [--adversarial] [Schwerpunkt als Text]
   ```

   `--adversarial` stellt zusätzlich die gewählte Lösung infrage (Annahmen, Fehlermodi, einfachere Alternative). Eine Zeile an die Nutzerin: gestartet, Laufordner. Nicht abfragen.
5. **Wenn der Lauf endet:** `omni-agent result` zeigt den Bericht. Gib die Befunde **zuerst und nach Schwere geordnet** weiter, mit Datei und Zeile wie im Bericht. Vermutungen und „nicht belegt" bleiben als solche erkennbar. Gibt es keine Befunde, sage das ausdrücklich.

## Regeln

- **Nach der Ausgabe der Befunde anhalten.** Ändere nichts am Code, behebe nichts, bevor die Nutzerin gesagt hat, welche Befunde sie behoben haben will. Auch nicht, wenn die Lösung offensichtlich ist.
- Ein Befund eines Fremdmodells ist eine Behauptung. Prüfe ihn am Code, bevor du ihn als Fehler bestätigst.
- Scheitert der Lauf (kein Bericht), nenne den Grund (`omni-agent status`, `fehler.log`) und halte an. Mach das Review nicht selbst als Ersatz.
- Frage nie nach einem Schlüssel im Chat. Fehlt einer: `/omni-agent:setup`.
