# Omni-Agent: Modell-Anbieter und Agent-CLIs (Faktenlage 28.10.2026)

Regeln dieser Datei: Nur Primärquellen (Hersteller-Doku, Hersteller-Repos). Jede Aussage trägt URL und Abrufdatum. **28.10.2026** = heute live abgerufen. **25.10.2026 (lokal)** = lokale Rohkopie (nicht im Repo) (selbst von der Hersteller-URL abgerufen, heute nicht erneut). **nicht belegt** = konnte nicht aus einer Primärquelle bestätigt werden. Keine Keys eingegeben, nichts installiert, keine Konten angelegt.

Abkürzungen: CC = Claude Code. `AUTH_TOKEN` = `ANTHROPIC_AUTH_TOKEN` (Bearer-Header). `API_KEY` = `ANTHROPIC_API_KEY` (x-api-key-Header).

---

## Vorab: Eine Sache gilt für alle Anbieter in Teil A

Auth-Rangfolge in CC (https://code.claude.com/docs/en/authentication, 28.10.2026): Cloud-Provider-Variablen > `ANTHROPIC_AUTH_TOKEN` > `ANTHROPIC_API_KEY` > `apiKeyHelper` > `CLAUDE_CODE_OAUTH_TOKEN` > Anthropic-Profile > Abo-Login. Im `-p`-Modus wird ein vorhandener `ANTHROPIC_API_KEY` **immer** benutzt (im interaktiven Modus nur nach Bestätigung). Folge für Omni-Agent: Beim Start gegen einen Fremdendpunkt nur `AUTH_TOKEN` setzen und `API_KEY` leer oder gar nicht setzen (OpenRouter schreibt `ANTHROPIC_API_KEY=""` ausdrücklich vor; Kimi: „remove it to avoid conflicts"). Der bestehende Wrapper mit `env -i` erfüllt das.

---

## TEIL A – Modell-Anbieter für den Runner „claude"

### A1. Übersicht

| Anbieter | Anthropic-Endpunkt (`ANTHROPIC_BASE_URL`) | Auth-Variable | Standardmodelle (laut Anbieter-Doku) | Quelle (Abruf) |
|---|---|---|---|---|
| **DeepSeek** | `https://api.deepseek.com/anthropic` | `AUTH_TOKEN` | `deepseek-flash` (V4.1-Flash-1017), `deepseek-v4-pro` (V4-Pro-0813); beide 1M Kontext, 384K Output. Doku setzt `ANTHROPIC_MODEL=deepseek-flash[1m]`, Opus/Sonnet ebenso, Haiku und `CLAUDE_CODE_SUBAGENT_MODEL=deepseek-flash`, dazu `CLAUDE_CODE_EFFORT_LEVEL=max`, `CLAUDE_CODE_AUTO_COMPACT_WINDOW=786432` | https://api-docs.deepseek.com/quick_start/pricing (28.10.), https://api-docs.deepseek.com/guides/anthropic_api (28.10.), Claude-Code-Seite lokal 25.10. von https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code |
| **OpenRouter** | `https://openrouter.ai/api` (volle URL mit Schema) | `AUTH_TOKEN` = OpenRouter-Key; `ANTHROPIC_API_KEY` auf **leeren String** setzen | Beliebige OpenRouter-Modelle; Beispiele in der Doku nutzen `~anthropic/claude-*-latest`-Aliase, `[1m]` für 1M Kontext. Variablen: `ANTHROPIC_DEFAULT_{FABLE,OPUS,SONNET,HAIKU}_MODEL`, `CLAUDE_CODE_SUBAGENT_MODEL`, optional `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1` | https://openrouter.ai/docs/guides/coding-agents/claude-code-integration (28.10.) |
| **Kimi / Moonshot** | `https://api.moonshot.ai/anthropic` | `AUTH_TOKEN` | `kimi-k3[1m]` (Haupt/Opus/Sonnet/Fable/Subagent), `kimi-k2.7-code` (Haiku-Stufe, Thinking erzwungen), optional `kimi-k2.6` | https://platform.kimi.ai/docs/guide/claude-code-kimi.md (28.10.) |
| **Ollama (lokal)** | `http://localhost:11434` | `AUTH_TOKEN=ollama` (Platzhalter), `API_KEY=""` | Doku-Beispiel lokal `qwen3.5`; Modell muss Tools können, Kontext >= 64k. Start auch per `ollama launch claude` | https://docs.ollama.com/integrations/claude-code (28.10.) |
| **Ollama Cloud (direkt)** | `https://ollama.com` | `AUTH_TOKEN=$OLLAMA_API_KEY`, `API_KEY=""` | Beispiele: `glm-5.3-flash`, `gemma4:cloud`, `kimi-k2.7-code:cloud` | gleiche Seite (28.10.) |
| **EUrouter** | **kein Anthropic-Endpunkt belegt.** Basis `https://api.eurouter.ai/api/v1`, OpenAI-Stil (`/chat/completions`, `/completions`, `/responses`) | Bearer-Key | Modellkatalog separat (Claude- und Mistral-Modelle gelistet) | https://www.eurouter.ai/docs , https://www.eurouter.ai/llms.txt , https://www.eurouter.ai/api/openapi.json (alle 28.10.) |
| **Claude, anderes Konto** | Standard (`api.anthropic.com`), keine Base-URL nötig | `ANTHROPIC_API_KEY` (Console-Key) **oder** `CLAUDE_CODE_OAUTH_TOKEN` (Abo, per `claude setup-token`) | `sonnet`/`opus`/`haiku`/`fable` oder volle Namen via `--model` | https://code.claude.com/docs/en/authentication (28.10.) |
| **Nvidia NIM** | **kein Anthropic-Endpunkt belegt.** Basis `https://integrate.api.nvidia.com`, `POST /v1/chat/completions` | NVIDIA-Key (Bearer) | Lokale Modelliste: `quellen/nvidia-modelliste-2026-10-25.txt` (Modellnamen dort nicht gegen Nvidia-Seite neu geprüft) | https://docs.api.nvidia.com/nim/reference/llm-apis (28.10.) |
| **Z.ai GLM** | `https://api.z.ai/api/anthropic` | `AUTH_TOKEN` | Mapping-Standard: `GLM-5.3-Flash` für Opus/Sonnet/Haiku; manuelles Beispiel: `glm-5.3[1m]` (Sonnet/Opus), `glm-5.3-flash[1m]` (Haiku); `API_TIMEOUT_MS=3000000`, `CLAUDE_CODE_AUTO_COMPACT_WINDOW=1000000` | https://docs.z.ai/devpack/tool/claude (28.10.) |
| **MiniMax** | `https://api.minimax.io/anthropic` (China: `api.minimaxi.com`, laut Suchtreffer-Zusammenfassung, Seite selbst nicht geöffnet) | `AUTH_TOKEN` = „Subscription Key" | `MiniMax-M3.1-Flash[1m]` für Haupt/Opus/Sonnet/Haiku; Thinking immer an; `CLAUDE_CODE_AUTO_COMPACT_WINDOW=524288` | https://platform.minimax.io/docs/token-plan/claude-code.md (28.10.). Andere MiniMax-Seiten nennen abweichende Modellnamen (M3, M3[1m], M3.1-Flash-Preview): Versionsdrift, jeweils die eigene Planseite prüfen |

### A2. Tool-Aufrufe, WebSearch/WebFetch, Preise, Datenstandort, Fallen

| Anbieter | Tools / WebSearch / WebFetch | Preise grob | Datenstandort / DSGVO | Bekannte Fallen |
|---|---|---|---|---|
| **DeepSeek** | Tools: `tool_choice` none/auto/any/tool unterstützt, `disable_parallel_tool_use` ignoriert. Bilder (base64/url/file) ja. `web_search`-Blöcke (`server_tool_use`, `web_search_tool_result`) als unterstützt gelistet; Such-/Fetch-API: 0,75 $ je 1.000 erfolgreiche Anfragen, **über Harness, Claude Code oder Codex derzeit kostenlos, Abrechnung ab 01.11.2026 00:00 Peking**. Eigener Praxistest (25.10., lokal `wissen.md`): Websuche, Seite laden, Datei schreiben funktionieren | flash: 0,15/0,30 $ Eingabe (Miss, Off-Peak/Peak), 0,60/1,20 $ Ausgabe je 1 Mio.; v4-pro: 0,66/1,32 $ und 1,98/3,96 $. Off-Peak = halber Preis. Peak: 01-04 und 06-10 UTC, Mo-Fr ohne chin. Feiertage | Datenschutzerklärung (Stand 10.02.2026, lokal 25.10. von https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html): Anbieter mit Sitz in China, Speicherung VR China, Nutzung zum Modelltraining vorgesehen. Für Personendaten aus der EU kritisch, rechtliche Bewertung **nicht belegt** | Modellname ohne Präfix `claude` und nicht ein echter DeepSeek-Name: HTTP 400. `claude-opus*` mappt auf v4-pro, `claude-sonnet*`/`claude-haiku*`/sonstige `claude*` auf flash. Ignoriert: `cache_control`, `mcp_servers`, `top_k`; `redacted_thinking`, `document`-Blöcke nicht unterstützt. Ohne Aufrufbegrenzung im Auftrag ufert der Agent aus (lokaler Test: 33 Tool-Aufrufe, 232 s) |
| **OpenRouter** | Native Tool-Nutzung und Thinking-Blöcke werden durchgereicht. Websuche: auf der Seite **nicht erwähnt** | Abrechnung über OpenRouter-Guthaben; Modellpreise je Modell, **nicht abgerufen** | Doku: Quellcode-Prompts werden nur geloggt, wenn man Prompt-Logging aktiviert. Weiteres zu Standort/DSGVO **nicht belegt** | Doku: Kompatibilität nur mit Anthropic-1P-Provider zugesagt, empfohlen: Anthropic 1P als Top-Priorität; CC „may not work correctly" mit anderen. Ohne `[1m]` im Namen nimmt CC 200k Kontext an. Nach früherem Anthropic-Login `/logout` |
| **Kimi** | Messages-API als „Anthropic-kompatibel" beschrieben. WebSearch **nicht belegt** | auf der Seite keine Preise; **nicht belegt** | **nicht belegt** | `env` in `~/.claude/settings.json` überstimmt Shell-Variablen. Nicht gesetzte Stufen-Variable lässt Hintergrund-/Subagent-Aufgaben still scheitern. `kimi-k2.7-code` ohne Thinking: 400 „only type=enabled is allowed". Zu großes `AUTO_COMPACT_WINDOW`: Kontextfehler. npm-Installation braucht Node 22+ (Seite) |
| **Ollama lokal** | Anthropic-Schnittstelle `/v1/messages`: Streaming, System-Prompts, Tools inkl. Tool-Results, Vision (nur base64), Thinking (`budget_tokens` angenommen, nicht erzwungen). **Nicht unterstützt:** `tool_choice`, gehostete Websuche, deferred Tools, `count_tokens`, Prompt-Caching, Batches, Citations, PDF-`document`-Blöcke (https://docs.ollama.com/api/anthropic-compatibility, 28.10.) | lokal kostenlos (Hardware); Cloud-Preise **nicht belegt** | lokal: Daten verlassen den Rechner nicht (folgt aus Betrieb, nicht aus Doku zitiert). Cloud: **nicht belegt** | **Mindestversion von Ollama für die Anthropic-API: nicht belegt** (beide Seiten nennen keine). Modell braucht Tool-Support und >= 64k Kontext. CC fragt standardmäßig nach Rechten; Direktverbindung zur Cloud unterstützt gehostete WebSearch nicht voll |
| **EUrouter** | Chat-Completions und Responses-Format; Anthropic-Format nicht belegt | Preise im Katalog, **nicht abgerufen** | Seite: „All inference traffic is processed inside the EU", „GDPR-aligned by design", konfigurierbare Routing- und Retention-Kontrollen (Marketingaussage, Details **nicht belegt**) | Für CC wird ein Übersetzer nötig (siehe A3). Die OpenAPI-Datei (278.743 Zeichen) wurde nur zu den ersten 100.000 Zeichen gelesen: dort kein `/messages`-Pfad; Pfad `/api/v1/chat/completions` vorhanden. Vollständiger Ausschluss eines Messages-Pfads daher **nicht belegt**, aber `llms.txt` listet 16 API-Referenzseiten ohne Messages |
| **Claude anderes Konto** | volle Tool- und Web-Funktionen (Erstanbieter) | Abo oder API-Abrechnung, Preise **nicht abgerufen** | **nicht belegt** (nicht geprüft) | `--bare` liest **kein** `CLAUDE_CODE_OAUTH_TOKEN` und keinen Keychain-Login; dort `ANTHROPIC_API_KEY` oder `apiKeyHelper` nötig. Token aus `setup-token` kann nur Modellanfragen, keine Remote-Control-Sitzungen, keine claude.ai-Connectors |
| **Nvidia NIM** | nur OpenAI-Format (Chat Completions) belegt | Free-Tier/Limits/Nutzungsbedingungen **nicht belegt** (Seite sagt dazu nichts) | **nicht belegt** | Übersetzer nötig (LiteLLM). Lokale Praxis: `drop_params: true`, sonst Fehler bei unbekannten Anthropic-Feldern |
| **Z.ai GLM** | Tools/WebSearch/MCP: Seite sagt dazu nichts, **nicht belegt** | Seite nennt keine Preise (verweist auf Coding-Plan-Seiten), **nicht belegt** | **nicht belegt** | Doku verifiziert mit CC 2.0.14 (veraltet gegenüber aktuell 2.1.312). Einrichtungsskript nur macOS/Linux; Coding-Helper `npx @z_ai/coding-helper` |
| **MiniMax** | **nicht belegt** | **nicht belegt** | **nicht belegt** | `ANTHROPIC_AUTH_TOKEN`/`BASE_URL` in der Shell überstimmen `settings.json`. Thinking nicht abschaltbar. `xhigh` wird von manchen CC-Versionen als `high` gesendet |

### A3. LiteLLM als OPTIONALES Extra

| Punkt | Befund | Quelle (Abruf) |
|---|---|---|
| Aktuelle Version | PyPI: `litellm` **1.106.5** (veröffentlicht 27.10.2026 19:44 UTC, Python `>=3.10,<3.15`); danach nur `1.109.0.dev1` (28.10.). Auch 1.104.8, 1.103.10, 1.105.6 am 27.10. neu veröffentlicht (Backports). Lokale Notiz vom 25.10. nannte 1.106.3 | https://pypi.org/pypi/litellm/json (28.10.), lokal `quellen/litellm-1.106.3-pypi-2026-10-25.json` |
| **Sicherheitsvorfall Oktober 2026** | `litellm==1.107.0` kompromittiert. PyPI: alle sieben Wheels live 11:39:51 bis 13:23 UTC am 21.10.2026. **Docker ebenfalls betroffen:** Docker Hub-Tags `v1.107.0`, `latest`, `main-latest`, `main-stable` zeigten 11:46:56 bis 14:20 UTC auf kompromittiertes Image; GHCR (`litellm`, `litellm-database`, `litellm-non_root`) ähnlich bis 13:51 UTC. Schadcode: Credential-Stealer plus Nachlader für Remote-Code-Ausführung; Indikatoren `cook.pth`, `cook.py`, `sitecustomize.py`, Daemon mit `/tmp/remote_code_loader.lock`; läuft beim Python-Start, ein `import litellm` ist nicht nötig. Der GitHub-Tag `v1.107.0` enthält die Schaddateien nicht. Hersteller: alle früheren Versionen sicher, auf `1.106.2` pinnen. Status „contained", Maintainer-Zugänge entzogen, Untersuchung läuft; Update vom 23.10. korrigiert frühere Annahmen | https://docs.litellm.ai/blog/security-incident-oct-21-2026 (28.10.) |
| **Sicherheitsvorfall März 2026** | `1.82.7` und `1.82.8` auf PyPI am 24.03.2026 (ca. 10:39 UTC, ca. 40 Minuten bis Quarantäne). Stahl Umgebungsvariablen, SSH-/Cloud-Keys, K8s-Tokens, DB-Passwörter; 1.82.8 mit `.pth`-Datei. Offizielles Proxy-Docker-Image und GitHub-Quellinstallation waren damals nicht betroffen. Sauber: 1.83.0 über neue CI-Pipeline | https://docs.litellm.ai/blog/security-update-march-2026 (28.10.) |
| Einordnung | Zwei Lieferkettenvorfälle in sieben Monaten, beim zweiten **auch die offiziellen Docker-Images**. CVE/GitHub-Advisory für den Oktobervorfall laut Sekundärquellen (Datadog, Microsoft) bei Redaktionsschluss nicht vergeben; OSV-Eintrag MAL-2026-2144 laut Suchtreffer. Ob 1.106.4 und 1.106.5 (nach dem Vorfall gebaut) vom Hersteller ausdrücklich als verifiziert bestätigt sind: **nicht belegt** | Sekundär: https://www.microsoft.com/en-us/security/blog/2026/10/23/inside-the-litellm-1-107-0-supply-chain-compromise-credential-theft-through-python-startup-hooks/ , https://securitylabs.datadoghq.com/articles/litellm-compromised-pypi-docker/ (nur über Suchergebnis gesehen, nicht geöffnet) |
| Mindestkonfiguration `/v1/messages` | `config.yaml` mit `model_list` (`model_name` = Name, den der Client schickt; `litellm_params.model` = Ziel, `api_key: os.environ/KEY`), Start `litellm --config <pfad>`, Anthropic-Aufruf `POST /v1/messages` mit Header `x-api-key`, `anthropic-version: 2023-06-01`. Hersteller: „follows the Anthropic messages specification". Einschränkungen laut Seite: `max_tokens` > 1; `thinking.budget_tokens` mind. 1024 und < `max_tokens` | https://docs.litellm.ai/docs/anthropic_unified (28.10.) |
| Claude Code gegen LiteLLM | Die Hersteller-Seite behandelt Claude Code **nicht**. Funktionierende Praxis lokal: `ANTHROPIC_BASE_URL=http://127.0.0.1:4000`, `AUTH_TOKEN` = Proxy-Masterkey, alle Modellvariablen auf einen `model_name`; `litellm_settings: {telemetry: false, drop_params: true}`; Liveness `GET /health/liveliness` | lokal `tools/fremdagent`, `tools/litellm/config.yaml` (eigene Erfahrung, kein Herstellerbeleg) |
| Codex gegen LiteLLM | Aktuelle Codex-Versionen unterstützen **nur** Responses-API-Endpunkte (`wire_api="chat"` entfernt). Ob LiteLLM `/v1/responses` für Nvidia/andere liefert: **nicht belegt** | https://learn.chatgpt.com/docs/models (lokal 25.10.) |

**Empfehlung LiteLLM (Einschätzung, kein Beleg):** Nur als Opt-in, nie als Pflichtabhängigkeit. Wenn doch: Version fest pinnen (z. B. 1.106.2 laut Hersteller oder eine selbst geprüfte spätere), Hash-Pinning, Docker nur per Digest und selbst gebaut oder aus GitHub-Tag, in eigener virtueller Umgebung beziehungsweise Container mit **nur einem** Anbieter-Schlüssel in der Umgebung, kein Zugriff auf SSH/Cloud-Keys, ausgehender Verkehr eingeschränkt. Vor jedem Update Vorfallsseite lesen.

### A4. Alternativen zu LiteLLM

| Option | Befund | Einschätzung |
|---|---|---|
| **claude-code-router** (musistudio) | Lokales Gateway `127.0.0.1:3456`, UI `:3458`; Protokolle: OpenAI Chat/Responses, Anthropic Messages, Gemini; Routing, Retries, Fallbacks; MIT; v3.1.3 (npm, 28.10.); 37,9k Sterne; Node 22+; Installation Desktop-App, `npm i -g @musistudio/claude-code-router`, Docker. Konfigurationsschema auf der Repo-Seite nicht dokumentiert; Sicherheits-Tab zeigt „1" ohne Inhalt; 944 offene Issues (https://github.com/musistudio/claude-code-router, 28.10.) | Brauchbare Alternative, aber Node-Paket mit großer Lieferkette und Tür für dieselbe Angriffsklasse; Sicherheitsstand **nicht geprüft** |
| **Native Anthropic-Endpunkte der Anbieter** | DeepSeek, Kimi, Z.ai, MiniMax, OpenRouter, Ollama liefern selbst Anthropic-Format (Tabelle A1) | **Bevorzugen:** kein Übersetzer, kleinere Angriffsfläche |
| Andere Übersetzer-Proxies | nicht untersucht | **nicht belegt** |
| Anderer Runner statt Proxy | OpenCode, Codex, dsh sprechen OpenAI-Format beziehungsweise Responses direkt (Teil B) | Für reine OpenAI-Anbieter (EUrouter, Nvidia) oft der sauberere Weg als „Claude Code + Übersetzer" |

### A5. Nutzungsbedingungen: Abo-Token in automatisierten Läufen

| Aussage | Quelle (Abruf 28.10.2026) |
|---|---|
| `claude setup-token` erzeugt ein einjähriges OAuth-Token „for CI pipelines, scripts, or other environments where interactive browser login isn't available". Es gilt für Pro/Max/Team/Enterprise, kann nur Modellanfragen. Wird als `CLAUDE_CODE_OAUTH_TOKEN` gesetzt, Rang 5 der Auth-Reihenfolge | https://code.claude.com/docs/en/authentication |
| OAuth-Anmeldung ist „intended exclusively for purchasers" der Abo-Pläne und „designed to support ordinary use of Claude Code and other native Anthropic applications" | https://code.claude.com/docs/en/legal-and-compliance |
| Entwickler, die Produkte oder Dienste bauen (ausdrücklich inkl. Agent SDK), sollen API-Key-Authentifizierung nutzen. Drittentwickler dürfen kein claude.ai-Login anbieten und Anfragen nicht über Abo-Zugangsdaten für ihre Nutzer routen; Zugangsdaten und Session-Tokens dürfen nicht gesammelt, gespeichert oder vermittelt werden | gleiche Seite |
| Angekündigte Pro/Max-Limits setzen „ordinary, individual usage of Claude Code and the Agent SDK" voraus; Anthropic kann Durchsetzung ohne Vorwarnung betreiben | gleiche Seite |
| Ausdrücklich erlaubt: Kunde konfiguriert eigene API-Keys für eigene Nutzer, sofern Abrechnung beim Key-Inhaber bleibt; Endnutzer darf sich im **unveränderten** CC-Binary mit eigenem Abo anmelden | gleiche Seite |
| Wer CC in Produkten/gehosteten Umgebungen mitliefert: Commercial Terms, Binary unverändert, keine Auth-Methode entfernen, nicht für Endnutzer bezahlen oder weiterverkaufen | gleiche Seite |

**Auslegung für Omni-Agent (Einschätzung, keine Rechtsauskunft):** Dass `setup-token` in der Auth-Doku für Skripte beschrieben ist und die Rechtsseite Entwickler von „products or services" auf API-Keys verweist, ist ein offener Spannungspunkt. Ob ein unbeaufsichtigter Hintergrundlauf mit dem **eigenen** Abo-Token auf dem **eigenen** Rechner als „ordinary, individual usage" gilt, ist **nicht belegt**. Sicher auf der richtigen Seite: Omni-Agent sammelt, speichert und vermittelt **nie** Tokens (Nutzer setzt `CLAUDE_CODE_OAUTH_TOKEN` oder `ANTHROPIC_API_KEY` selbst in seiner Umgebung), startet das unveränderte `claude`-Binary und warnt im README vor dem Abo-Token-Fall. Rückfrage bei Anthropic Sales wäre der einzige verlässliche Weg.

---

## TEIL B – Austauschbare Agent-CLIs („Runner")

### B1. Claude Code (`claude -p`)

| Punkt | Befund | Quelle (Abruf 28.10.2026) |
|---|---|---|
| Version | npm `@anthropic-ai/claude-code` **2.1.312** (27.10.2026) | https://registry.npmjs.org/@anthropic-ai/claude-code |
| Headless | `claude -p "…"`; Eingabe auch per Pipe (Stdin max. 10 MB); `--input-format text|stream-json` | https://code.claude.com/docs/en/headless , https://code.claude.com/docs/en/cli-reference |
| Modell/Anbieter | Nur per Umgebungsvariablen (Teil A) oder `--model`, `--settings <datei|json>`, `settings.json` mit `env`-Block. **Achtung:** `env` in `settings.json` überstimmt Shell-Variablen (Kimi-/MiniMax-Seite). `--fallback-model` verfügbar | cli-reference; Kimi-Seite |
| Rechte | `--allowed-tools` (Regeln ohne Rückfrage, Syntax `Bash(git diff *)`), `--tools` (Verfügbarkeit einschränken, `""` = keine), `--disallowed-tools`, `--permission-mode` = `default`/`manual`, `acceptEdits`, `plan`, `auto`, `dontAsk`, `bypassPermissions`; `--permission-prompts none` (ab v2.1.259). `dontAsk` verweigert alles, was sonst fragen würde. **Ab v2.1.302 startet `-p` ohne gesetzten Modus im Manual-Modus** (nicht Gewährung) | cli-reference, headless |
| Isolation | `--setting-sources project` (oder `user,project,local`), `--strict-mcp-config` (+ `--mcp-config`), `--no-session-persistence`, `--bare` (Empfehlung der Doku für Skripte, wird künftig Standard; lädt nichts aus Hooks/Skills/MCP/CLAUDE.md, liest **kein** OAuth/Keychain). Ohne `--bare` führt `-p` Hooks aus `.claude/settings.json` und MCP-Server aus `.mcp.json` des Arbeitsordners aus, auch in nie bestätigten Ordnern, und zeigt keinen Trust-Dialog | headless |
| Begrenzungen | `--max-turns` (Fehler bei Erreichen), `--max-budget-usd` (Schätzung, kann überschritten werden), `--json-schema` (Feld `structured_output`) | cli-reference |
| Ausgabe | `text`, `json` (mit `result`, `session_id`, `total_cost_usd`), `stream-json` (zeilenweise, mit `--verbose`; `--include-partial-messages` für Deltas). Letzte Zeile = `result`-Nachricht; erste = `system/init` (Modell, Tools, MCP-Status, `plugin_errors`, `mcp_server_errors`); `system/api_retry` mit `error_status`; `permission_denied`-Nachrichten und `permission_denials` im Ergebnis | headless |
| Fertig/Fehler | Exit 0 = Erfolg, nicht 0 = Fehlschlag; Fehler im Lauf (z. B. fehlende Auth) erscheinen als Ergebnis auf stdout. SIGTERM → Exit **143**, kein Ergebnis für den laufenden Zug. Die genauen Feldnamen des `result`-Objekts (z. B. `is_error`, `subtype`) stehen auf der abgerufenen Seite **nicht** → **nicht belegt** | headless |
| Arbeitsordner | Erbt das aktuelle Verzeichnis; `--add-dir` für weitere. Wird der Ordner mitten im Lauf gelöscht, läuft die Sitzung weiter und meldet Warnung im Stream | headless |
| Hintergrundarbeit | Nach dem Zug wartet der Lauf auf Hintergrundbefehle/Subagents bis 10 Minuten Leerlauf (`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS`) | headless |
| Installation | `curl -fsSL https://claude.ai/install.sh | bash`, PowerShell/CMD-Installer, `brew install --cask claude-code`, npm `@anthropic-ai/claude-code` | lokal 25.10. https://code.claude.com/docs/en/setup |
| Windows | Ja: Windows 10 1809+, Server 2019+; Bash, Zsh, PowerShell oder CMD. Git for Windows empfohlen (sonst PowerShell als Shell-Tool); DeepSeek-/Z.ai-Seiten nennen Git for Windows als Voraussetzung | setup (lokal 25.10.) |
| Sicherheit | 35 veröffentlichte GitHub-Advisories (Zählung lokal 25.10.); Inhalt nicht ausgewertet | lokal `quellen/claude-code/github-security-advisories-2026-10-25.json` |

### B2. OpenAI Codex CLI (`codex exec`)

| Punkt | Befund | Quelle |
|---|---|---|
| Version | npm `@openai/codex` **0.165.0** (28.10.), Apache-2.0, Rust (Notiz lokal) | https://registry.npmjs.org/@openai/codex (28.10.) |
| Headless | `codex exec "<prompt>"` (Kurzform `codex e`); Fortschritt auf stderr, **nur die letzte Agentennachricht auf stdout**; Pipe-Stdin wird als Zusatzkontext genommen; Unterbefehle `resume`, `fork` | https://learn.chatgpt.com/docs/non-interactive-mode.md (lokal 25.10.), https://learn.chatgpt.com/docs/developer-commands.md (28.10.) |
| Sandbox/Rechte | Standard in `exec`: **read-only**. `--sandbox workspace-write` (Bearbeiten im Ordner), `--sandbox danger-full-access` (nur in isolierter Umgebung). `--full-auto` **nicht mehr unterstützt**; Ersatz `--approve-for-me` (laut lokaler Doku) beziehungsweise `--sandbox workspace-write`. Approval-Werte laut Sandbox-Seite: `on-request`, `never` (`untrusted` entfernt). `--add-dir` statt Vollzugriff. `--ignore-user-config`, `--ignore-rules`. **Keine Werkzeug-Whitelist je Tool** wie bei CC; Steuerung über Sandbox-Modus und Execpolicy-`.rules` | non-interactive-mode (lokal), https://learn.chatgpt.com/docs/sandboxing.md (28.10.). Die `exec`-Flagtabelle wird auf der Seite per Komponente gerendert und war nicht abrufbar; `--approve-for-me` stand nur in der lokalen Kopie |
| Ausgabe | `--json`: JSONL-Ereignisse `thread.started`, `turn.started`, `turn.completed` (mit `usage`), `turn.failed`, `item.*`, `error`. `-o/--output-last-message <datei>` schreibt Endnachricht in Datei. `--output-schema <datei>` erzwingt JSON-Schema | non-interactive-mode (lokal 25.10.) |
| Fertig/Fehler | Ereignis `turn.completed` beziehungsweise `turn.failed`; `exec` bricht mit Fehler ab, wenn ein MCP-Server mit `required = true` nicht startet. **Exit-Codes: nicht belegt** | wie oben |
| Anbieter/Key | Standard: gespeicherte Anmeldung oder `CODEX_API_KEY` (nur für den einen Aufruf setzen, nicht job-weit). Eigene Anbieter in `config.toml` (`$CODEX_HOME`, Standard `~/.codex`): `[model_providers.<id>]` mit `name`, `base_url`, `env_key`, `http_headers`, `env_http_headers`, `auth{command…}`; Auswahl `model_provider = "<id>"`, Überschreiben per `-c key=value`. **Eigene Anbieter müssen Responses-API sprechen; `wire_api = "chat"` und reine Chat-Completions-Endpunkte werden nicht mehr unterstützt.** Ollama-Beispiel der Doku: `base_url = "http://localhost:11434/v1"` ohne `env_key` | https://learn.chatgpt.com/docs/config-file/config-advanced.md (28.10.), models (lokal 25.10.), auth (lokal 25.10.) |
| Arbeitsordner | Aktuelles Verzeichnis; `-C/--cd` (Flag nur indirekt bestätigt, `resume` zeigt `-C`); `--worktree` legt verwalteten Git-Worktree an. `--skip-git-repo-check`: auf Seite **nicht belegt** | developer-commands (28.10.) |
| Installation | `curl -fsSL https://chatgpt.com/codex/install.sh | sh`, Windows `irm https://chatgpt.com/codex/install.ps1 | iex`, npm `@openai/codex` | cli (lokal 25.10.) |
| Windows | Ja: native Windows-Sandbox in PowerShell, WSL2 nutzt Linux-Sandbox | sandboxing (28.10.) |
| Sicherheit | 3 CVEs (lokale NVD-Kopien: CVE-2025-61260, CVE-2026-19591, CVE-2026-19592); nicht ausgewertet. Hinweis der Doku: `OPENAI_API_KEY`/`CODEX_API_KEY` nicht als Job-Umgebung setzen, wenn Repo-Code läuft | auth/non-interactive (lokal) |

### B3. OpenCode (`opencode run`)

| Punkt | Befund | Quelle |
|---|---|---|
| Repo/Version | `anomalyco/opencode` (sst/opencode leitet dorthin um), MIT, ca. 221k Sterne. **Zwei Linien:** V1 npm `opencode-ai` **1.19.5** (28.10.), V2 npm `@opencode/cli` **2.1.4** (25.10.). `brew install opencode` = V2, `brew install anomalyco/tap/opencode` = V1; Installer-Skript und npm = V1 | https://github.com/anomalyco/opencode , npm (28.10.), https://opencode.ai/docs/ (28.10.) |
| Headless | `opencode run "<prompt>"`; Flags: `--model/-m provider/model`, `--agent`, `--file/-f`, `--format default|json` (rohe JSON-Ereignisse), `--dir`, `--continue/-c`, `--session/-s`, `--fork`, `--attach <url>` (laufender `opencode serve`), `--variant`, `--thinking`, `--auto`, `--port`, `--title` | https://opencode.ai/docs/cli/ (28.10.) |
| Rechte | Konfig-Schlüssel `permission` mit `allow`/`ask`/`deny` je Werkzeug (`read`, `edit`, `bash`, `webfetch`, `websearch`, `task`, `external_directory`, …) und Glob-Muster (letzte passende Regel gewinnt); `"permission": "allow"` für alles. Standard meist `allow`, `external_directory` und `doom_loop` `ask`, `.env` lesen `ask`. Nicht-interaktiv: `--auto` (alles außer ausdrücklich `deny`), `OPENCODE_PERMISSION` (Inline-JSON), `OPENCODE_CONFIG_CONTENT` (ganze Konfig inline). Wie `ask` ohne `--auto` behandelt wird: **nicht belegt** | https://opencode.ai/docs/permissions/ , cli (28.10.) |
| Anbieter/Key | Katalog über `/connect`, Schlüssel in `~/.local/share/opencode/auth.json`. Eigener Anbieter in `opencode.json`: `provider.<id>.npm = "@ai-sdk/openai-compatible"` (Chat Completions) oder `@ai-sdk/openai` (Responses), `options.baseURL`, `options.apiKey = "{env:VAR}"`, `models`. `baseURL` für `provider.anthropic` überschreibbar (Proxy). Config-Pfad per `OPENCODE_CONFIG`, `OPENCODE_CONFIG_DIR` | https://opencode.ai/docs/providers/ (28.10.); V2: `@opencode/ai/providers/openai-compatible`-Paket (lokal 25.10.) |
| Fertig/Fehler | Ausgabe `--format json`; **Exit-Codes nicht dokumentiert** | cli (28.10.) |
| Windows | Natives Windows via Chocolatey, Scoop, npm, Mise, Docker, Binaries; Doku **empfiehlt WSL** (Leistung, Funktionsumfang) | https://opencode.ai/docs/ (28.10.) |
| Sicherheit | Advisories (lokal 25.10.): GHSA-632h-h47v-g4x4 (hoch, bis 1.18.21, 24.09.2026), GHSA-c83v-7274-4vgp (kritisch, XSS im Web-UI, behoben 1.1.10), GHSA-vxw4-wv6m-9hhh (hoch, unauthentifizierter HTTP-Server, behoben 1.0.216). Presse (Sekundärquelle, 20.10.2026): stillschweigend gepatchte RCE über MCP-OAuth unter Windows/WSL, Versionen 1.0.137 bis 1.18.32, behoben in 1.18.33; Hersteller sieht bösartige MCP-Server „outside their threat model" | lokal `quellen/opencode/github-security-advisories-api-2026-10-25.json`, `infosecurity-opencode-rce-2026-10-25.html` (https://www.infosecurity-magazine.com/news/opencode-quietly-patched-critical/) |

### B4. DeepSeek-eigene Agent-CLI: **DeepSeek Harness, Befehl `dsh`**

| Punkt | Befund | Quelle |
|---|---|---|
| Offiziell? | **Ja.** Repo `deepseek-ai/deepseek-harness` (MIT, angelegt 13.08.2026), npm `@deepseek-ai/dsh`. DeepSeek-Doku führt „DeepSeek Harness" unter „Agent Integrations" und nennt es „developer preview". Das Kürzel „dsh" nennt die Integrationsseite selbst nicht, steht aber im README und im npm-Namen | https://github.com/deepseek-ai/deepseek-harness (lokal 25.10.), https://api-docs.deepseek.com/quick_start/agent_integrations/deepseek_harness (28.10.) |
| Reifegrad | README: „Developer preview … THERE WILL BE COMPATIBILITY-BREAKING CHANGES". SAFETY.md: keine Sicherheitsprüfung, nicht produktionsreif, Sandbox ohne Garantie, in Wegwerf-VM/Container laufen lassen. npm `latest` = `0.2.1-rc.2`, `next` = `0.2.1-rc.3`, `alpha` = `0.2.1-alpha.5` (25.10.). Lokal installiert: 0.1.5-rc.1. Keine veröffentlichten Advisories (25.10.) | lokal 25.10. |
| Headless | **`dsh --profile headless "job"`**: eine frische, gespeicherte Sitzung, gibt die Endantwort auf stdout aus und beendet sich. Reasoning-Deltas gehen auf stderr (`dsh: reasoning:`). Öffnet keine Ports. **Exit 0 = Aufgabe erledigt, 1 = abgebrochen oder Fehler** (Meldung `dsh: <code>: <message>` auf stderr); leere Aufgabe wird vor dem Start abgelehnt; eine Aufgabe je Aufruf. Die Benutzerdoku der Haupt-README (https://github.com/deepseek-ai/deepseek-harness/blob/master/apps/cli/README.md, 28.10.) sagt „gives no numeric exit codes"; die Exit-Aussage stammt aus dem Paket-README `dsh-headless` der installierten Version | installiertes Paket `~/.nvm/versions/node/v24.19.0/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai/dsh-headless/README.md` (lokal gelesen 28.10.) |
| Weitere Profile | `web` (Web-UI, Port 3080), `acp` (ACP über stdio), `sdk`/`sdk-minimal` (JSON-RPC über stdio), `plugin` | apps/cli README (28.10.) |
| Arbeitsordner | „The invoking directory is the default workspace root" | README (28.10.) |
| Modell/Anbieter/Key | Schlüssel in `$DSH_HOME/.credentials.yaml` (Web-UI schreibt sie; „write-only"), Einstellung in YAML-Patches (`cordis.patch.yml`, Profil-Ebene, Home-Ebene, `--patch`-Overlay); `--dump-config` zeigt das Ergebnis. Mitgelieferte Anbieter-IDs u. a. `anthropic`, `openai`, `moonshotai` (Kimi), `zai` (GLM), `openai-codex`; Umgebungsvariablen als Rückfallebene für Keys; eigene Anbieter über Adapter-Plugin (`LlmAdapter`) oder „custom OpenAI-compatible endpoints". Exakte **Umgebungsvariablennamen** und die **Config-Zeilen für headless** (Modell/Anbieter wählen): **nicht belegt** | docs/user/guide/providers.md (lokal 25.10.), llm-adapter.md (lokal 25.10.) |
| Rechte/Sandbox | Pakete `dsh-permission-presets` (`workspace-write` mit `approval: ask`, `danger-full-access` mit `approval: never`), `dsh-sandbox-local`, `dsh-fs-sandbox`, `dsh-bash-sandbox`, `dsh-pwsh-sandbox`, `dsh-sandbox-windows-acl`. Ob **headless** ohne Rückfragen läuft und wie man eine Werkzeug-Whitelist setzt: **nicht belegt** | installiertes Paketverzeichnis (28.10.) |
| Ausgabe | Nur Klartext der Endantwort; kein JSON-Modus für headless belegt (SDK-Profil liefert JSON-RPC) | s. o. |
| Installation | `npx @deepseek-ai/dsh web` oder npm global; Node.js nötig; aus Quelle `pnpm` | README |
| Windows | Windows-Sandbox-Pakete vorhanden (`dsh-pwsh-sandbox`, `dsh-sandbox-windows-acl`); die CLI-Doku enthält „no Windows-specific guidance" → **offizielle Windows-Unterstützung nicht belegt** | apps/cli README (28.10.) |

### B5. Antigravity CLI (`agy`)

| Punkt | Befund | Quelle |
|---|---|---|
| Einordnung | Google-Produktfamilie (App, CLI, IDE, SDK). Gemini CLI wird laut Google-Doku durch `agy` abgelöst (Migrationsseite: `agy plugin import gemini`, Konfiguration wandert von `~/.gemini/settings.json` zu `mcp_config.json`). Antigravity-App v2.26.0 (22.10.2026) | https://antigravity.google/docs/cli/gcli-migration (lokal 25.10.) |
| Headless | **`agy -p "<prompt>"`** (Alias `--print`, `--prompt`). Flags: `--output-format text|json|stream-json`, `--input-format text|stream-json`, `--json-schema`, `--model <slug>` (`agy models`), `--effort low|medium|high`, `--agent`, `--dangerously-skip-permissions`, `--continue/-c`, `--conversation <id>`, `--print-timeout` (Standard 5 min), `--sandbox` | https://antigravity.google/docs/cli/headless/ (28.10.) |
| Arbeitsordner | Beispiel der Best-Practices-Seite: `agy -p "…" --cwd $(pwd)`; die Headless-Seite listet kein cwd-Flag; Widerspruch, **nicht abschließend belegt** | https://antigravity.google/docs/cli/best-practices (28.10.) |
| Rechte | Ohne `--dangerously-skip-permissions` werden genehmigungspflichtige Werkzeuge „soft-denied": **Lauf endet mit Exit 0 und Hinweis auf stderr**. Vorab-Freigaben: `permissions.allow` mit `action(target)` in `~/.gemini/antigravity-cli/settings.json`; `toolPermission` = `request-review` (Standard), `proceed-in-sandbox`, `strict`. Regelpriorität Deny > Ask > Allow. Sandbox: macOS `sandbox-exec`, Linux Namespaces (Doku-Index, lokal) | headless, best-practices (28.10.); permissions/sandbox (lokal 25.10.) |
| Ausgabe | JSON: `conversation_id`, `status` (`SUCCESS`, `ERROR`, `CANCELED`, `INTERRUPTED`, `INVALID`, `WAITING`, `RUNNING`), `response`, `error`, `duration_seconds`, `num_turns`, `usage{…}`, `structured_output`. Stream: `init` (mit `cwd`, `tools`, `permission_mode`), `step_update`, `result` | headless (28.10.) |
| Exit-Codes | 0 Erfolg; nicht 0 = keine Antwort (Beispiele: 1 unbekanntes Modell/ungültige Eingabe, 2 Steuerereignisse im Stream-Input). Unangemeldet nicht-interaktiv: Fehler `authentication required`, kein Hängen | headless (28.10.) |
| Anbieter/Key | Anmeldung per Google-Konto, Gemini-Enterprise/Cloud, ADC, Schlüsselbund oder „Using a Gemini API key" (Abschnittstitel der Installationsseite, lokal). Headless nutzt **gecachte Anmeldedaten** (einmal interaktiv anmelden); `GEMINI_API_KEY` für die CLI auf der Headless-Seite **nicht erwähnt** (nur für das SDK belegt). **Nicht-Google-Modellendpunkte in `agy`: nicht belegt** (kein Beleg, dass es geht) | headless (28.10.); docs-install, sdk-overview (lokal 25.10.) |
| ToS | FAQ: Zugriff auf Antigravity mit Drittwerkzeugen unter Antigravity-Login „is a violation of our Terms of Service" (Sperrung möglich); für Drittagenten wird ein Gemini-Enterprise- oder AI-Studio-API-Key empfohlen; `agy` in Drittanwendungen einzubetten oder Konten zu rotieren sei unter Privatplänen „not supported". Headless sei für „direct scripting and CI workflows" gedacht | https://antigravity.google/docs/faq (28.10.) |
| Installation/Windows | Installer je Oberfläche (Details nicht ausgewertet); Windows-Erkennung auf der Seite vorhanden, **Windows-Support der CLI nicht belegt** | docs-install (lokal 25.10.) |
| Repo | `google-antigravity/antigravity-cli`: laut GitHub-API keine Lizenz hinterlegt; SDK Apache-2.0 | lokal 25.10. |

### B6. Optional: Aider, Goose, Crush

| CLI | Headless | Anbieter/Rechte | Ausgabe/Exit | Windows | Quelle (28.10.) |
|---|---|---|---|---|---|
| **Aider** | `--message/-m "…"` (oder `--message-file/-f`, Umgebungsvariable `AIDER_MESSAGE`) wendet an und beendet sich; `--yes` bestätigt alles; `--commit`, `--dry-run`, `--no-auto-commits` | `--model`, `--openai-api-base`, Key-Variablen: auf der Seite **nicht belegt** | Kein JSON belegt, Exit-Codes **nicht belegt**; Python-API ausdrücklich „not officially supported" | **nicht belegt** | https://aider.chat/docs/scripting.html |
| **Goose** (jetzt unter AAIF) | `goose run -t "…"` / `-i <datei>` / `-i -`; beendet sich nach Aufgabe; `--no-session`; `--provider`, `--model`; `--with-*-extension`; `--recipe` | Rechte (`GOOSE_MODE`): **nicht belegt** | `--output-format json|stream-json`; Exit-Codes **nicht belegt** | `NUL` erwähnt, sonst **nicht belegt** | https://goose-docs.ai/docs/guides/running-tasks |
| **Crush** (Charm) | Seite zeigt `crush run` **nicht** (dort „not in the page"); Flags `--yolo`, `--debug`, `--cwd` | Vorab-Freigabe/Sperre per `permissions allow view ls grep edit` / `permissions deny bash sourcegraph`; Anbieter: `openai-compat` mit `--base-url`, `--type anthropic` mit Base-URL; Beispiel DeepSeek `https://api.deepseek.com/v1`. Lizenz **FSL-1.1-MIT** | Ausgabe/Exit **nicht belegt** | Ja: PowerShell und WSL, `winget install charmbracelet.crush`, Scoop | https://github.com/charmbracelet/crush |

### B7. Tabelle Runner × Fähigkeit

Legende: **ja** = belegt, **teilw.** = belegt mit Einschränkung, **nb** = nicht belegt.

| Runner | Headless-Befehl | Eigener Anbieter wählbar | Tool-Whitelist | JSON-/Stream-Ausgabe | Exit-Code dokumentiert | Arbeitsordner | Windows |
|---|---|---|---|---|---|---|---|
| **claude** (CC) | `claude -p` ja | ja, nur Anthropic-Format (Env oder `settings.json`) | ja (`--allowed-tools`, `--tools`, `dontAsk`) | ja (`json`, `stream-json`) | ja (0 / nicht 0, SIGTERM 143) | aktuelles Verzeichnis, `--add-dir` | ja (Git for Windows empfohlen) |
| **codex** | `codex exec` ja | ja, nur Responses-API-Endpunkte | teilw. (Sandbox-Modi und Execpolicy, keine Einzelwerkzeug-Liste) | ja (`--json`, `-o`, `--output-schema`) | nb | aktuelles Verzeichnis, `-C`/`--cd` teilw., `--worktree` | ja (native Sandbox, WSL2) |
| **opencode** | `opencode run` ja | ja (Katalog, OpenAI-kompatibel, Anthropic-baseURL) | ja (`permission`-Regeln, `--auto`, `OPENCODE_PERMISSION`) | ja (`--format json`) | nb | `--dir` | ja, Doku rät zu WSL |
| **dsh** | `dsh --profile headless "…"` ja | ja (Kimi, GLM, OpenAI, Anthropic, eigene Adapter); Headless-Konfiguration nb | nb (Sandbox/Approval-Presets vorhanden) | nein (Klartext der Endantwort) | teilw. (0/1 im Paket-README, Haupt-README „keine numerischen Codes") | aufrufendes Verzeichnis | nb |
| **agy** | `agy -p` ja | nb (Google-Anmeldung/Gemini-Key; keine Fremdendpunkte belegt) | teilw. (`permissions.allow`, Soft-Deny, `--sandbox`) | ja (`json`, `stream-json`) | ja, aber Soft-Deny liefert Exit 0 | `--cwd` widersprüchlich belegt | nb |
| aider | `aider -m` ja | nb | nein | nb | nb | nb | nb |
| goose | `goose run -t` ja | teilw. (`--provider`, `--model`) | nb | ja | nb | nb | nb |
| crush | `crush run` nb | ja (openai-compat, anthropic-Typ) | ja (`permissions allow/deny`) | nb | nb | `--cwd` | ja |

---

## Empfehlung: Welche Runner zuerst

| Rang | Runner | Begründung |
|---|---|---|
| 1 | **claude** | Bestdokumentierter Headless-Weg mit Exit-Code, Stream-JSON, feinster Werkzeug-Whitelist und Isolation (`--setting-sources`, `--strict-mcp-config`, `--bare`). Deckt per Base-URL ohne Übersetzer sieben der neun Anbieter ab (DeepSeek, OpenRouter, Kimi, Ollama, Z.ai, MiniMax, Anthropic). Heutiger Wrapper bereits darauf gebaut. |
| 2 | **codex** | Sauberes `exec` mit JSONL, `-o`, Schema, Sandbox, Windows-Sandbox. Eigene Anbieter nur mit Responses-Endpunkt: deckt OpenAI und potenziell EUrouter (listet `/responses`; Kompatibilität mit Codex-Gateway-Anforderungen **nicht geprüft**) ab. Bringt ein zweites Modell-Ökosystem. |
| 3 | **opencode** | Anbieterneutral (Katalog plus beliebige OpenAI-kompatible Endpunkte inkl. Nvidia, EUrouter ohne Proxy), Rechte als Konfiguration, JSON-Ausgabe. Lücken: Exit-Codes nicht dokumentiert, zwei Versionslinien (V1/V2), jüngere Sicherheitsvorfälle; deshalb Version festlegen und Exit-Auswertung über `bericht.md` statt Exit-Code. |
| 4 | **dsh** (als „experimentell" markiert) | Offizielles DeepSeek-Harness mit einfachem `--profile headless`, aber Developer Preview mit angekündigten Breaking Changes, Konfiguration für headless nicht belegt, kein JSON, Windows nicht belegt. Erst aufnehmen, wenn Schnittstelle stabil (Release ohne `rc`/`alpha`). |
| später | agy | Fremdanbieter nicht belegt, Soft-Deny mit Exit 0 ist eine Falle, ToS-Hinweise zu Drittwerkzeugen; nur sinnvoll als reiner Gemini-Runner mit API-Key. |
| später | Crush, Goose, Aider | Lücken in der Belegbarkeit des Headless-Verhaltens (Crush `run` nicht belegt; Aider ohne JSON/Exit-Doku). |

### Gemeinsame Adapter-Schnittstelle

**Grundprinzip:** Die Wahrheit über „fertig" ist weder der Exit-Code noch die Ausgabe des Runners, sondern der **Vertrag `bericht.md`** im Laufordner (so macht es der Wrapper heute). Der Exit-Code ist nur Zusatzsignal, weil er je Runner unterschiedlich belegt ist (agy: Soft-Deny = 0; opencode/codex: nicht belegt).

**Eingabe (`auftrag.json` oder CLI-Argumente an den Adapter):**

| Feld | Bedeutung |
|---|---|
| `auftrag` | Pfad zur Auftragsdatei (`auftrag.md`), wird in den Laufordner kopiert |
| `arbeitsordner` | Leerer Laufordner (Standard) oder angegebener Projektordner; Adapter setzt cwd selbst (`cd`, `--dir`, `-C`, `--cwd`) |
| `runner` | `claude` / `codex` / `opencode` / `dsh` |
| `anbieter` | Eintrag aus eigener Anbieterliste: `id`, `protokoll` (`anthropic` / `openai-chat` / `openai-responses`), `base_url`, `key_name`, Modell-Tabelle |
| `modell` | Name oder Alias aus dieser Tabelle |
| `werkzeuge` | Neutrale Liste, z. B. `lesen`, `schreiben`, `shell`, `web_suche`, `web_laden`; Adapter übersetzt (CC: `--allowed-tools` plus `dontAsk`; OpenCode: `permission`-JSON; Codex: `--sandbox read-only|workspace-write`; dsh: Preset) |
| `limit` | `max_runden`, `max_kosten`, `zeitlimit_s` (CC: `--max-turns`, `--max-budget-usd`; sonst Adapter-Timeout per Prozessgruppe) |

**Ausgabe (immer im Laufordner):**

| Datei | Inhalt |
|---|---|
| `bericht.md` | Ergebnis, vom Agenten laut Auftrag geschrieben. Vorhanden = fertig |
| `log.jsonl` | Rohausgabe des Runners (CC `stream-json`, Codex `--json`, OpenCode `--format json`, agy `stream-json`; dsh Klartext) |
| `fehler.log` | stderr |
| `status.json` | `zustand` (`arbeitet` / `fertig` / `fehler` / `abgebrochen`), `start`, `ende`, `exitcode`, `runner`, `anbieter`, `modell`, optional `kosten`, `runden` |
| Exitcode des Adapters | 0 = `bericht.md` vorhanden und Runner-Exit 0; 1 = Runner-Fehler; 2 = Konfigurationsfehler (fehlender Key, Runner nicht installiert); 3 = Proxy/Endpunkt nicht erreichbar; 124 = Zeitlimit |

**Adapter-Pflichten (aus den belegten Fallen):**

1. Umgebung bereinigen (`env -i` plus Nötigstes), je Runner nur den **einen** benötigten Key reinreichen; bei CC `ANTHROPIC_API_KEY` leer halten; bei Codex `CODEX_API_KEY` nur für den Aufruf.
2. CC mit `--setting-sources project`, `--strict-mcp-config`, `--no-session-persistence`, leerem Ordner (oder `--bare` + API-Key, wo kein OAuth nötig ist), weil `-p` sonst Hooks und MCP des Arbeitsordners ausführt.
3. Alle Modell-Variablen setzen (`ANTHROPIC_MODEL`, `*_OPUS/SONNET/HAIKU_MODEL`, `CLAUDE_CODE_SUBAGENT_MODEL`), sonst scheitern Hintergrundstufen still (Kimi-Seite).
4. Auftragstext immer mit Aufrufbegrenzung und Ergebnisformat (lokaler DeepSeek-Test: ohne Limit 232 s, mit Limit 16 s).
5. Fertig = `bericht.md`; zusätzlich Runner-Signal auswerten: CC letzte `result`-Zeile, Codex `turn.completed`/`turn.failed`, agy `status`, dsh Exit 0/1.
6. Lieferkettenvorsicht: Runner-Versionen pinnen; LiteLLM/Proxy nur optional und mit Pin (Abschnitt A3).
7. Tokens nie speichern oder weiterreichen (Abschnitt A5).

---

## Gesamtliste: nicht belegt

- Ollama: Mindestversion für die Anthropic-API (beide Doku-Seiten nennen keine; GitHub-Releases nicht geprüft).
- EUrouter: Existenz eines Messages-Pfads endgültig ausgeschlossen (OpenAPI nur zu 100.000 von 278.743 Zeichen gelesen); Codex-Kompatibilität über `/responses`; Preise; Aufbewahrungsfristen.
- Kimi, Z.ai, MiniMax: Preise, Datenstandort/DSGVO, WebSearch-/WebFetch-Funktion in Claude Code.
- OpenRouter: Preise, Datenstandort, Websuche über die Anthropic-Schnittstelle.
- Nvidia NIM: Anthropic-Endpunkt (nur „nicht erwähnt"), Free-Tier-Limits und Nutzungsbedingungen, Datenstandort.
- DeepSeek: rechtliche DSGVO-Bewertung (nur Speicherort China und Trainingsnutzung aus der Datenschutzerklärung).
- LiteLLM: ob 1.106.4/1.106.5 vom Hersteller ausdrücklich als nachvollzogen sauber bestätigt sind; Claude-Code-Anleitung von Hersteller; `/v1/responses` für Nicht-OpenAI-Ziele.
- claude-code-router: Konfigurationsschema, Inhalt des Sicherheits-Tabs, Datum des letzten Commits; andere Übersetzer-Proxies nicht untersucht.
- Claude Code: Feldnamen des `result`-Objekts (`is_error`/`subtype`) auf den abgerufenen Seiten; Verhalten von `--bare` mit `ANTHROPIC_AUTH_TOKEN`; ob unbeaufsichtigte Läufe mit Abo-Token zulässig sind.
- Codex: Exit-Codes, vollständige `exec`-Flagtabelle (`--model`, `--cd`, `--skip-git-repo-check`, `--approve-for-me` nur lokal gesehen).
- OpenCode: Exit-Codes, Behandlung von `ask` ohne `--auto`, Config-Pfad.
- dsh: Umgebungsvariablennamen für Keys, Headless-Modellkonfiguration, Werkzeug-Whitelist, Windows-Support, JSON-Ausgabe.
- agy: `--cwd`-Verhalten, Windows, Fremdendpunkte, `GEMINI_API_KEY` in der CLI.
- Aider, Goose, Crush: Exit-Codes, Rechte, Windows-Details teils nicht belegt; Crush `run` nicht belegt.
- Alle Aussagen mit „(lokal 25.10.)" wurden heute nicht erneut gegen die Hersteller-URL geprüft.
