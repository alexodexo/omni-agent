# Änderungen

## 1.1.1

Größte Änderung seit dem Start: Omni-Agent arbeitet nach dem Vorbild des Codex-Plugins. **Bruchstelle:** Die Skills `run`, `review`, `status`, `doctor`, `setup` und `delegieren` sind Befehle bzw. der Subagent geworden. Aufrufe wie `/omni-agent:run` bleiben gleich, aber `run` startet jetzt über den Subagenten `omni-agent:lauf`, und Läufe starten losgelöst.

Neu:

- **Subagent `omni-agent:lauf`** (dünner Weiterleiter). Claude kann ihn von selbst rufen, auch in `/goal`; der Hauptchat bleibt sauber, Claude Code meldet das Ende.
- **Befehle** statt Skills: `run`, `review`, `adversarial-review`, `status`, `result`, `cancel`, `konten`, `doctor`, `setup`. Status, Ergebnis, Abbrechen, Prüfen, Konten laufen ohne Modell dazwischen.
- **Interne Skills** für Laufzeitvertrag, Auftrag schreiben und Ergebnisweitergabe.
- **Losgelöste Läufe:** `omni-agent run --hintergrund` / `--warten SEK`, `omni-agent warte`. Läufe überleben das Ende des startenden Befehls.
- **Sitzungen:** Hooks ordnen Läufe der Claude-Sitzung zu; `status`, `result`, `cancel` und `fortsetzbar` beziehen sich zuerst darauf. `SessionEnd` beendet noch laufende Läufe der Sitzung.
- **Rückfrage „fortsetzen oder neu?"** bei `/omni-agent:run`.
- **Projektmodus:** `--projekt` (nur lesen) und `--schreibend` für Claude-Konten und Codex; Codex läuft dann in der Sandbox `read-only` bzw. `workspace-write`.
- **Review-Vertrag:** festes Berichtsgerüst (Urteil, Befunde mit Schwere, Stelle, Sicherheit, Empfehlung, nächste Schritte); gegnerische Haltung nach Codex-Vorbild; bei sauberem Arbeitsbaum Branch gegen Hauptzweig.
- **Review-Gate (aus):** `setup --review-gate an` prüft vor dem Beenden einer Sitzung neue Änderungen.
- Statustabelle als Markdown (`status --md`).
