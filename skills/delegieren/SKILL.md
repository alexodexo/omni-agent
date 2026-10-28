---
description: Schlägt vor, eine abgrenzbare Teilaufgabe (Recherche, Vergleich, Entwurf, Zweitmeinung) von einem Omni-Agent-Hintergrundlauf mit anderem Modell erledigen zu lassen, wenn Kosten, Parallelität oder Modellvielfalt das nahelegen
---

# Wann Omni-Agent sinnvoll ist

Schlage einen Hintergrundlauf **vor** (starte nie ohne Zustimmung), wenn eine Teilaufgabe

- sich in einem Satz beschreiben lässt und ein klares Ergebnis hat (Recherche, Vergleich, Entwurf, Zweitmeinung),
- unabhängig vom Rest der Unterhaltung ist und parallel laufen kann,
- günstig oder mit einem anderen Modell sinnvoller ist als mit diesem,
- **keine** personenbezogenen Daten, Zugangsdaten oder Interna braucht.

Nicht geeignet: Aufgaben, die den Kontext dieser Unterhaltung brauchen, die schreibend in fremde Systeme eingreifen oder bei denen Fehler teuer sind.

# Vorgehen

1. `omni-agent doctor` prüfen, ob ein Anbieter mit Schlüssel bereitsteht. Wenn nicht: auf `/omni-agent:setup` verweisen und die Aufgabe selbst erledigen.
2. Der Nutzerin in zwei Zeilen vorschlagen: Welche Aufgabe, welcher Anbieter, wo liegen die Daten (`omni-agent anbieter`).
3. Nach ihrem Ja den Ablauf von `/omni-agent:run` anwenden (Hintergrund starten, nicht pollen, Bericht lesen und einordnen).
