# Omni-Agent

Hintergrund-Agents mit **austauschbarem Modell-Anbieter** und **austauschbarer Agent-CLI**.

Du gibst einen Auftrag, Omni-Agent startet damit einen zweiten Agenten (zum Beispiel mit DeepSeek, Kimi oder einem lokalen Ollama-Modell), wartet, bis dieser `bericht.md` geschrieben hat, und gibt dir den Bericht zurück. Dein Haupt-Claude arbeitet währenddessen weiter.

```
Claude Code (du)  ──/omni-agent:run──►  omni-agent run
                                         ├─ Anbieter  (wessen Modell, wo, welcher Schlüssel)
                                         └─ Runner    (welche Agent-CLI führt aus)
                                              ▼
                              ~/.omni-agent/laeufe/<zeit>-<anbieter>/bericht.md
```

| Schicht | Auswahl | Standard |
|---|---|---|
| **Anbieter** | DeepSeek, OpenRouter, Kimi, Ollama, EUrouter, Nvidia, Claude mit anderem Konto | – |
| **Runner** | Claude Code, opencode, codex, dsh (experimentell) | Claude Code |

## Installieren

**Schnellster Weg:** Gib Claude Code diese Repo-Adresse und sage „Installiere mir das". Claude folgt dann [INSTALL.md](INSTALL.md).

**Oder selbst, als Claude-Code-Plugin:**

```
/plugin marketplace add alexodexo/omni-agent
/plugin install omni-agent@omni-agent
/omni-agent:setup
```

**Oder ohne Plugin** (funktioniert auch ohne Claude, im Terminal): Repo klonen, dann `bin/omni-agent setup`. Voraussetzung: Python 3.10 oder neuer (macOS, Linux, WSL) und mindestens eine Agent-CLI (Standard: [Claude Code](https://claude.com/claude-code)).

## Benutzen

| Befehl im Claude-Chat | Zweck |
|---|---|
| `/omni-agent:setup [anbieter]` | Einrichtung, Anleitung für einen Anbieter |
| `/omni-agent:doctor` | Was ist da, was fehlt |
| `/omni-agent:run deepseek <auftrag>` | Auftrag im Hintergrund ausführen |
| `/omni-agent:status` | Läufe und Berichte ansehen |

Dazu kennt Claude die Skill `delegieren`: Sie schlägt von selbst einen Hintergrundlauf vor, wenn eine Teilaufgabe sich dafür eignet. Gestartet wird nie ohne dein Ja.

Im Terminal:

```bash
omni-agent run --anbieter deepseek --text "Vergleiche drei Methoden zur Qualitätssicherung von Unterricht"
omni-agent run --anbieter nvidia --runner opencode auftrag.md
omni-agent status
```

## Schlüssel: nie im Chat

Schlüssel liegen in `~/.omni-agent/env` (Zeile `NAME=wert`, Rechte 600) oder in einer Umgebungsvariable. `omni-agent setup` legt die Datei an; **du trägst den Schlüssel selbst ein**. Claude fragt nie danach und liest die Datei nie aus. Omni-Agent verweigert die Datei, wenn andere sie lesen könnten.

## Anbieter und Datenschutz

**Alles, was du in einen Auftrag schreibst, geht an den Anbieter.** Schicke keine Teilnehmerdaten, Zugangsdaten oder Interna an einen Anbieter, dessen Datenort du nicht akzeptierst.

| Anbieter | Format | Datenort | Live getestet | Schlüssel |
|---|---|---|---|---|
| **deepseek** | Anthropic | **China**, Training vorgesehen | ja | `DEEPSEEK_API_KEY` |
| **openrouter** | Anthropic | nicht belegt | nein | `OPENROUTER_API_KEY` |
| **kimi** | Anthropic | nicht belegt | nein | `MOONSHOT_API_KEY` |
| **ollama** | Anthropic | **lokal**, bleibt auf dem Rechner | nein | keiner |
| **eurouter** | OpenAI | EU (laut Anbieter) | nein | `EUROUTER_API_KEY` |
| **nvidia** | OpenAI (nur Chat) | nicht belegt | nein | `NVIDIA_API_KEY` |
| **claude-konto** | Anthropic | Anthropic | nein | `ANTHROPIC_API_KEY` |

„Nein" heißt: nach Herstellerdokumentation eingebaut (Stand 28.10.2026), aber nicht von uns ausprobiert. Für Personenbezug: `ollama` oder `eurouter`. Eigene Anbieter: JSON-Datei in `~/.omni-agent/providers.d/` (gleiches Schema wie [providers.json](providers.json)).

### Claude mit anderem Konto

Empfohlen ist ein **API-Schlüssel** (`ANTHROPIC_API_KEY`). Ein Abo-Token (`CLAUDE_CODE_OAUTH_TOKEN`) für unbeaufsichtigte Läufe ist bei Anthropic nicht ausdrücklich geregelt; ob das erlaubt ist, ist **nicht belegt**. Omni-Agent speichert diesen Token nie, es reicht ihn nur als Umgebungsvariable an das unveränderte `claude` durch. Die Entscheidung liegt bei dir.

## Anbieter und Runner passen zusammen

Jeder Anbieter spricht ein Format, jede CLI versteht nur manche.

| Anbieter | claude | opencode | codex |
|---|---|---|---|
| deepseek, openrouter, kimi, ollama | ja | ja | nein |
| eurouter | nur mit LiteLLM | ja | ja (Responses-Pfad nicht geprüft) |
| nvidia | nur mit LiteLLM | ja | nein |
| claude-konto | ja | – | – |

`omni-agent run` nimmt ohne `--runner` den ersten **installierten** passenden Runner (claude, opencode, codex). `omni-agent doctor` zeigt die Matrix für deinen Rechner. Passt nichts, sagt es dir, was fehlt.

**Runner-Stand:** `claude` ist live getestet. `opencode` und `codex` sind nach Herstellerdokumentation gebaut, aber nicht ausprobiert. `dsh` (DeepSeek Harness) ist eine Developer Preview und läuft nur, wenn du `--runner dsh` ausdrücklich nennst.

### Optional: LiteLLM als Übersetzer

Nur nötig, wenn Claude Code gegen einen reinen OpenAI-Anbieter laufen soll. Meist ist `--runner opencode` der bessere Weg. `omni-agent extras litellm install` legt LiteLLM in eine eigene Umgebung (fest gepinnte Version, Hash-Prüfung); gestartet wird es mit `--ueber-litellm`. Der Proxy lauscht nur auf 127.0.0.1 und bekommt nur den einen Schlüssel des Anbieters. Hintergrund: Die Version 1.107.0 von LiteLLM war am 21.10.2026 kompromittiert; Omni-Agent pinnt davor.

## Sicherheit

| Maßnahme | Wirkung |
|---|---|
| Saubere Umgebung (`env -i` plus Nötigstes) | Dein Login und deine Base-URL rutschen nicht in den Fremdagenten |
| Nur der eine benötigte Schlüssel | Kein anderer Anbieter-Schlüssel erreicht den Lauf |
| Claude-Runner: `--setting-sources project`, `--strict-mcp-config`, `--no-session-persistence`, `dontAsk`, leerer Arbeitsordner | Keine fremden Hooks, MCP-Server oder Sitzungen |
| Standard **ohne Shell** | Websuche kann Fremdtext liefern, der den Agenten lenkt. `--werkzeuge +shell` nur bewusst |
| Schlüssel werden in `log.jsonl` und `fehler.log` geschwärzt | Kein Schlüssel im Log |
| Zeitlimit (900 s) und Rundenobergrenze | Ein hängender Lauf wird samt Kindprozessen beendet |

Ein Lauf ist **fertig, wenn `bericht.md` existiert**. Der Exit-Code des Runners ist nur ein Zusatzsignal. Omni-Agent-Exit: 0 fertig, 1 Fehler im Lauf, 2 Konfiguration, 3 Endpunkt nicht erreichbar, 124 Zeitlimit.

Das Ergebnis eines Fremdmodells ist ein Entwurf. Prüfe Aussagen, die der Agent als „nicht belegt" markiert hat. Die „Kosten laut CLI" im Fortschritt rechnet Claude Code mit eigenen Preisen; die echten Kosten stehen beim Anbieter.

## Entwickeln

```bash
python3 -m unittest discover -s tests -v     # Kern, Passung, Runner-Befehle, Ende-zu-Ende mit Attrappe
claude plugin validate --strict .            # Plugin und Marketplace
claude --plugin-dir .                        # Plugin lokal laden, /reload-plugins nach Änderungen
```

Architektur und Hintergründe: [docs/02-architektur.md](docs/02-architektur.md), Plugin-Grundlagen: [docs/01-plugin-handbuch.md](docs/01-plugin-handbuch.md). Mitarbeit für Agenten: [AGENTS.md](AGENTS.md).

## Lizenz

[MIT](LICENSE)
