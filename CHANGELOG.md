# Änderungen

## 1.2.0

- **Projektmodus für jeden Anbieter.** Die Sperre für Fremdanbieter ist weg; `--projekt` und `--schreibend` gelten mit DeepSeek, Kimi, Ollama und allen anderen. Die Entscheidung, welche Daten wohin gehen, liegt bei der Nutzerin. Mit opencode wird die Schlussantwort jetzt ebenfalls zum Bericht.
- **Nutzung und Guthaben:** `omni-agent nutzung` und `/omni-agent:nutzung`. Codex (Plan, Auslastung je Fenster, Reset, Guthaben, Reset-Gutschriften über `codex app-server`), DeepSeek, Kimi, OpenRouter und EUrouter (Guthaben), Claude-Konten wie bisher.
- **Fernziele:** `omni-agent host add|list|remove|test|install|setup` und `--host NAME` für `run`, `status`, `result`, `cancel`, `warte`, `nutzung`, `doctor`. Läuft per ssh, auch über Tailscale. `/omni-agent:hosts`.
- **Python 3.9** reicht jetzt (die Version, die macOS mitbringt).

## 1.1.1

Größte Änderung seit dem Start: Omni-Agent arbeitet nach dem Vorbild des Codex-Plugins. **Bruchstelle:** Die Skills `run`, `review`, `status`, `doctor`, `setup` und `delegieren` sind Befehle bzw. der Subagent geworden. Aufrufe wie `/omni-agent:run` bleiben gleich, aber `run` startet jetzt über den Subagenten `omni-agent:lauf`, und Läufe starten losgelöst.

Neu:

- **Subagent `omni-agent:lauf`** (dünner Weiterleiter). Claude kann ihn von selbst rufen, auch in `/goal`; der Hauptchat bleibt sauber, Claude Code meldet das Ende.
- **Befehle** statt Skills: `run`, `review`, `adversarial-review`, `status`, `result`, `cancel`, `konten`, `doctor`, `setup`. Status, Ergebnis, Abbrechen, Prüfen, Konten laufen ohne Modell dazwischen.
- **Interne Skills** für Laufzeitvertrag, Auftrag schreiben und Ergebnisweitergabe.
- **Losgelöste Läufe:** `omni-agent run --hintergrund` / `--warten SEK`, `omni-agent warte`. Läufe überleben das Ende des startenden Befehls.
- **Sitzungen:** Hooks ordnen Läufe der Claude-Sitzung zu; `status`, `result`, `cancel` und `fortsetzbar` beziehen sich zuerst darauf. `SessionEnd` beendet noch laufende Läufe der Sitzung.
- **Rückfrage „fortsetzen oder neu?"** bei `/omni-agent:run`.
- **Projektmodus:** `--projekt` (nur lesen) und `--schreibend` für jeden Anbieter; Codex läuft dann in der Sandbox `read-only` bzw. `workspace-write`.
- **Review-Vertrag:** festes Berichtsgerüst (Urteil, Befunde mit Schwere, Stelle, Sicherheit, Empfehlung, nächste Schritte); gegnerische Haltung nach Codex-Vorbild; bei sauberem Arbeitsbaum Branch gegen Hauptzweig.
- **Review-Gate (aus):** `setup --review-gate an` prüft vor dem Beenden einer Sitzung neue Änderungen.
- Statustabelle als Markdown (`status --md`).
