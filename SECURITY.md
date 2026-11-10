# Sicherheit

## Lücke melden

Bitte **nicht** als öffentliches Issue. Nutze [Private Vulnerability Reporting](https://github.com/alexodexo/omni-agent/security/advisories/new) auf GitHub. Du bekommst eine Antwort, sobald es möglich ist.

## Was Omni-Agent schützt

- Jeder Lauf startet in einer sauberen Umgebung und bekommt nur den einen Schlüssel, den er braucht.
- Schlüssel liegen in `~/.omni-agent/env` (Rechte 600) und werden in Logs geschwärzt. Omni-Agent verweigert die Datei, wenn andere sie lesen können.
- Standard ohne Shell. Fremdanbieter laufen nie im Projektmodus.
- Der Review sendet nichts, wenn der Diff mögliche Geheimnisse oder `.env`-Dateien enthält.

Die vollständige Liste steht im Abschnitt [Sicherheit der README](README.md#sicherheit).

## Was nicht geschützt ist

Alles, was du in einen Auftrag schreibst, geht an den gewählten Anbieter. Den Datenort zeigt `omni-agent anbieter`.
