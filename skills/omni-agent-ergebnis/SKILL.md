---
name: omni-agent-ergebnis
description: Interne Regeln dafür, wie Berichte, Reviews und Statusmeldungen von Omni-Agent der Nutzerin gezeigt werden. Laden, sobald eine Ausgabe von omni-agent vorliegt.
user-invocable: false
---

# Ergebnisse von Omni-Agent weitergeben

Wenn `omni-agent` oder der Subagent `omni-agent:lauf` eine Ausgabe liefert:

- Behalte Gliederung, Urteil, Befunde und nächste Schritte so, wie sie kommen. Keine Neufassung, keine Kürzung ohne Anlass.
- Bei Reviews zuerst die Befunde, nach Schwere geordnet. Dateinamen und Zeilen exakt wie berichtet.
- Behalte die Beweisgrenzen: Was der Agent als Vermutung, „nicht belegt", Annahme oder offene Frage kennzeichnet, bleibt so erkennbar.
- Gibt es keine Befunde, sage das ausdrücklich und halte den Restrisikosatz kurz.
- Hat der Agent Dateien geändert (Projektmodus mit `--schreibend`), sage das und nenne die Dateien, wenn der Bericht sie nennt.
- Ein Fremdmodell liefert Behauptungen. Prüfe einen Befund am Code, bevor du ihn als Fehler bestätigst.
- **Nach der Ausgabe von Review-Befunden anhalten.** Ändere nichts und behebe nichts, bevor die Nutzerin gesagt hat, welche Befunde sie behoben haben will. Auch nicht, wenn die Lösung offensichtlich ist.
- Scheitert ein Lauf (`[fehler]`, `[abgebrochen]`, kein Bericht): nenne die verwertbarsten Zeilen und halte an. Mach daraus keinen eigenen Umsetzungsversuch. Wurde der Agent nie erfolgreich gestartet, erfinde keine Ersatzantwort.
- Verlangt die Ausgabe Einrichtung oder Anmeldung: verweise auf `/omni-agent:setup` und improvisiere keinen anderen Anmeldeweg. Frage nie im Chat nach einem Schlüssel.
- Nachfragen an denselben Agenten: `/omni-agent:run --fortsetzen …`. Abbrechen: `/omni-agent:cancel`.
