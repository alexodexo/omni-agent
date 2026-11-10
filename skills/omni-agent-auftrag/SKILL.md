---
name: omni-agent-auftrag
description: Interne Anleitung, wie ein Auftrag für einen Omni-Agent-Lauf geschrieben wird (Ziel, Kontext, Erledigt-Kriterium, Grenzen). Nur zum Schärfen des Auftragstexts, nicht zum eigenen Lösen.
user-invocable: false
---

# Auftrag für einen Omni-Agent-Lauf schreiben

Der Agent kennt weder diese Unterhaltung noch das, was du schon gelesen hast. Schärfe die Anfrage der Nutzerin nur so weit, dass er sie allein erledigen kann. Löse sie nicht selbst und untersuche das Projekt nicht dafür.

## Bausteine

Nimm nur, was die Aufgabe braucht, als kurze Abschnitte (XML-artige Tags oder Überschriften):

| Baustein | Inhalt |
|---|---|
| Ziel | Ein Satz: Was soll am Ende vorliegen? |
| Kontext | Nur Fakten, die der Agent nicht selbst findet: Fehlermeldung, Ort, was schon versucht wurde. Im Projektmodus gehören Dateipfade statt Dateiinhalte hinein. |
| Erledigt wenn | Das prüfbare Kriterium: „nennt die drei wahrscheinlichsten Ursachen mit Datei und Zeile". |
| Grenzen | Was er nicht tun soll: nichts ändern, nichts löschen, keine Annahmen über Daten außerhalb des Auftrags. |
| Form | Nur wenn nötig: Tabelle, Reihenfolge nach Gewicht. Der Berichtsrahmen des Laufs gibt die Grundgliederung schon vor. |

## Regeln

- Ein Auftrag, ein Ziel. Zwei unabhängige Fragen sind zwei Läufe.
- Positiv formulieren („nenne die Ursache mit Beleg") statt „rate nicht".
- Verlange Belege und die Trennung von Beobachtung und Vermutung. Das ist schon im Rahmen des Laufs, wiederhole es nicht.
- Keine Zugangsdaten, keine personenbezogenen Daten in den Text. Verweise auf Dateien im Projektmodus, statt sie abzuschreiben.
- Behalte die Worte der Nutzerin, wo sie präzise sind. Ergänze, ersetze nicht.
- Lange Aufträge in eine Datei schreiben und den Pfad übergeben.

## Beispiel

Anfrage der Nutzerin: „Schau, warum der Login manchmal hängt."

Auftrag: „Ziel: Ursachen für sporadisch hängenden Login finden. Kontext: Das Hängen tritt nach dem Wechsel der Sitzungsverwaltung auf; relevant sind vermutlich `app/auth/` und `lib/session.ts`. Erledigt wenn: bis zu drei Ursachen mit Datei und Zeile und je einer Prüfmöglichkeit genannt sind. Grenzen: nur lesen, nichts ändern."
