# Mitmachen

Schön, dass du helfen willst. Der Kern ist Python-Standardbibliothek ohne Abhängigkeiten, das soll so bleiben.

## Loslegen

```bash
git clone https://github.com/alexodexo/omni-agent && cd omni-agent
python3 -m unittest discover -s tests -v     # Kein Test spricht mit einem echten Anbieter
claude plugin validate --strict .            # Plugin und Marketplace
claude --plugin-dir .                        # Plugin lokal laden, /reload-plugins nach Änderungen
```

## Regeln

1. **Neue Flags zuerst im Parser** (`lib/omni_agent/cli.py`), erst dann in `commands/`, `agents/` oder `skills/` dokumentieren. Ein Test prüft jeden dokumentierten Befehl gegen den echten Parser.
2. **Tests mitschreiben.** Neues Verhalten bekommt einen Test, der ohne Netz und ohne echten Anbieter läuft (Attrappe statt echtem `claude`).
3. **Version gleich halten** in `lib/omni_agent/__init__.py` und `.claude-plugin/plugin.json`, und erhöhen, wenn Nutzer die Änderung bekommen sollen. Sonst gibt es für sie kein Update. Ein Test prüft die Gleichheit.
4. **Ehrlich markieren, was geprüft ist.** `geprueft: true` in `providers.json` heißt: live ausprobiert, nicht nur aus der Doku gelesen.
5. **Keine Schlüssel, keine persönlichen Pfade** in Code, Tests, Doku oder Commit.

## Neuen Anbieter hinzufügen

Eine JSON-Datei nach dem Schema von [providers.json](providers.json), zum Ausprobieren in `~/.omni-agent/providers.d/`. Für die Aufnahme ins Repo: Herstellerdokumentation verlinken, Datenort angeben und den Anbieter einmal live durchlaufen lassen.

Mehr zum Aufbau: [docs/02-architektur.md](docs/02-architektur.md) und [AGENTS.md](AGENTS.md).
