# Omni-Agent: Hinweise für Agenten, die am Repo arbeiten

Omni-Agent ist ein Python-Kern (`bin/omni-agent`, `lib/omni-agent/`, nur Standardbibliothek) mit einer dünnen Claude-Code-Plugin-Hülle (`.claude-plugin/`, `skills/`). Sprache im Repo, in Commits und Tests: Deutsch.

## Aufbau

| Ort | Inhalt |
|---|---|
| `bin/omni-agent` | Einstieg. Findet `lib/` über den eigenen Dateipfad (auch per Symlink); `${CLAUDE_PLUGIN_ROOT}` ist in Bash-Befehlen nicht gesetzt |
| `lib/omni-agent/lauf.py` | Lauf: wählen, starten, überwachen, `status.json` |
| `lib/omni-agent/runner/` | Ein Adapter je Agent-CLI (`claude`, `opencode`, `codex`, `dsh`), Passungsregel in `__init__.py` |
| `lib/omni-agent/anbieter.py` + `providers.json` | Anbieter als Daten |
| `lib/omni-agent/extras.py` + `extras/litellm/` | Optionaler Übersetzer, gepinnt mit Hash-Sperre |
| `skills/*/SKILL.md` | Slash-Befehle (Text für Claude, kein Code) |
| `tests/` | `python3 -m unittest discover -s tests -v` |

## Regeln

- **Neuer Anbieter:** Eintrag in `providers.json` (kein Code), `geprueft` nur auf `true`, wenn ein echter Lauf gelungen ist. Datenort in `region` und README-Tabelle ehrlich: unbekannt heißt „nicht belegt".
- **Neuer Runner:** Klasse in `runner/`, in `RUNNER` eintragen, Befehlsbau mit einem Test absichern. Experimentelle Runner nie in `AUTO_REIHENFOLGE`.
- **Schlüssel** nie im Repo, im Log, im Chat. Ein Runner bekommt nur die Schlüssel aus `LaufKontext.schluessel` (genau einer). Die Umgebung wird neu aufgebaut (`grundumgebung()`), nie vererbt.
- **Fertig heißt `bericht.md` vorhanden.** Der Exit-Code des Runners ist nur ein Zusatzsignal.
- **Was ein Runner nicht kann, wird verweigert**, nicht still weggelassen (`loese_werkzeuge`). Nur Standard-Werkzeuge dürfen still schrumpfen.
- **Version:** `lib/omni-agent/__init__.py` (`VERSION`) und `.claude-plugin/plugin.json` (`version`) bleiben gleich (Test). Wer `version` nicht erhöht, liefert Nutzerinnen kein Update.
- **LiteLLM-Pin** nur nach Lesen der Vorfallsseite des Herstellers ändern; Sperrdatei mit Hashes neu erzeugen (`uv pip compile --generate-hashes`).
- Vor jedem Commit: Tests und `claude plugin validate --strict .`. Vor jeder Veröffentlichung: Geheimnis-Scan des Baums **und** der Git-Historie.
- Keine Zeitschätzungen in Plänen; nur Reihenfolge und Tore.
