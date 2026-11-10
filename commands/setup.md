---
description: Richtet Omni-Agent ein (Ordner, Schlüsseldatei, Befehl, Prüfung) und schaltet auf Wunsch das Review-Gate vor dem Beenden ein oder aus
argument-hint: '[--anbieter ID] [--review-gate an|aus]'
allowed-tools: Bash(python3:*), AskUserQuestion
---

!`python3 "${CLAUDE_PLUGIN_ROOT}/bin/omni-agent" setup $ARGUMENTS`

Erkläre das Ergebnis kurz: welche Agent-CLI gefunden wurde, welche Anbieter einen Schlüssel oder Login haben, was fehlt.

Regeln:

- **Schlüssel trägt die Nutzerin selbst ein.** Nenne ihr den Pfad `~/.omni-agent/env` und die Zeile `NAME=wert` (der Name steht in der Ausgabe von `setup --anbieter ID`). Frage nie im Chat nach dem Schlüssel, schreibe ihn nie selbst in eine Datei, lies die Datei nie aus.
- Ist keine Agent-CLI installiert, sage das klar und nenne `claude`, `codex` oder `opencode` als Möglichkeit. Installiere nichts ohne ausdrücklichen Wunsch.
- Ist Codex installiert, aber nicht angemeldet, verweise auf `codex login` im Terminal (zum Beispiel `!codex login` im Chat) und improvisiere keinen anderen Weg.
- Mehrere Claude-Konten: Jedes bekommt einen Namen (`omni-agent konto add NAME --art api|token`). Den Schlüssel gibt die Nutzerin im Terminal ein. Ein Abo-Token für unbeaufsichtigte Läufe ist bei Anthropic nicht ausdrücklich erlaubt: sage das, bevor sie sich dafür entscheidet.
- **Review-Gate** (`--review-gate an`): Vor dem Beenden einer Claude-Sitzung wird jeder neue Stand ungeprüfter Änderungen an das Standardkonto gesendet und kann das Beenden einmal aufhalten. Das kostet Nutzung und der Diff verlässt den Rechner. Schalte es nur auf ausdrücklichen Wunsch ein und sage das dazu.
- Fehlt Python 3.10 oder neuer, sage es klar: Omni-Agent braucht es (macOS, Linux, WSL).
- Anbieter ohne Claude-Format (EUrouter, Nvidia) laufen mit `--runner opencode` oder über das Extra LiteLLM (`omni-agent extras litellm install`, nur auf Wunsch).
