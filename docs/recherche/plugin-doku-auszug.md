# Claude-Code-Plugins: Theorie und Praxis (Stand Claude Code 2.1.304)

Quellen: offizielle Doku unter code.claude.com/docs (Seiten sind je Abschnitt genannt), lokale Praxis unter `~/.claude/plugins/`. Belegt = steht in der fetchten Doku oder ist lokal geprüft. Nicht belegt = in der Doku nicht gefunden.

Abgrenzung: Der lokale Skill `/plugin-authoring` (Mods) betrifft UI-Panes. Ein Mod ist ein Plugin mit einem JavaScript-Hooks-Modul (`modules` in `hooks/hooks.json`). Für Omni-Agent ist das nicht gemeint. Siehe `plugins/mods/overview` und `plugins/overview`.

---

## 1. Begriffe und Komponenten

Plugin = Ordner mit optionalem Manifest `.claude-plugin/plugin.json`, der Komponenten bündelt und als Einheit lädt. Marketplace = Katalog (`.claude-plugin/marketplace.json`), der Plugins und deren Quelle auflistet. Quelle: `plugins/overview`, `plugins/create-marketplace`.

| Komponente | Standardort im Plugin | Was es tut | Quelle |
|---|---|---|---|
| Skills | `skills/<name>/SKILL.md` | Anweisungen, die Claude bei passender `description` lädt; auch als `/plugin:skill` aufrufbar | `plugins/components`, `skills` |
| Commands (alt) | `commands/*.md` | Wie Skills, nur eine Datei. Für neue Plugins Skills nehmen | `plugins/components` |
| Agents (Subagents) | `agents/*.md` | Eigener Assistent mit eigenem Kontext; Markdown-Body = Systemprompt | `plugins/components`, `sub-agents` |
| Hooks | `hooks/hooks.json` | Shell-/HTTP-/MCP-Tool-/Prompt-Aktionen bei Lebenszyklusereignissen | `plugins/components`, `hooks` |
| MCP-Server | `.mcp.json` (oder Key `mcpServers`) | Tools aus externen Prozessen/Diensten | `plugins/components`, `mcp` |
| LSP-Server | `.lsp.json` | Diagnose und Navigation für eine Sprache | `plugins/components` |
| Output-Styles | `output-styles/<name>.md` | Antwortstil, erscheint in `/output-style` als `<plugin>:<name>` | `plugins/components` |
| Themes | `themes/<slug>.json` (Manifest `experimental.themes`) | Farbschema für `/theme` | `plugins/components`, `manifest-reference` |
| Monitors | `monitors/monitors.json` (Manifest `experimental.monitors`) | Hintergrund-Shellbefehl, dessen Ausgabe Claude als Benachrichtigung erhält. Startet nicht mit `-p` | `plugins/components` |
| `bin/` | `bin/<datei>` | Dateien landen im PATH des Bash-Tools, solange das Plugin aktiv ist | `plugins/components` |
| `settings.json` | Plugin-Root | Wirkt nur mit zwei Schlüsseln: `agent`, `subagentStatusLine`. Rest wird verworfen | `plugins/components` |
| Workflows | `workflows/*.js` (Manifest `workflows`) | Skripte, die mehrere Subagents orchestrieren | `manifest-reference` (nur Feld belegt, Details nicht gelesen) |
| Channels | Manifest `channels` + MCP-Server | Nachrichten von außen in eine Session | `plugins/components`, `manifest-reference` |
| Mods (JS-Module) | `modules` in `hooks/hooks.json` | JavaScript im Claude-Code-Prozess, siehe oben | `plugins/mods/overview` |
| CLAUDE.md im Plugin-Root | – | Wird NICHT geladen. Anweisungen gehören in eine Skill | `plugins/components`, `manifest-reference` |

Marketplace und Plugin: Ein Marketplace ist nur ein Katalog. Die Plugins liegen woanders (im selben Repo, auf GitHub, auf git-URL, als npm-Paket, als Archiv). Quelle: `plugins/marketplace-reference`.

---

## 2. Verzeichnislayout

Plugin-Root = Ordner, der `.claude-plugin/` enthält. Nur `plugin.json` gehört in `.claude-plugin/`. Alles andere (skills, hooks, bin, ...) liegt im Root. Quelle: `plugins/manifest-reference` (Standard layout), `plugins/create`.

```text
omni-agent/
├── .claude-plugin/
│   ├── plugin.json          # Manifest (optional, aber für Name/Version/userConfig nötig)
│   └── marketplace.json     # nur wenn das Repo auch Marketplace ist
├── skills/agent-start/SKILL.md
├── agents/
├── hooks/hooks.json
├── .mcp.json
├── bin/omni-agent            # chmod +x empfohlen (siehe Abschnitt 8)
├── scripts/
├── package.json + package-lock.json   # nur wenn npm-Abhängigkeiten
└── settings.json            # optional, nur agent/subagentStatusLine
```

Lokales Beispiel: `~/.claude/plugins/marketplaces/claude-plugins-official/plugins/feature-dev/` hat genau dieses Muster (`.claude-plugin/plugin.json`, `commands/feature-dev.md`, `agents/*.md`, `README.md`, `LICENSE`).

---

## 3. `.claude-plugin/plugin.json`

Quelle: `plugins/manifest-reference` (Fields, Path rules, User configuration). Einziges Pflichtfeld: `name`.

| Feld | Typ | Pflicht | Hinweis |
|---|---|---|---|
| `name` | string | ja | kebab-case, keine Leerzeichen, `@`, `:`, Pfadtrenner. Namensraum für alle Komponenten |
| `displayName` | string | nein | nur Anzeige |
| `version` | string | nein | nicht semver-geprüft. Gesetzt = Nutzer bleiben auf dieser Version, bis sie geändert wird |
| `description` | string | nein | Text in `/plugin` |
| `author` | object | nein | `name` Pflicht; `email`, `url` optional |
| `homepage` | string | nein | muss als URL parsbar sein, sonst lädt das Plugin nicht |
| `repository` | string | nein | nicht validiert |
| `license` | string | nein | SPDX, z. B. `MIT` |
| `keywords` | string[] | nein | Suche |
| `metadata` | object | nein | frei, Claude Code liest es nicht (ab 2.1.222) |
| `icon`, `documentationUrl`, `supportUrl`, `privacyPolicyUrl`, `termsOfServiceUrl` | string | nein | nur für Anthropic-Verzeichnis |
| `defaultEnabled` | boolean | nein | Standard `true` |
| `dependencies` | (string \| object)[] | nein | `"name"`, `"name@marketplace"` oder `{name, marketplace?, version?}` |
| `settings` | object | nein | nur `agent`, `subagentStatusLine` wirken |
| `userConfig` | object | nein | Werte, nach denen beim Aktivieren gefragt wird (Abschnitt 6) |
| `channels` | object[] | nein | Kanal-Bindung an einen MCP-Server |
| `skills` | Pfad \| Pfad[] | nein | ZUSÄTZLICH zum Standard `skills/`. `"."` oder `"./"` = Root |
| `commands` | Pfad \| Pfad[] \| Objekt | nein | ERSETZT den Standard `commands/` |
| `agents` | Pfad \| Pfad[] | nein | ERSETZT `agents/`; nur `.md`-Dateien |
| `hooks` | Pfad \| Objekt \| Array | nein | ZUSÄTZLICH zu `hooks/hooks.json` |
| `mcpServers` | Pfad \| Objekt \| Array | nein | ZUSÄTZLICH zu `.mcp.json`; gleicher Name = späterer ersetzt früheren |
| `lspServers` | Pfad \| Objekt \| Array | nein | ZUSÄTZLICH zu `.lsp.json` |
| `outputStyles` | Pfad \| Pfad[] | nein | ERSETZT `output-styles/` |
| `workflows` | Pfad \| Pfad[] | nein | ERSETZT `workflows/` |
| `experimental` | object | nein | `themes`, `monitors`, `evals` (Form kann sich ändern) |

Pfadregeln: Jeder Komponentenpfad beginnt mit `./` (außer `"."` bei `skills`), bleibt im Plugin-Root, existiert. `..` und Backslashes auf macOS/Linux werden abgelehnt.

Minimalbeispiel (Quelle: `plugins/create`):
```json
{
  "name": "my-first-plugin",
  "description": "A greeting plugin to learn the basics",
  "version": "1.0.0",
  "author": { "name": "Your Name" }
}
```

---

## 4. `.claude-plugin/marketplace.json`

Quelle: `plugins/marketplace-reference`, `plugins/create-marketplace`, `plugins/host-marketplace`.

Top-Level:

| Feld | Pflicht | Hinweis |
|---|---|---|
| `name` | ja | Buchstaben, Ziffern, `.`, `_`, `-`. Nutzer tippen es nach `@`: `plugin@<name>` |
| `owner` | ja | `{ "name": ..., "email"?, "url"? }` |
| `plugins` | ja | Array der Plugin-Einträge |
| `description`, `version` | nein | `description` fehlt = Validator-Warnung |
| `metadata.pluginRoot` | nein | Basisordner, damit `"source": "formatter"` nach `./plugins/formatter` auflöst (ab 2.1.239) |
| `renames` | nein | alter Name → neuer Name oder `null` (entfernt). Verhindert „not found“ bei Umbenennung |
| `forceRemoveDeletedPlugins` | nein | `true` = entfernte Plugins werden bei Nutzern deinstalliert |
| `allowCrossMarketplaceDependenciesOn` | nein | Erlaubt Abhängigkeiten aus fremden Marketplaces |

Plugin-Eintrag (`plugins[]`): `name` und `source` Pflicht. Dazu `description`, `version`, `category`, `tags`, `strict` (Standard `true`), `defaultEnabled`, `displayName`, `dependencies`, `metadata`, `headers`/`headersHelper` (nur für `archive`), `relevance`. Alle Felder aus `plugin.json` sind ebenfalls erlaubt.

`source`-Varianten (Quelle: `plugins/marketplace-reference` → „Plugin sources“):

| Form | Beispiel | Hinweis |
|---|---|---|
| Relativer Pfad (String) | `"./"` oder `"./plugins/x"` | Muss mit `./` beginnen, Pfad relativ zum Marketplace-Root (nicht zu `.claude-plugin/`) |
| `github` | `{"source":"github","repo":"owner/repo","ref":"v1","sha":"<40 hex>"}` | `ref`/`sha` optional |
| `url` | `{"source":"url","url":"https://host/x.git","ref":"main"}` | beliebige git-URL |
| `git-subdir` | `{"source":"git-subdir","url":"owner/mono","path":"tools/x"}` | Unterordner eines Repos, Sparse-Checkout |
| `npm` | `{"source":"npm","package":"@org/x","version":"^2.0.0"}` | Lifecycle-Skripte laufen nicht |
| `archive` | `{"source":"archive","url":"https://...zip","sha256":"<64 hex>"}` | nur https; `sha256` prüft Download |
| `command` | `{"source":"command","command":"tool path"}` | Befehl druckt Verzeichnis; Nutzer muss Befehl bestätigen |

Hinweis `strict`: Hat das Plugin eine eigene `plugin.json` und der Eintrag setzt `commands`, `agents`, `skills`, `hooks`, `outputStyles` oder `themes`, dann: `strict: true` (Default) = wird angehängt (bei `hooks` ersetzen die Matcher je Event). `strict: false` = Konflikt, Plugin lädt nicht.

`version`-Auflösung (`plugins/loading`, „Versions and updates“): 1. `version` in `plugin.json`, 2. `version` im Eintrag, 3. je nach Quelle: github/url/git-subdir = Commit-SHA (12 Zeichen); archive = sha256; relativer Pfad in git-Marketplace = Commit-SHA des Ordners; npm = `unknown`.

Beispiel-Marketplace im selben Repo (Quelle: `plugins/publish`):
```json
{
  "name": "your-marketplace",
  "owner": { "name": "Your Name" },
  "plugins": [
    { "name": "deploy-helper", "source": "./" }
  ]
}
```

Lokales Beispiel: `~/.claude/plugins/marketplaces/claude-plugins-official/.claude-plugin/marketplace.json` hat `$schema`, `name`, `description`, `owner`, `renames` und `plugins[]` mit `git-subdir`-Quellen inkl. `ref` und `sha`.

---

## 5. Namensräume, Skills vs. Commands, Frontmatter

Namensräume (Quelle: `plugins/components`, `skills`, `sub-agents`):
- Skill `skills/review/SKILL.md` im Plugin `my-plugin` → `/my-plugin:review`. Frontmatter-`name` ersetzt nur das letzte Segment.
- Command `commands/db/migrate.md` → `/my-plugin:db:migrate`.
- Agent `agents/security-reviewer.md` → `my-plugin:security-reviewer`; Aufruf `@agent-my-plugin:security-reviewer`. Unterordner werden Teil des Namens (`agents/review/security.md` → `my-plugin:review:security`).
- Manifest-Name ≠ Eintrags-Name: Installation erfolgt über Eintrags-Namen; Namensraum der Komponenten ist der Manifest-Name. Gleich halten (`plugins/marketplace-reference`).

Skills vs. Commands (Quelle: `skills`, `plugins/components`): Commands sind die ältere Form. Skills unterstützen zusätzlich Hilfsdateien im Ordner und Auto-Laden. Dieselbe Datei kann beides sein; beide funktionieren weiter.

Frontmatter-Felder von Skills (Quelle: `skills`, Abschnitt Frontmatter; nicht vollständig gelesen, Liste laut Fetch):

| Feld | Bedeutung |
|---|---|
| `name` | Befehlsname (Standard: Ordnername) |
| `description` | Wann die Skill greift; wird mit `when_to_use` auf 1.536 Zeichen gekürzt |
| `when_to_use` | zusätzlicher Auslösetext |
| `argument-hint` | Autocomplete-Hinweis, z. B. `[aufgabe]` |
| `arguments` | benannte Argumente für `$name` |
| `disable-model-invocation: true` | nur Nutzer kann aufrufen |
| `user-invocable: false` | nur Claude kann aufrufen, nicht im `/`-Menü |
| `allowed-tools` | Tools ohne Rückfrage im Zug der Skill. Schränkt NICHT ein. Wird beim nächsten Nutzer-Satz gelöscht |
| `disallowed-tools` | Tools entfernen, solange Skill aktiv |
| `model`, `effort` | nur für den aktuellen Zug |
| `context: fork` | Läuft in Subagent. Kein Zugriff auf Gesprächsverlauf |
| `agent` | Subagent-Typ bei `context: fork` (Standard `general-purpose`) |
| `background` | bei `fork`: Standard `true`; `false` wartet auf Ergebnis |
| `hooks` | Hooks, die beim Aufruf registriert werden und bis Sitzungsende bleiben |
| `paths` | Glob-Muster für automatische Aktivierung |
| `shell` | `bash` (Standard) oder `powershell` für `` !`cmd` `` |

Substitutionen in Skill-Text: `$ARGUMENTS`, `$0`/`$ARGUMENTS[0]`, `$name` (bei `arguments`), `${CLAUDE_SKILL_DIR}`, `${CLAUDE_SESSION_ID}`, `${CLAUDE_EFFORT}`, `${CLAUDE_PROJECT_DIR}`, `${CLAUDE_PLUGIN_ROOT}`, `${CLAUDE_PLUGIN_DATA}` (nur Plugin-Skills). `` !`befehl` `` läuft vor dem Senden; schlägt er fehl, bricht der Aufruf ab.

Agent-Frontmatter im Plugin (Quelle: `plugins/components`, Agents): unterstützt u. a. `name`, `description`, `model`, `effort`, `maxTurns`, `tools`, `disallowedTools`, `skills`, `memory`, `background`, `isolation` (nur `worktree`), `color`. IGNORIERT werden `permissionMode`, `hooks`, `mcpServers`, `initialPrompt`. Hooks und MCP-Server gehören also ins Plugin, nicht in die Agent-Datei.

Lokales Beispiel `feature-dev/commands/feature-dev.md`: `description`, `argument-hint`. `feature-dev/agents/code-reviewer.md`: `name`, `description`, `tools`, `model`, `color`.

---

## 6. Variablen, Daten, userConfig, Umgebungsvariablen

Pfadvariablen (Quelle: `plugins/manifest-reference` → Environment variables; `plugins/components` → Path variables):

| Variable | Wert | Zweck |
|---|---|---|
| `${CLAUDE_PLUGIN_ROOT}` | Installationsordner der aktiven Version (`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`) | Skripte und Binaries. ÄNDERT sich bei Update, also dort nichts speichern |
| `${CLAUDE_PLUGIN_DATA}` | `~/.claude/plugins/data/<id>/` (id: Zeichen außer Buchstaben/Ziffern/`_`/`-` → `-`) | Persistent über Updates: `node_modules`, Venvs, Caches, Zustand. Wird beim Deinstallieren aus letztem Scope gelöscht (außer `--keep-data`) |
| `${CLAUDE_PROJECT_DIR}` | Projektwurzel | Projektlokale Dateien |

Wo aufgelöst (Quelle: `plugins/manifest-reference`, Tabelle „Where each variable resolves“):
- Hook-`command`/`args`: Ersetzung und Umgebung.
- Monitor-`command`: Ersetzung, keine Umgebungsvariablen.
- MCP stdio `command`/`args`/`env`: Ersetzung; Umgebung bekommt `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA`.
- MCP http/sse/ws `url`/`headers`: Ersetzung.
- LSP `command`/`args`/`env`/`workspaceFolder`.
- Skill-/Command-/Agent-Text: Ersetzung im Markdown.
- Nicht in der Umgebung von Befehlen, die Claude über das Bash-Tool startet. Doku-Wortlaut: „The variables aren't present in the environment of commands Claude runs through the Bash tool.“ Folge: Ein `bin/`-Skript kann `${CLAUDE_PLUGIN_ROOT}` nicht aus der Umgebung lesen. Empfehlung (eigene Schlussfolgerung, nicht Doku): Pfad aus `$0` ableiten, z. B. `ROOT="$(cd "$(dirname "$0")/.." && pwd)"`.

Umgebungsvariablen für Prozesse (Hooks bekommen zusätzlich `CLAUDE_PLUGIN_OPTION_<KEY>`; Monitore bekommen KEINE Optionswerte).

### userConfig (Quelle: `plugins/manifest-reference` → User configuration; `plugins/components` → Ask the user for configuration values)

Felder je Option (strikt, unbekannte Schlüssel = Fehler):

| Feld | Pflicht | Hinweis |
|---|---|---|
| `type` | ja | `string`, `number`, `boolean`, `directory`, `file` |
| `title` | ja | Dialog-Label |
| `description` | ja | Hilfetext |
| `required` | nein | Dialog akzeptiert keine leere Eingabe |
| `default` | nein | string, number, boolean oder string[] |
| `options` | nein | feste Auswahl (nur `string`, nicht `sensitive`/`multiple`; ab 2.1.271) |
| `multiple` | nein | string[] |
| `sensitive` | nein | maskiert, Speicherort = sicherer Speicher |
| `min`, `max` | nein | für `number` |

Schlüssel: Buchstaben, Ziffern, Unterstrich, nicht mit Ziffer beginnend.

Speicherort: Nicht-sensible Werte stehen in `pluginConfigs` der `settings.json`. Sensible Werte gehen in den „platform's secure credential store“. Ob das beim Mac die Schlüsselbund-Anwendung ist, steht im gelesenen Text NICHT (nicht belegt).

Abruf des Werts:
- `${user_config.KEY}`: in MCP-Config (`command`, `args`, `env`, `url`, `headers`), LSP-Config, Exec-Form-Hook-`args`, Skill-/Agent-Text. Im Skill-/Agent-Text werden sensible Werte NICHT eingesetzt, sondern durch einen Platzhalter ersetzt.
- `CLAUDE_PLUGIN_OPTION_<KEY>`: als Umgebungsvariable für Hooks (Großschreibung). Shell-Form-Hooks lesen z. B. `$CLAUDE_PLUGIN_OPTION_API_KEY`.
- Verboten mit `${user_config.*}`: Shell-Form-Hook-`command`, Monitor-`command`, MCP-`headersHelper`. Dort gibt es einen Fehler.

Dialog: erscheint bei Installation in `/plugin`, bei `/plugin install` in der Session und bei Aktivierung im Tab „Installed“. Nachträglich: `/plugin configure <plugin>@<marketplace>`. `claude plugin install` fragt NICHT: Werte per `--config KEY=VALUE` oder `claude plugin configure <plugin> --values-stdin` (JSON per stdin). Mit `--plugin-dir` erscheint der Dialog nicht (Doku-Fehlerbeispiel).

Lokales Beispiel: `code-modernization/.claude-plugin/plugin.json` hat `userConfig` mit `type`, `title`, `description`, `default` und `options`.

Umgebung für Hooks (Quelle: `plugins/components`, Hooks): `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA`, `CLAUDE_PLUGIN_OPTION_<KEY>`, sowie `CLAUDE_PROJECT_DIR`.

---

## 7. Installation und Lebenszyklus

### Befehle in der Session (Quelle: `plugins/install`, `plugins/cli-reference`)

| Befehl | Wirkung |
|---|---|
| `/plugin` | Panel mit Tabs Discover, Installed, Marketplaces, Errors |
| `/plugin install <name>@<marketplace>` | öffnet Details, Scope-Wahl |
| `/plugin install <name> --marketplace <owner/repo>` | fügt Marketplace hinzu und installiert (ab 2.1.275) |
| `/plugin marketplace add <quelle>` / `list` / `update [name]` / `remove <name>` | Marketplace-Verwaltung |
| `/plugin configure <plugin>@<marketplace>` | userConfig-Dialog |
| `/reload-plugins` (`--force`) | lädt Änderungen neu (ohne Neustart) |

### Befehle in der Shell (Quelle: `plugins/cli-reference`, lokal geprüft: `claude plugin --help`)

| Befehl | Wichtige Optionen |
|---|---|
| `claude plugin install <plugin> [--scope user\|project\|local] [--config K=V] [-y] [--json] [--marketplace <src>]` | Standard-Scope `user` |
| `claude plugin uninstall <plugin> [--scope ...] [--keep-data] [--prune] [-y]` | Alias `remove` |
| `claude plugin enable <plugin> [--scope]` / `disable [plugin] [--scope] [-a]` | |
| `claude plugin update <plugin> [--scope ...] [-y]` | |
| `claude plugin list [--json] [--available]` | |
| `claude plugin details <name>` | Komponentenliste und Token-Kosten |
| `claude plugin configure <plugin> [--values-stdin]` | |
| `claude plugin validate <pfad> [--strict] [--json]` | Exit 0 bei Erfolg; `--strict` macht Warnungen zu Fehlern |
| `claude plugin init <name> [--with skills hooks mcp ...] [--description] [--force]` | legt Plugin unter `~/.claude/skills/<name>/` an |
| `claude plugin tag [pfad] [--push] [--dry-run]` | erzeugt `<name>--v<version>` |
| `claude plugin prune` | entfernt nicht mehr benötigte Auto-Abhängigkeiten |
| `claude plugin marketplace add <quelle> [--scope project] [--sparse] [--claudeai]` / `list` / `update` / `remove` | |
| `claude --plugin-dir <pfad>` (wiederholbar) | lädt Ordner oder `.zip` nur für diese Sitzung |
| `claude --plugin-url <zip-url>` | lädt Zip aus URL für eine Sitzung |
| Env `CLAUDE_CODE_PLUGIN_DIRS=/abs/pfad` | wie `--plugin-dir`; Projekt-Settings können sie nicht setzen (ab 2.1.280) |

Exit-Codes (Quelle: `plugins/cli-reference`): 0 Erfolg, 1 Fehler; `validate` zusätzlich 2 bei unerwartetem Fehler.

### Scopes (Quelle: `plugins/install` → „Choose an install scope“; `plugins/loading`)

| Scope | Schreibt in | Wirkung |
|---|---|---|
| `user` | `~/.claude/settings.json` (`enabledPlugins`) | alle Projekte auf dem Rechner |
| `project` | `.claude/settings.json` (committen) | alle, die das Repo klonen; jeder Mitarbeiter muss trotzdem einmal installieren |
| `local` | `.claude/settings.local.json` | nur dieses Repo, nur für dich |
| `managed` | Managed Settings | Admin, nur Update möglich |

Rangfolge bei Konflikt: local überschreibt project, project überschreibt user (Doku-Formulierung in `plugins/install`). Schlüssel: `"<name>@<marketplace>": true|false` in `enabledPlugins`.

### Wo liegt was auf der Platte (Quelle: `plugins/loading` → „Find plugins on disk“; lokal geprüft)

| Pfad (unter `~/.claude/plugins/`) | Inhalt |
|---|---|
| `cache/<marketplace>/<plugin>/<version>/` | kopierte Plugin-Version; Lade-Ziel von `${CLAUDE_PLUGIN_ROOT}` |
| `data/<id>/` | `${CLAUDE_PLUGIN_DATA}` |
| `marketplaces/<name>/` | Klon des Marketplace (GitHub/Git) |
| `installed_plugins.json` | Installationsliste mit Scope, `installPath`, `version`, `gitCommitSha` |
| `known_marketplaces.json` | Marketplace-Quelle und `lastUpdated` |
| `.orphaned_at` im Versionsordner | Marker; Aufräumen nach 14 Tagen |

Lokal geprüft: `installed_plugins.json` enthält `feature-dev@claude-plugins-official` mit Scope `user`, `installPath` in `cache/...`, Version `1.0.1`, `gitCommitSha`. `known_marketplaces.json` nennt `source: github` mit `repo: anthropics/claude-plugins-official`.

Kopierregel (Quelle: `plugins/loading` → „In-place and copied plugins“): Marketplace-Plugins werden in den Cache KOPIERT. Dateien außerhalb des Plugin-Ordners (z. B. `../shared`) fehlen dann. Ausnahmen, die direkt aus dem Quellordner laden: `--plugin-dir`, Skills-Dir-Plugins, relative Pfade in einem Marketplace, der aus einem lokalen Pfad hinzugefügt wurde.

### Updates (Quelle: `plugins/loading` → „Versions and updates“, „When auto-update runs“; `plugins/install` → „Keep plugins updated“)

- Ein Nutzer bekommt eine neue Version nur, wenn sich die berechnete Version ändert.
- Gesetzte `version` in `plugin.json` = Nutzer bleiben darauf, auch bei neuen Commits. Ohne `version` (in beiden Stellen) = Commit-SHA dient als Version (bei github/url/git-subdir).
- Auto-Update: Standard AN für offizielle Marketplaces (`claude-plugins-official` u. a.), AUS für alle anderen. Umschalten: `/plugin` → Marketplaces → „Enable auto-update“, oder `autoUpdate` in `extraKnownMarketplaces`.
- Ablauf: Nach der ersten Nachricht wartet Claude Code bis zu 10 Minuten (zufällig), aktualisiert dann. Die laufende Sitzung behält alte Version; Meldung „Run /reload-plugins to apply“. Hooks/MCP/LSP wechseln nach `/reload-plugins`, Monitore brauchen Neustart.
- Manuell: `claude plugin update <plugin>@<marketplace>`.
- Lokal in-place geladene relative Plugins: jede Session lädt den aktuellen Stand, unabhängig von `version`.

### Entwicklungsschleife (Quelle: `plugins/create`, `plugins/components`, `plugins/troubleshooting`)

1. Ordner anlegen, `plugin.json` schreiben.
2. `claude plugin validate ./omni-agent`.
3. `claude --plugin-dir ./omni-agent` starten; im Test `/omni-agent:<skill>` aufrufen.
4. Änderungen: `/reload-plugins`. Kontrolle: `/plugin` → Errors, `claude plugin list`, `/mcp`, `claude --debug` für Hooks.

### Abhängigkeiten (Quelle: `plugins/dependencies`, `plugins/loading` → „Node.js package dependencies“)

- `dependencies` in `plugin.json` (siehe Abschnitt 3). Abhängigkeiten werden mit installiert und aktiviert.
- Fremder Marketplace: nur wenn der Root-Marketplace in `allowCrossMarketplaceDependenciesOn` steht.
- Versionsbereiche (`"~2.1.0"`, `"^2.0"`) werden gegen Git-Tags `<plugin>--v<version>` aufgelöst.
- Node-Abhängigkeiten: Claude Code installiert sie automatisch in den Cache, wenn `package.json` UND ein Lockfile vorhanden sind (`bun.lock`, `npm-shrinkwrap.json` oder `package-lock.json`, npm-lockfileVersion 2 oder 3). Regeln: nur Registry-Pakete mit exakter Version; keine Lifecycle-Skripte (`--ignore-scripts`); keine `overrides`/`patchedDependencies`; Timeout 60 s. Abschaltbar ist das nicht. Yarn-/pnpm-Lockfile = übersprungen.
- Alternative laut Doku: SessionStart-Hook installiert nach `${CLAUDE_PLUGIN_DATA}` (Beispiel in `plugins/components`). Gilt auch für Python, Git-Abhängigkeiten, Yarn/pnpm.

---

## 8. Verteilung

### Eigener öffentlicher GitHub-Marketplace im selben Repo (Quelle: `plugins/publish` → „Publish through your own marketplace“, `plugins/host-marketplace`, `plugins/install`)

- Repo-Layout: `.claude-plugin/plugin.json` und `.claude-plugin/marketplace.json` (Eintrag `"source": "./"`). Ein Repo kann beides sein.
- Wer ein öffentliches Repo hat, kann ohne Einreichung installieren lassen. Die Doku verlangt keine Freigabe.
- Nutzer-Befehle (Doku-Muster, Platzhalter ersetzen):
  - `/plugin marketplace add <user>/omni-agent` (oder `claude plugin marketplace add <user>/omni-agent`)
  - `/plugin install omni-agent@<marketplace-name>`. Den Marketplace-Namen liest Claude Code aus `marketplace.json`, NICHT aus dem Repo-Namen. Wenn beide `omni-agent` heißen: `omni-agent@omni-agent`.
  - Oder in einem Schritt: `/plugin install omni-agent --marketplace <user>/omni-agent` (ab 2.1.275).
  - Pin auf Branch/Tag: `<user>/omni-agent#v0.1.0`.
- Die Bitte „Repo-URL dem Claude geben“: Die Doku beschreibt Installation durch den Nutzer per Befehl. Ob Claude aus einer bloßen URL selbständig installiert, ist nicht belegt.
- Versionierung: Entweder `version` in `plugin.json` pflegen und bei jedem Release erhöhen, oder weglassen (dann zählt der Commit-SHA). Doku: „Don't set version in both“.
- Release-Tag: `claude plugin tag --push` erzeugt `omni-agent--v<version>` (nur nötig, wenn andere Plugins Versionsbereiche darauf setzen).

### Team-Setup (Quelle: `plugins/loading` → „Plugins shared through a repository“; `plugins/install`)

- In `.claude/settings.json` (committen): `extraKnownMarketplaces` (Quelle des Marketplace) und `enabledPlugins` (`"omni-agent@omni-agent": true`).
- Achtung: Ein Plugin mit externer Quelle wird NICHT automatisch bei Kollegen installiert, wenn nur das Projekt es aktiviert. Dann meldet `/plugin` „enabled in project settings but isn't installed“. Lösung laut Doku: jeder Kollege führt `claude plugin install omni-agent@omni-agent --scope project` aus. Ausnahme: relative Pfad-Quellen oder Seed-Verzeichnisse.
- Cloud-Sessions (claude.ai/code) laden lokal installierte Plugins NICHT (`plugins/install`).

### Private Repos (Quelle: `plugins/host-marketplace` → „Grant access to a private marketplace“)

- Kein Token-Feld in `marketplace.json`. Claude Code nutzt die git-Zugangsdaten des Rechners, ohne Rückfrage.
- SSH: Schlüssel ohne Passphrase-Abfrage (ssh-agent), Host in `known_hosts`.
- HTTPS: Credential-Helper speichert Zugang (`gh auth login` + `gh auth setup-git`).
- Bei `owner/repo`-Kurzform prüft Claude Code SSH zuerst. Mit `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1` wird immer HTTPS genutzt.

### Anthropic-Verzeichnis (Quelle: `plugins/publish` → „Submit to Anthropic's directory“)

- Einreichung über `claude.ai/directory/manage`. Voraussetzung laut Doku: bezahlter claude.ai-Plan (Pro/Max eigener Account; Team/Enterprise: Owner).
- Der offizielle Marketplace `claude-plugins-official` nimmt keine Einreichungen über das Portal; dafür Anthropic-Partnerkontakt.
- Nach Freigabe: Nutzer mit claude.ai-Account bekommen das Plugin, Claude Code lädt es als `<name>@synced`.
- Prüfung/Fristen: nicht belegt (Verweis auf claude.com-Seiten, nicht gelesen).

### Namensregeln (Quelle: `plugins/manifest-reference` → `name`; `plugins/marketplace-reference` → Reserved names)

- Plugin-Name darf nicht beginnen mit `claude-`, `anthropic-`, `anthropics-`, `cc-plugin-` (Fehler). Auch nicht `claude`, `anthropic`, `claude-code`, `claude-mods`. `omni-agent` ist zulässig.
- Reservierte Marketplace-Namen u. a.: `inline`, `builtin`, `skills-dir`, `synced`, `npm`, `pip`, `uv`, `cargo`, `github`, `gh`, `claude-plugin-test`, und alle offiziellen Anthropic-Namen.

---

## 9. Sicherheit (Quelle: `plugins/security`, `hooks`, `plugins/org`)

- Ein Plugin führt Code mit den Rechten des Nutzers aus (Doku-Wortlaut sinngemäß). Hooks, Monitore, MCP-Server, LSP-Server und Mod-Prozesse laufen AUSSERHALB der Sandbox.
- Befehle aus `bin/`, die Claude über das Bash-Tool startet, sind Tool-Aufrufe und unterliegen den Berechtigungsregeln.
- Skills/Agents/Commands wirken als Anweisungen an Claude (Prompt-Ebene), nicht als Code.
- Vertrauenswarnung bei Installation (Wortlaut): „Make sure you trust a plugin before installing, updating, or using it. Anthropic does not control what MCP servers, files, or other software are included in plugins...“. Organisationen können `pluginTrustMessage` anhängen.
- Prüfen vor Installation: `/plugin` → Details → „Will install“. Sonst Dateien lesen: `hooks/hooks.json`, `.mcp.json`, `bin/`. Dazu `claude --plugin-dir <ordner> plugin details <name>`.
- Auto-Update kann die geprüften Dateien ändern (Doku-Warnung in `plugins/security`).
- Projekt-Plugins aus dem Repo: laden erst nach Vertrauensprüfung des Ordners; MCP-Server brauchen Einzelfreigabe; Hintergrund-Monitore laden nicht; MCP-Bundles aus dem Repo werden übersprungen.
- Admin-Steuerung (Managed Settings): `strictKnownMarketplaces`, `blockedMarketplaces`, `allowManagedHooksOnly`, `disableCommandPluginSources`, `strictPluginOnlyCustomization`, Abschalten von `--plugin-dir`/`CLAUDE_CODE_PLUGIN_DIRS`, `syncClaudeAiPlugins`.
- Hooks (Quelle: `hooks`): Exit 2 blockiert, Stderr wird als Grund gezeigt. Andere Fehlercodes lassen die Aktion durchlaufen. Standard „fail-open“; `"onFailure": "block"` (ab 2.1.295) ändert das. `if`-Filter ist „best-effort“. Für harte Regeln Berechtigungen nutzen.
- Secrets: Sensible Werte per `userConfig` mit `sensitive: true`. Nie im Klartext in `.mcp.json` oder Skripten. Für `headersHelper` entfernt Claude Code credential-artige Umgebungsvariablen (Quelle: `plugins/host-marketplace`).
- Deinstallation aus letztem Scope löscht gespeicherte Optionen, Secrets und Datenordner (Quelle: `plugins/cli-reference`, Ausnahme `--keep-data`).

---

## 10. Fallen und Grenzen

| # | Falle | Quelle / Status |
|---|---|---|
| 1 | Komponenten in `.claude-plugin/` laden nicht (nur `plugin.json` gehört dort hinein) | `plugins/create` |
| 2 | Pfade ohne `./` werden abgelehnt; `..` verboten; Backslash auf macOS/Linux verboten | `plugins/manifest-reference` |
| 3 | `CLAUDE.md` im Plugin-Root wird nicht geladen. Anweisungen als Skill | `plugins/components` |
| 4 | Marketplace-Plugins werden kopiert. Dateien außerhalb des Plugin-Ordners fehlen im Cache | `plugins/loading` |
| 5 | `version` gesetzt + neue Commits ohne Bump = Nutzer bekommen nichts | `plugins/loading` |
| 6 | Plugin-Name und Eintrags-Name unterschiedlich = „Plugin not found“ | `plugins/marketplace-reference` |
| 7 | Hooks in einer Marketplace-`plugins[]`-Eintrag als Dateipfad: laufen nie; nur Inline-Objekt | `plugins/marketplace-reference` |
| 8 | `settings.json` im Plugin: nur `agent` und `subagentStatusLine` | `plugins/components` |
| 9 | `hooks`/`mcpServers`/`permissionMode` in Agent-Frontmatter werden ignoriert | `plugins/components` |
| 10 | `${CLAUDE_PLUGIN_ROOT}` in Shell-Form-Hooks: in Anführungszeichen setzen; sonst warnt `validate` | `plugins/manifest-reference` |
| 11 | `${CLAUDE_PLUGIN_ROOT}` ist NICHT in der Umgebung von Bash-Tool-Befehlen. `bin/`-Skripte: Pfad aus `$0` ableiten (eigene Empfehlung) | `plugins/manifest-reference` |
| 12 | Sensible `userConfig`-Werte erscheinen in Skill-/Agent-Text NICHT (Platzhalter). Sie müssen in MCP-`env` oder Hook-`args` | `plugins/manifest-reference` |
| 13 | Shell-Form-Hook, Monitor und `headersHelper` akzeptieren kein `${user_config.*}` | `plugins/manifest-reference` |
| 14 | Monitore starten nicht mit `-p`; kein `${user_config.*}`; laufen nach Deaktivierung weiter bis Sitzungsende | `plugins/components` |
| 15 | Node-Abhängigkeiten nur mit Lockfile (npm/bun); Yarn/pnpm-Lockfile = keine Installation; kein Lifecycle-Skript; 60 s | `plugins/loading` |
| 16 | Bei `--plugin-dir` erscheint der userConfig-Dialog nicht; `/plugin configure` nutzen | `plugins/components` |
| 17 | `claude plugin install` fragt keine userConfig-Werte ab (`--config` oder `configure --values-stdin`) | `plugins/components` |
| 18 | Hooks laufen ab Session-Start, nicht erst bei Skill-Aufruf; Matcher eng setzen | `plugins/components` |
| 19 | Hooks mit gleichem Plugin-Namen aus zwei Marketplaces: einer wird nicht ausgeführt | `plugins/loading` |
| 20 | `validate --strict` scheitert an fehlender `version`/`description`/`author` | `plugins/manifest-reference` |
| 21 | Windows: Shell-Form-Hooks laufen über Git Bash, sonst PowerShell. Exec-Form braucht echte `.exe`; `.cmd`-Shims über `node <script>` aufrufen | `hooks`, `plugins/manifest-reference` |
| 22 | Windows: `${CLAUDE_PLUGIN_ROOT}` mit Schrägstrichen (`C:/...`) in Git-Bash-Hooks | `plugins/troubleshooting` |
| 23 | Ausführungsrecht für `bin/`: Doku-Beispiel nutzt `chmod +x`; Pflicht nicht ausdrücklich belegt. Die Plugins im lokalen Marketplace haben teils Modus 644 (z. B. `code-modernization/scripts/telemetry.sh`), laufen aber über `sh …`. Sicher: Skripte mit `sh "${CLAUDE_PLUGIN_ROOT}/…"` aufrufen oder `chmod +x` setzen | lokal geprüft |
| 24 | Änderungen an Hooks/MCP nach Update: alter Pfad bis `/reload-plugins`; Monitore nur mit Neustart | `plugins/loading` |
| 25 | Cloud-Sessions laden lokal installierte Plugins nicht | `plugins/install` |
| 26 | Pfade außerhalb des Plugin-Ordners (z. B. `../shared`) fehlen nach dem Kopieren in den Cache | `plugins/loading` |
| 27 | Abhängigkeit von `@synced`-Plugins nur per claude.ai erfüllt, wenn das Plugin auch dort geladen wird | `plugins/dependencies` |
| 28 | Dateien mit Git LFS werden bei Klon nicht geladen (Pointer-Dateien) | `plugins/host-marketplace` |
| 29 | Private Marketplaces: Auto-Update im Hintergrund klappt nur mit gespeicherten Zugangsdaten | `plugins/host-marketplace` |

Grenzen (nicht Fähigkeiten von Plugins): Kein Plugin-Pendant zu Managed Agents; Hintergrund-Prozesse kommen über MCP-Server, Monitore, `bin/`-Befehle oder Subagents mit `background`-Feld. Ob das für Hintergrund-Agents mit Fremdmodellen reicht, ist eine Designfrage, die die Doku nicht beantwortet (nicht belegt).

---

## 11. Minimal lauffähige Beispiele

### 11.1 plugin.json (mit userConfig und Secret)
```json
{
  "name": "omni-agent",
  "version": "0.1.0",
  "description": "Startet Hintergrund-Agents mit Fremdmodellen",
  "author": { "name": "Alex" },
  "repository": "https://github.com/<user>/omni-agent",
  "license": "MIT",
  "userConfig": {
    "eurouter_api_key": {
      "type": "string",
      "title": "EUrouter API-Key",
      "description": "Schlüssel für das Modell-Gateway",
      "sensitive": true,
      "required": true
    },
    "default_model": {
      "type": "string",
      "title": "Standardmodell",
      "description": "Modell für neue Agents",
      "default": "auto"
    }
  }
}
```

### 11.2 marketplace.json (Repo ist zugleich Marketplace)
```json
{
  "name": "omni-agent",
  "owner": { "name": "Alex", "url": "https://github.com/<user>" },
  "description": "Marketplace für das Omni-Agent-Plugin",
  "plugins": [
    {
      "name": "omni-agent",
      "source": "./",
      "description": "Hintergrund-Agents mit Fremdmodellen"
    }
  ]
}
```
Ablage: `.claude-plugin/marketplace.json`. Nutzer: `/plugin marketplace add <user>/omni-agent`, dann `/plugin install omni-agent@omni-agent`.

### 11.3 Slash-Command mit Argumenten (Skill)
`skills/agent-start/SKILL.md`:
```markdown
---
description: Startet einen Hintergrund-Agent mit einem Fremdmodell
argument-hint: "[aufgabe]"
disable-model-invocation: true
allowed-tools: Bash(omni-agent *)
---
Starte einen Hintergrund-Agent für die Aufgabe: $ARGUMENTS

Führe `omni-agent start "$ARGUMENTS"` aus und melde danach die Job-ID.
```
Aufruf: `/omni-agent:agent-start Recherche zu Tarifen`. `$ARGUMENTS` ist der Rest der Eingabe; `$0` wäre das erste Wort.

### 11.4 Skill (automatisch geladen)
`skills/modellwahl/SKILL.md`:
```markdown
---
description: Wählt für eine Hintergrundaufgabe das Fremdmodell. Nutzen, wenn der Nutzer ein Modell für einen Agent nennt oder eine Kosten-/Qualitätsfrage zu Modellen stellt.
---
Lies die Modellliste über `omni-agent models` und wähle das günstigste Modell, das die Aufgabe nach Nutzerangabe erfüllt. Nenne Modell und Begründung in einem Satz.
```
Ohne `disable-model-invocation` darf Claude die Skill selbst laden.

### 11.5 Hook (Exec-Form, mit Pfadvariable)
`hooks/hooks.json`:
```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "node",
            "args": ["${CLAUDE_PLUGIN_ROOT}/scripts/check-env.js"],
            "timeout": 10
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "sh",
            "args": ["${CLAUDE_PLUGIN_ROOT}/scripts/after-bash.sh"],
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```
Exit 2 im Skript blockiert, Stderr ist der Grund. Exec-Form (mit `args`) braucht keine Anführungszeichen.

### 11.6 bin/-Befehl (Pfad aus $0, da ROOT-Variable im Bash-Tool fehlt)
`bin/omni-agent` (`chmod +x`, oder Aufruf über `sh` in Skripten):
```bash
#!/bin/sh
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
case "${1:-}" in
  start) shift; exec node "$ROOT/dist/cli.js" start "$@" ;;
  status) exec node "$ROOT/dist/cli.js" status ;;
  *) echo "Aufruf: omni-agent start|status ..." >&2; exit 2 ;;
esac
```

### 11.7 MCP-Server mit Secret aus userConfig
`.mcp.json`:
```json
{
  "mcpServers": {
    "omni-agent": {
      "command": "node",
      "args": ["${CLAUDE_PLUGIN_ROOT}/mcp/server.js"],
      "env": {
        "EUROUTER_API_KEY": "${user_config.eurouter_api_key}",
        "OMNIAGENT_DATA": "${CLAUDE_PLUGIN_DATA}"
      }
    }
  }
}
```
Tools heißen `mcp__plugin_omni-agent_omni-agent__<tool>`. Server in `/mcp` als `plugin:omni-agent:omni-agent`.

---

## 12. Konsequenzen für Omni-Agent (aus der Doku abgeleitet)

1. Repo mit `.claude-plugin/plugin.json` (name `omni-agent`) und `.claude-plugin/marketplace.json` (source `./`) im Root.
2. API-Schlüssel nur über `userConfig` mit `sensitive: true`, und nur in MCP-`env` oder Hook-`args` einsetzen. Nicht in Skill-Text.
3. Hintergrund-Agents als MCP-Server oder als `bin/`-Befehl mit eigenem Datenordner in `${CLAUDE_PLUGIN_DATA}` (Zustand, Logs, Job-Liste). Nicht in `${CLAUDE_PLUGIN_ROOT}` schreiben.
4. Version bewusst pflegen. Ohne `version` folgen Nutzer dem Commit.
5. Installationsweg für Nutzer: `/plugin marketplace add <user>/omni-agent`, dann `/plugin install omni-agent@omni-agent`. Kurzform mit `--marketplace`.
6. Vor Veröffentlichung: `claude plugin validate --strict ./`, dann lokal mit `claude --plugin-dir ./` testen.

---

## 13. Nicht belegt (in der Doku nicht gefunden oder nicht vollständig gelesen)

- Ob `sensitive` userConfig-Werte auf macOS im Schlüsselbund liegen. Doku sagt nur „platform's secure credential store“.
- Ob Claude aus einer bloßen Repo-URL im Chat selbständig installiert.
- Ob `bin/`-Dateien zwingend `chmod +x` brauchen (Doku-Beispiel nutzt es, Pflicht nicht formuliert).
- Vollständige Frontmatter- und Hook-Felder (Hooks: Doku nur bis Abschnitt „Exit codes“ und Sicherheit gelesen; Seite ist sehr lang; einzelne Event-Eingaben ungeprüft).
- Workflow-Format (`workflows/*.js`) und Channels: nur Erwähnung, keine Details.
- Prüf- und Freigabefristen des Anthropic-Verzeichnisses.
- Ob Hintergrund-Agents mit Fremdmodellen über Plugin-Mechanik dauerhaft laufen dürfen (keine Doku-Aussage; Monitore und `background` sind nur Teilantworten).
- Ob `/plugin marketplace add` mit reinem Repo-Namen ohne Owner funktioniert (Doku nennt nur `owner/repo`).
- Windows-Verhalten für `bin/` im Bash-Tool: nur Hinweis auf PowerShell-Tool; keine Aussage zu Exec-Rechten.
