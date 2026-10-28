# Omni-Agent: Architektur

Stand: 28.10.2026. Grundlage: [`01-plugin-handbuch.md`](01-plugin-handbuch.md) und die geprüften Fakten in
[`recherche/anbieter-und-runner.md`](recherche/anbieter-und-runner.md). Stand der Umsetzung: Stufen 1 bis 8 sind gebaut (Kern, Anbieter, `doctor`/`setup`, Plugin, Runner `opencode`, `codex`, `dsh`, Extra LiteLLM). Live geprüft sind nur Runner `claude` mit Anbieter `deepseek` und die Plugin-Installation; alles andere folgt der Herstellerdoku und ist durch Tests der Befehlsbildung abgesichert. Stufe 9 (Veröffentlichung) steht aus.

## 1. Idee in einem Satz

Omni-Agent ist ein **Kern-Programm**, das einen Auftrag an einen **Runner** (Agent-CLI) mit einem **Anbieter** (Modell-Quelle)
übergibt und einen **Bericht** zurückliefert. Das Claude-Code-Plugin ist nur die **Hülle**, die den Kern bequem macht.

```
 Orchestrator (Claude Code, später Codex …)
   │  Slash-Befehl / Skill (nur Text)
   ▼
 omni-agent run auftrag.md --anbieter deepseek
   │
   ├─ Anbieter  ← providers.json   (Protokoll, URL, Key-Name, Modelle)
   ├─ Runner    ← lib/runner/*     (claude · opencode · codex · dsh)
   ├─ Passung   ← Protokoll des Anbieters × Protokolle des Runners
   └─ optional  ← Extra LiteLLM    (Übersetzer für Chat-Completions)
   ▼
 ~/.omni-agent/laeufe/<zeit>-<anbieter>/
   auftrag.md · bericht.md · log.jsonl · fehler.log · status.json
```

Zwei Schichten, zwei Austauschpunkte:

| Schicht | Austauschbar durch | Frage, die sie beantwortet |
|---|---|---|
| **Anbieter** | Eintrag in `providers.json` | „Wessen Modell, wo, mit welchem Schlüssel?“ |
| **Runner** | Adapter-Klasse in `lib/runner/` | „Welche Agent-CLI führt den Auftrag aus?“ |

Claude Code ist der **Standard-Runner**, aber keiner, an den man gebunden ist.

## 2. Warum ein Kern-Programm und kein MCP-Server

| Entscheidung | Begründung |
|---|---|
| `bin/omni-agent` als gewöhnlicher Befehl | Läuft ohne Plugin, ohne Claude, unter Codex, im Terminal. Das Plugin ist dann nur Komfort |
| Hintergrund über das **Bash-Tool** | Claude startet den blockierenden Befehl im Hintergrund und wird bei Ende geweckt. Kein Daemon nötig |
| Python 3, nur Standardbibliothek | JSON, Prozessgruppen, Zeitlimits ohne Installation von Paketen. Bash scheitert an JSON und `stat -f` (nur macOS). Zielplattformen: macOS, Linux, WSL |
| Schlüssel aus Umgebung, dann `~/.omni-agent/env` | `userConfig` erreicht `bin/` nicht (Handbuch, Abschnitt 7) |

## 3. Anbieter (`providers.json`)

Jeder Eintrag: `id`, `protokoll` (`anthropic` / `openai-chat` / `openai-responses`), `base_url`, `key_env`, `modelle`
(Alias → Name), `region`, `hinweis`. Die Werte unten sind am 28.10.2026 gegen die Herstellerseiten geprüft, soweit nicht
„nicht belegt“ steht.

| Anbieter | Protokoll | Base-URL | Schlüssel-Variable | Standardmodell | Datenort / Hinweis |
|---|---|---|---|---|---|
| **deepseek** | anthropic | `https://api.deepseek.com/anthropic` | `DEEPSEEK_API_KEY` | `deepseek-flash` (stark: `deepseek-v4-pro`) | **China**, Training vorgesehen. Such-/Fetch-API ab 01.11.2026 kostenpflichtig (0,75 $ / 1.000). Modellname ohne `claude`-Präfix und ohne DeepSeek-Namen ergibt 400 |
| **openrouter** | anthropic | `https://openrouter.ai/api` | `OPENROUTER_API_KEY` | frei wählbar | Standort nicht belegt. Claude-Code-Doku: nur Anthropic als Anbieter zugesagt. `ANTHROPIC_API_KEY` muss leer sein. Websuche nicht belegt |
| **kimi** | anthropic | `https://api.moonshot.ai/anthropic` | `MOONSHOT_API_KEY` | `kimi-k3[1m]`, Haiku-Stufe `kimi-k2.7-code` | Standort und Preise nicht belegt. Alle Stufen-Variablen setzen, sonst scheitern Hintergrundaufgaben still |
| **ollama** | anthropic | `http://localhost:11434` | keiner (`ollama` als Platzhalter) | z. B. `qwen3.5` | **lokal, Daten bleiben auf dem Rechner.** Modell braucht Tools und ≥ 64k Kontext. Kein `tool_choice`, keine Websuche. Mindestversion nicht belegt |
| **eurouter** | openai-chat (+ responses) | `https://api.eurouter.ai/api/v1` | `EUROUTER_API_KEY` | Katalog | Laut Anbieter Verarbeitung in der EU. **Kein Anthropic-Pfad belegt** → Runner `opencode`/`codex` oder Extra LiteLLM |
| **claude-konto** | anthropic | Standard | `CLAUDE_CODE_OAUTH_TOKEN` oder `ANTHROPIC_API_KEY` | `sonnet`, `haiku`, `opus` | Anderes Konto = eigene Kontingente. **Siehe Abschnitt 8 (Bedingungen)** |
| **nvidia** | openai-chat | `https://integrate.api.nvidia.com/v1` | `NVIDIA_API_KEY` | `z-ai/glm-5.3-flash` u. a. | Nur Chat-Completions. Free-Tier und Standort nicht belegt. Runner `opencode` oder Extra LiteLLM |
| *zai*, *minimax* | anthropic | `https://api.z.ai/api/anthropic`, `https://api.minimax.io/anthropic` | `ZAI_API_KEY`, `MINIMAX_API_KEY` | `glm-5.3`, `MiniMax-M3.1-Flash[1m]` | später, Preise und Standort nicht belegt |

Eigene Anbieter trägt man in `~/.omni-agent/providers.d/*.json` ein (gleiches Schema), ohne das Repo zu ändern.

## 4. Runner und Passung

| Runner | Befehl | Spricht | Rechte-Steuerung | Ausgabe | Status |
|---|---|---|---|---|---|
| **claude** | `claude -p` | anthropic | `--allowed-tools`, `dontAsk` (fein) | `stream-json`, Exit 0/≠0 | **Standard**, bestdokumentiert |
| **opencode** | `opencode run` | openai-chat, openai-responses, anthropic | `permission`-Konfig, `--auto` | `--format json` | zweite Wahl. Zwei Versionslinien (V1/V2), Exit-Codes nicht dokumentiert, jüngere Sicherheitsvorfälle: Version festlegen |
| **codex** | `codex exec` | **nur** openai-responses | Sandbox-Modi, keine Einzel-Whitelist | `--json`, `-o` | zweite Welt (OpenAI). `wire_api="chat"` entfernt |
| **dsh** | `dsh --profile headless` | OpenAI-kompatibel (Headless-Konfig nicht belegt) | nicht belegt | Klartext | **experimentell**, Developer Preview mit angekündigten Brüchen |
| *agy*, Crush, Goose, Aider | – | – | – | – | später. `agy`: Soft-Deny liefert Exit 0, Fremdanbieter nicht belegt |

**Passungsregel:** Ein Lauf braucht einen Runner, der das Protokoll des Anbieters spricht.

| Anbieter | claude | opencode | codex |
|---|---|---|---|
| deepseek, openrouter, kimi, ollama, claude-konto | ja | ja | nur wenn Responses |
| eurouter | nur mit LiteLLM | **ja** | ja (Responses-Kompatibilität nicht geprüft) |
| nvidia | nur mit LiteLLM | **ja** | nein |

`omni-agent run` wählt ohne `--runner` den ersten **installierten** Runner in der Reihenfolge claude → opencode → codex,
der passt. Passt keiner, sagt es klar warum und was fehlt (Runner installieren oder Extra LiteLLM). `omni-agent doctor`
zeigt dieselbe Matrix für den eigenen Rechner.

## 5. Der Vertrag zwischen Kern und Runner

**Eingabe an den Adapter:** Auftragsdatei, Laufordner, Anbieter, Modell, neutrale Werkzeugliste, Limits.

**Neutrale Werkzeuge:** `lesen`, `schreiben`, `web_suche`, `web_laden`, `shell`.
Standard: **ohne** `shell`. Jeder Adapter übersetzt:

| Neutral | claude | opencode | codex |
|---|---|---|---|
| lesen | `Read Glob Grep` | `permission.read/glob/grep` | Sandbox lesbar |
| schreiben | `Write Edit` | `permission.edit` | `workspace-write` |
| web_suche, web_laden | `WebSearch`, `WebFetch` | `websearch`, `webfetch` | nicht belegt |
| shell | `Bash` | `permission.bash` | Sandbox |

Was ein Runner nicht kann, nennt `doctor` und der Lauf **verweigert**, statt still weniger zu tun.

**Ausgabe im Laufordner:**

| Datei | Inhalt |
|---|---|
| `bericht.md` | Ergebnis. **Vorhanden = fertig.** Das ist der einzige verbindliche Fertig-Beweis |
| `log.jsonl` | Rohausgabe des Runners |
| `fehler.log` | stderr |
| `status.json` | `zustand` (`arbeitet`/`fertig`/`fehler`/`abgebrochen`), `start`, `ende`, `exitcode`, `runner`, `anbieter`, `modell`, `runden` |

Der Exit-Code des Runners ist nur Zusatzsignal: er ist je Runner unterschiedlich dokumentiert, bei `agy` bedeutet 0 auch „verweigert“.

**Exit-Code von `omni-agent`:** 0 fertig · 1 Fehler im Lauf · 2 Konfiguration (Key oder Runner fehlt) · 3 Endpunkt nicht erreichbar · 124 Zeitlimit.

**Auftragsrahmen**, den der Kern jedem Auftrag voranstellt (aus dem lokalen Test: ohne Limit 232 s und 33 Tool-Aufrufe, mit Limit 16 s):

- Ergebnis in `bericht.md` im Arbeitsordner schreiben, Quellen mit URL.
- Höchstens *N* Werkzeugaufrufe (Standard 12, einstellbar).
- Behauptungen ohne Beleg als „nicht belegt“ kennzeichnen.
- Nichts außerhalb des Arbeitsordners lesen oder schreiben.

## 6. Befehle

| Befehl | Zweck |
|---|---|
| `omni-agent setup` | Führung: Anbieter wählen, Datei `~/.omni-agent/env` anlegen und öffnen, Runner prüfen, Kern in den PATH legen (`~/.local/bin`) |
| `omni-agent doctor` | Was ist da, was fehlt: Runner, Schlüssel (nur ob gesetzt, nie der Wert), Erreichbarkeit, Passungs-Matrix |
| `omni-agent run <auftrag.md> [--anbieter] [--modell] [--runner] [--werkzeuge] [--max-runden] [--zeit] [--ordner]` | Auftrag ausführen, blockierend, Live-Fortschritt |
| `omni-agent status [lauf]` | Läufe, Zustand, Bericht |
| `omni-agent anbieter`, `omni-agent runner` | Listen |
| `omni-agent extras litellm install | start | stop` | optionaler Übersetzer, Abschnitt 7 |

**Slash-Befehle (Plugin):** `/omni-agent:setup`, `:doctor`, `:run`, `:status`; dazu die Skill `delegieren` (Claude schlägt von selbst
einen Fremdagent vor, wenn Kosten, Parallelität oder Modellvielfalt es nahelegen). `:run` ist `disable-model-invocation: true`
und trägt `allowed-tools: Bash(omni-agent *)`; der Skill-Text weist Claude an, den Befehl **im Hintergrund** zu starten.

## 7. Extra: LiteLLM (optional)

Nur für OpenAI-kompatible Anbieter, wenn der gewünschte Runner sie nicht selbst spricht (zum Beispiel `claude` gegen EUrouter oder Nvidia).

| Regel | Grund |
|---|---|
| Nie Pflicht, nur `omni-agent extras litellm install` | Zwei Lieferkettenvorfälle in sieben Monaten |
| Version **fest gepinnt**, Hash-Sperre, eigene virtuelle Umgebung unter `~/.omni-agent/extras/litellm` | `litellm==1.107.0` wurde am 21.10.2026 kompromittiert (PyPI **und** offizielle Docker-Images), Hersteller empfiehlt Pin 1.106.2. Die lokal verwendete 1.106.3 liegt davor |
| Nur 127.0.0.1, ein eigener Zugangsschlüssel, **nur ein** Anbieter-Key in der Umgebung des Proxys | Schaden begrenzen |
| Vor jedem Pin-Wechsel die Vorfallsseite des Herstellers lesen | Der Schadcode lief beim Python-Start, ein `import` war nicht nötig |
| Alternative `claude-code-router` nicht gewählt | Große Node-Lieferkette, Sicherheitsstand nicht geprüft |

Bevorzugt wird immer: **anderer Runner statt Übersetzer** (EUrouter und Nvidia mit `opencode`).

## 8. Sicherheit und Bedingungen

| Thema | Regel |
|---|---|
| Schlüssel | Nie im Repo, nie im Chat, nie im Log. Datei `~/.omni-agent/env` mit Rechten 600 (Kern verweigert sonst). Der Kern reicht dem Runner **nur den einen** benötigten Schlüssel |
| Umgebung | `env -i` plus Nötigstes. Bei `claude`: `ANTHROPIC_API_KEY` leer, `--setting-sources project`, `--strict-mcp-config`, `--no-session-persistence`, leerer Laufordner. Ohne das führt `-p` Hooks und MCP des Arbeitsordners aus |
| Alle Modell-Variablen | `ANTHROPIC_MODEL`, Opus/Sonnet/Haiku, `CLAUDE_CODE_SUBAGENT_MODEL` setzen, sonst scheitern Hintergrundstufen still |
| Standard ohne Shell | `shell` nur ausdrücklich (`--werkzeuge +shell`) mit Warnung. Websuche kann Prompt-Injection liefern; ein Agent mit Shell und fremden Webinhalten ist eine Einladung |
| Datenschutz | README nennt den Datenort je Anbieter. **DeepSeek: China.** Keine Teilnehmerdaten oder Interna in Aufträge. Für Personenbezug: ollama (lokal) oder eurouter |
| **claude-konto** | Anthropic erlaubt `claude setup-token` für Skripte, verweist aber Entwickler von Produkten auf API-Keys, und verbietet das Sammeln, Speichern oder Weiterreichen von Abo-Zugangsdaten. Ob ein unbeaufsichtigter Lauf mit **eigenem** Abo-Token „ordinary use“ ist, ist **nicht belegt**. Darum: Omni-Agent **speichert diesen Token nie** (nur Umgebungsvariable der Nutzerin), startet das unveränderte `claude`-Binary, empfiehlt den API-Key und warnt im README |
| Zeitlimit | Prozessgruppe wird bei Ablauf beendet (Exit 124) |
| Vor Veröffentlichung | Geheimnis-Scan des Arbeitsbaums **und** der Git-Historie, Test-Key rotieren |

## 9. Migration vom jetzigen Wrapper

| Heute | Neu |
|---|---|
| `fbs/agent-love/tools/fremdagent` (Bash) | `bin/omni-agent` + `lib/` (Python) |
| `~/.fremdagent/` | `~/.omni-agent/` (Läufe werden übernommen, Schlüssel nur mit deinem OK verschoben) |
| `status.json`-Vertrag, `fortschritt.py` | bleiben, wandern in den Kern |
| LiteLLM-Venv in `~/.fremdagent/litellm-venv` | `~/.omni-agent/extras/litellm` (neu gepinnt) |
| Name `fremdagent` | `omni-agent`. Für Altnutzer ein Alias-Skript `fremdagent` |

## 10. Reihenfolge (nur Reihenfolge und Tore, keine Zeitangaben)

| Stufe | Inhalt | Tor |
|---|---|---|
| 1 | Kern + Runner `claude` + Anbieter `deepseek`: Portierung des heutigen Wrappers | Lauf mit Bericht, `status.json` stimmt |
| 2 | `providers.json` komplett, `doctor`, `setup`, Passungs-Matrix | `doctor` zeigt die Matrix, fehlender Key wird sauber gemeldet |
| 3 | Plugin-Hülle: Manifeste, 5 Skills | `claude plugin validate --strict` grün, `/omni-agent:run` startet einen Lauf in `claude --plugin-dir` |
| 4 | `INSTALL.md`, `AGENTS.md`, README mit Datenschutz-Tabelle | Eine frische Claude-Sitzung installiert und prüft nur anhand der `INSTALL.md` |
| 5 | Runner `opencode` | Lauf gegen EUrouter oder Nvidia ohne Proxy |
| 6 | Runner `codex` | Lauf gegen einen Responses-Endpunkt |
| 7 | Extra LiteLLM | `claude` gegen Nvidia über den gepinnten Proxy |
| 8 | Runner `dsh` (experimentell) | erst wenn ein Release ohne `rc`/`alpha` vorliegt, sonst nur mit Warnschild |
| 9 | Geheimnis-Scan, Schlüsselrotation, **Veröffentlichung nach deinem Ja** | Scan sauber |

Für morgen realistisch: Stufen 1 bis 4 mit DeepSeek (Schlüssel vorhanden). Weitere Anbieter sind eingetragen,
aber **nur live geprüft, wo du einen Schlüssel hast**; alles andere trägt im README den Vermerk „laut Herstellerdoku, nicht getestet“.

## 11. Entscheidungen (getroffen)

1. **Schlüssel-Weg:** Umgebung plus Datei `~/.omni-agent/env` statt MCP.
2. **Kern:** Python 3 (macOS, Linux, WSL; natives Windows später).
3. **Name:** `omni-agent` (das ältere `omniagent` ist auf npm von einem anderen Projekt belegt).
4. **GitHub-Account:** `alexodexo`.
5. **Claude-Konto** ist Anbieter, mit der Warnung aus Abschnitt 8.
6. **Standardanbieter:** keiner, die Nutzerin wählt bei jedem Lauf.
