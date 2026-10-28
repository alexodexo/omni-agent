---
description: Richtet Omni-Agent ein oder führt durch die Einrichtung eines Anbieters (Schlüsseldatei, Befehl, Prüfung). Nutzen bei "Omni-Agent einrichten", "Omni-Agent installieren", "Anbieter hinzufügen"
argument-hint: "[anbieter]"
---

# Omni-Agent einrichten

Anbieter (optional): `$ARGUMENTS`

## Ablauf

1. **Einrichtung ausführen.** Der Befehl `omni-agent` liegt im PATH, sobald das Plugin aktiv ist. Sonst nimm den Pfad direkt:

   ```
   "${CLAUDE_PLUGIN_ROOT}/bin/omni-agent" setup
   ```

   Mit Anbieter: `… setup --anbieter <anbieter>`. Der Befehl legt `~/.omni-agent/` (Rechte 700) und die Schlüsseldatei `~/.omni-agent/env` (Rechte 600) an, verlinkt `omni-agent` nach `~/.local/bin` und prüft den Rechner.
2. **Ergebnis erklären**, kurz: welche Agent-CLI gefunden wurde, welche Anbieter einen Schlüssel haben, was fehlt.
3. **Schlüssel: die Nutzerin trägt ihn selbst ein.** Sage ihr den Pfad `~/.omni-agent/env` und die Zeile `NAME=wert` (der Name steht in der Ausgabe von `setup --anbieter`). Frage **nie** im Chat nach dem Schlüssel, schreibe ihn nie selbst in eine Datei und lies die Datei nie aus.
4. **Prüfen:** `omni-agent doctor`, danach ein kleiner Probelauf mit `/omni-agent:run`.

## Hinweise

- Fehlt Python 3.10 oder neuer, sage es klar: Omni-Agent braucht es (macOS, Linux, WSL).
- Anbieter ohne Claude-Format (EUrouter, Nvidia) laufen mit `--runner opencode` (muss installiert sein) oder über das optionale Extra LiteLLM (`omni-agent extras litellm install`). Das Extra nur installieren, wenn die Nutzerin es will.
- „Claude mit anderem Konto": ein API-Schlüssel ist der empfohlene Weg. Ein Abo-Token für unbeaufsichtigte Läufe ist bei Anthropic nicht ausdrücklich erlaubt. Sage das, bevor die Nutzerin sich dafür entscheidet.
