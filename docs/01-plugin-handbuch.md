# Claude-Code-Plugins: das Handbuch (auf Omni-Agent angewendet)

Stand: 28.10.2026, Claude Code 2.1.304. Alles hier stammt aus der offiziellen Doku (`code.claude.com/docs`)
oder aus einem lokal geprüften Plugin. Wo etwas nicht belegt ist, steht es ausdrücklich da. Die Rohfassung
mit Doku-Seiten je Aussage: [`recherche/plugin-doku-auszug.md`](recherche/plugin-doku-auszug.md).

## 0. Das Wichtigste in neun Zeilen

1. Ein **Plugin** ist ein Ordner. Mehr nicht. Claude Code lädt daraus Skills, Hooks, MCP-Server und Befehle.
2. Ein **Marketplace** ist eine Liste (`marketplace.json`), die sagt: „Diese Plugins gibt es, hier liegen sie.“
3. Ein öffentliches GitHub-Repo kann **beides zugleich** sein. Eine Anmeldung bei Anthropic ist nicht nötig.
4. Slash-Befehle sind **Skills**: `skills/run/SKILL.md` im Plugin `omni-agent` wird zu `/omni-agent:run`.
5. Skills sind **Text für Claude**, kein Code. Code liegt in `bin/`, in Hooks oder in MCP-Servern.
6. API-Schlüssel gehören in `userConfig` mit `sensitive: true`. **Aber:** Dieser Weg erreicht `bin/`-Skripte nicht (Abschnitt 7).
7. Das Plugin wird beim Installieren in einen **Cache kopiert**. Alles, was es braucht, muss im Ordner liegen.
8. Entwickeln: `claude plugin validate`, `claude --plugin-dir ./`, `/reload-plugins`.
9. Installieren für andere: `/plugin marketplace add <account>/omni-agent`, dann `/plugin install omni-agent@omni-agent`.

---

## 1. Das Bild im Kopf

| Begriff | Bild | Datei |
|---|---|---|
| Plugin | Ein Koffer mit Werkzeug | Ordner mit `.claude-plugin/plugin.json` |
| Marketplace | Ein Katalog, der Koffer aufzählt | `.claude-plugin/marketplace.json` |
| Installieren | Der Koffer wird kopiert nach `~/.claude/plugins/cache/…` | durch Claude Code |
| Aktivieren | Der Koffer wird in `settings.json` auf „an“ gesetzt | `enabledPlugins` |

Ohne Plugin müsste jeder Nutzer Dateien von Hand in `~/.claude/skills/`, `~/.claude/settings.json` usw. kopieren.
Das Plugin macht daraus **einen** Befehl, einen Namensraum, eine Versionsnummer und ein sauberes Deinstallieren.

Abgrenzung: Der lokale Skill `plugin-authoring` („Mods“) baut UI-Panels im Claude-Fenster. Das ist eine Sonderform
(ein Plugin mit JavaScript im Claude-Prozess). Für Omni-Agent ist das **nicht** gemeint.

---

## 2. Alle Bausteine, was sie tun und ob Omni-Agent sie braucht

| Baustein | Ort im Plugin | Was es ist | Omni-Agent |
|---|---|---|---|
| **Skills** | `skills/<name>/SKILL.md` | Anweisung, die Claude bei passender Beschreibung lädt, oder die du als `/plugin:name` aufrufst | **ja**, das sind unsere Slash-Befehle |
| Commands (alt) | `commands/*.md` | Dasselbe wie Skill, nur eine Datei. Für Neues Skills nehmen | nein |
| **Agents** | `agents/*.md` | Eigener Assistent mit eigenem Kontext und Systemprompt | vielleicht später (Gutachter-Agent) |
| **Hooks** | `hooks/hooks.json` | Befehl bei Ereignis (Sitzung startet, Tool lief, Antwort fertig …) | optional (Selbsttest beim Start) |
| **MCP-Server** | `.mcp.json` | Eigener Prozess, der Claude **Tools** gibt | **nicht jetzt**, Begründung in Abschnitt 8 |
| LSP-Server | `.lsp.json` | Code-Navigation für eine Sprache | nein |
| Output-Styles | `output-styles/*.md` | Antwortstil, wählbar mit `/output-style` | nein |
| Themes | `themes/*.json` (experimentell) | Farbschema | nein |
| Monitors | `monitors/monitors.json` (experimentell) | Hintergrundbefehl, dessen Ausgabe als Meldung bei Claude ankommt. Startet **nicht** mit `-p` | später für „Lauf fertig“ denkbar |
| **bin/** | `bin/<datei>` | Dateien kommen in den **PATH des Bash-Tools**, solange das Plugin aktiv ist | **ja**, hier liegt der Kern `omni-agent` |
| settings.json | Plugin-Root | Wirkt nur mit zwei Schlüsseln: `agent`, `subagentStatusLine` | nein |
| Workflows | `workflows/*.js` | Skripte, die mehrere Subagents steuern (Doku-Details nicht gelesen) | nein |
| Channels | Manifest `channels` | Nachrichten von außen in eine Sitzung | nein |
| CLAUDE.md im Root | – | **Wird nicht geladen.** Anweisungen gehören in einen Skill | nein |

Regel dahinter: **Skill = Text für Claude. Hook, MCP, bin = Code, der mit deinen Rechten läuft.**

---

## 3. Ordnerlayout

Nur `plugin.json` und `marketplace.json` gehören in `.claude-plugin/`. Alles andere liegt im Root daneben.
Der häufigste Anfängerfehler ist, `skills/` in `.claude-plugin/` zu legen: dann lädt nichts.

So sieht Omni-Agent aus:

```text
omni-agent/
├── .claude-plugin/
│   ├── plugin.json              Name, Beschreibung, userConfig
│   └── marketplace.json         Katalog mit einem Eintrag, source "./"
├── skills/
│   ├── run/SKILL.md             /omni-agent:run     Auftrag starten
│   ├── setup/SKILL.md           /omni-agent:setup   Einrichtung führen
│   ├── doctor/SKILL.md          /omni-agent:doctor  prüfen, was fehlt
│   ├── status/SKILL.md          /omni-agent:status  Läufe und Berichte
│   └── delegieren/SKILL.md      Claude entscheidet selbst, wann ein Fremdagent passt
├── bin/
│   └── omni-agent                Der Kern (ausführbar), ruft lib/ auf
├── lib/                         Runner-Adapter, Anbieter-Logik (Python)
├── providers.json               Anbieter als Daten
├── hooks/hooks.json             optional
├── INSTALL.md                   für Claude geschrieben („installiere mir das“)
├── AGENTS.md                    dasselbe für Codex und andere Orchestratoren
├── README.md   LICENSE   .gitignore
└── docs/
```

---

## 4. Die zwei Manifeste

### plugin.json

Einziges Pflichtfeld ist `name`. Die wichtigsten Felder:

| Feld | Hinweis |
|---|---|
| `name` | kebab-case. Wird zum Namensraum aller Befehle. **Darf nicht mit `claude-`, `anthropic-`, `cc-plugin-` beginnen.** `omni-agent` ist erlaubt |
| `version` | Gesetzt = Nutzer bleiben darauf, bis du sie erhöhst. **Weggelassen = jeder neue Commit ist ein Update** |
| `description`, `author`, `license`, `repository`, `homepage`, `keywords` | Anzeige und Suche. `homepage` muss eine echte URL sein, sonst lädt das Plugin nicht |
| `userConfig` | Eingaben, nach denen beim Aktivieren gefragt wird (Abschnitt 7) |
| `dependencies` | andere Plugins, die mitinstalliert werden |
| `skills`, `hooks`, `mcpServers` | **zusätzliche** Pfade zum Standardordner |
| `commands`, `agents`, `outputStyles` | **ersetzen** den Standardordner |

Pfade im Manifest beginnen mit `./`, bleiben im Plugin-Ordner, enthalten kein `..`.

### marketplace.json

| Feld | Hinweis |
|---|---|
| `name` | Das tippen Nutzer nach dem `@`: `omni-agent@omni-agent`. Kommt aus dieser Datei, **nicht** vom Repo-Namen |
| `owner` | Pflicht, `{ "name": … }` |
| `plugins[]` | je Eintrag `name` und `source` |
| `renames` | alter Name → neuer Name. **Nützlich, falls wir von `fremdagent` umbenennen** |

`source`-Varianten: relativer Pfad `"./"` (Plugin liegt im selben Repo), `github`, `url`, `git-subdir`, `npm`, `archive`.
Für Omni-Agent genügt `"./"`.

Unsere zwei Dateien stehen fertig im Abschnitt 11 dieser Datei.

---

## 5. Skills, also Slash-Befehle

**Namensraum:** `skills/run/SKILL.md` im Plugin `omni-agent` ergibt `/omni-agent:run`. Der Plugin-Name steht immer davor,
damit sich zwei Plugins nicht in die Quere kommen. Agents heißen entsprechend `omni-agent:name`.

**Aufbau einer Skill:** Frontmatter (Einstellungen) und darunter Text, den Claude liest.

```markdown
---
description: Startet einen Hintergrund-Agent mit einem Fremdmodell
argument-hint: "[anbieter] [auftragsdatei]"
disable-model-invocation: true
allowed-tools: Bash(omni-agent *)
---
Starte mit `omni-agent run $ARGUMENTS` im Hintergrund …
```

| Frontmatter | Bedeutung |
|---|---|
| `description` | **Entscheidend.** Daran erkennt Claude, wann die Skill passt |
| `argument-hint` | Hinweis beim Tippen |
| `disable-model-invocation: true` | Nur du kannst sie aufrufen, Claude nie von selbst. Gut für Befehle mit Wirkung |
| `user-invocable: false` | Nur Claude kann sie laden, nicht im `/`-Menü. Gut für Hintergrundwissen |
| `allowed-tools` | Diese Tools laufen **ohne Rückfrage**, solange die Skill aktiv ist. Sie **schränkt nichts ein** |
| `disallowed-tools` | nimmt Tools weg |
| `context: fork` | Läuft in eigenem Subagent ohne Gesprächsverlauf |
| `model`, `effort` | nur für diesen Zug |
| `paths` | automatisch bei passenden Dateien |

**Textbausteine im Skill:** `$ARGUMENTS` (alles hinter dem Befehl), `$0` (erstes Wort), `${CLAUDE_PLUGIN_ROOT}`,
`${CLAUDE_PLUGIN_DATA}`, `${CLAUDE_SKILL_DIR}`. `` !`befehl` `` läuft **vor** dem Senden; scheitert er, bricht der Aufruf ab.

**Zwei Arten für Omni-Agent:**
- *Befehl* (`run`, `setup`, `doctor`, `status`): `disable-model-invocation: true`, du löst sie bewusst aus.
- *Wissen* (`delegieren`): ohne dieses Flag, damit Claude von selbst auf Omni-Agent kommt, wenn du sagst
  „lass das DeepSeek recherchieren“.

---

## 6. Pfade und Variablen

| Variable | Zeigt auf | Wofür |
|---|---|---|
| `${CLAUDE_PLUGIN_ROOT}` | `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` | Skripte, die mitgeliefert werden. **Ändert sich bei jedem Update, nie hineinschreiben** |
| `${CLAUDE_PLUGIN_DATA}` | `~/.claude/plugins/data/<id>/` | Dinge, die ein Update überleben. **Wird beim Deinstallieren gelöscht** |
| `${CLAUDE_PROJECT_DIR}` | Projektordner | projektlokales |

**Die zwei Fallen dabei:**

1. **Cache-Kopie.** Marketplace-Plugins werden kopiert. Eine Datei außerhalb des Plugin-Ordners (`../shared`) fehlt im Cache.
   Omni-Agent liegt deshalb komplett in einem Ordner.
2. **Die Variablen gibt es nicht in der Umgebung von Befehlen, die Claude über das Bash-Tool startet.** Ein Skript in `bin/`
   kann `$CLAUDE_PLUGIN_ROOT` also nicht lesen. Lösung (eigene Schlussfolgerung, nicht Doku): Der Kern findet seinen Ort aus
   dem eigenen Dateipfad. Persistente Läufe und Schlüssel legen wir **nicht** in `PLUGIN_DATA`, sondern in `~/.omni-agent/`
   (Gründe: Abschnitt 7 und `02-architektur.md`).

Die Variablen werden aufgelöst in: Hook-Befehlen, MCP-Konfiguration, LSP-Konfiguration und im Text von Skills und Agents.

---

## 7. Geheimnisse: `userConfig`, und warum es für Omni-Agent nicht reicht

`userConfig` sind Fragen, die Claude Code beim Aktivieren des Plugins stellt.

| Feld | Hinweis |
|---|---|
| `type` | `string`, `number`, `boolean`, `directory`, `file` |
| `title`, `description` | Pflicht, Text im Dialog |
| `required`, `default`, `options`, `multiple`, `min`, `max` | wie erwartet |
| **`sensitive: true`** | Eingabe maskiert, Speicherung im „sicheren Speicher der Plattform“ statt in `settings.json` |

Ob dieser sichere Speicher auf dem Mac der Schlüsselbund ist, steht in der Doku **nicht** (nicht belegt).

**Wo kommt der Wert an?**

| Ziel | Funktioniert |
|---|---|
| MCP-Server (`env`, `args`, `url`, `headers`) via `${user_config.KEY}` | ja |
| Hook im Exec-Format (`args`) via `${user_config.KEY}` | ja |
| Hook-Umgebung als `CLAUDE_PLUGIN_OPTION_<KEY>` | ja |
| Text in Skills und Agents | nur nicht-geheime Werte. **Geheime werden durch einen Platzhalter ersetzt** |
| Shell-Hook, Monitor, `headersHelper` | nein, Fehler |
| **`bin/`-Skript, das Claude per Bash startet** | **nein, kommt dort nicht an** |

**Folge für Omni-Agent:** Der Kern ist ein `bin/`-Befehl. Er sieht `userConfig`-Geheimnisse nicht. Es gibt drei Wege:

| Weg | Wie | Urteil |
|---|---|---|
| A | Kern liest Schlüssel aus der **Umgebung** (`DEEPSEEK_API_KEY`) und rückfallend aus `~/.omni-agent/env` (Rechte 600) | **gewählt:** funktioniert in jeder Umgebung, ohne Plugin, auch unter Codex |
| B | Kern als **MCP-Server**, Schlüssel per `${user_config.*}` | sauber und plugin-nativ, aber setzt Node oder Python-Laufzeit im MCP voraus und verlagert alles in Tools. Später als Komfortstufe |
| C | Hook schreibt `userConfig` in eine Datei | verwirft den Vorteil des sicheren Speichers, nein |

Eingabe ohne Chat: `/omni-agent:setup` führt dich, legt die Datei `~/.omni-agent/env` mit leeren Zeilen an und öffnet sie.
Du trägst den Schlüssel selbst dort ein. Er geht **nie durch den Chat**.

---

## 8. Hooks, MCP, bin, Monitor: was wann

| Mechanismus | Läuft | Gut für | Omni-Agent |
|---|---|---|---|
| Skill | als Text in Claudes Kopf | Anleitung, Ablauf | Befehle und Wissen |
| **bin/** | wenn Claude (oder du) per Bash ruft | ein echtes Programm, das du auch ohne Claude brauchst | **der Kern** |
| Hook | bei Ereignissen, automatisch | Prüfen, Blockieren (Exit 2), Protokollieren | optional: Selbsttest bei `SessionStart` |
| MCP-Server | dauerhaft im Hintergrund | Tools mit Zustand, Schlüssel aus `userConfig` | nicht jetzt |
| Monitor | dauerhaft, meldet an Claude | „Lauf fertig“-Meldung | nicht jetzt, wird bei `-p` nicht gestartet |

**Warum bin/ statt MCP für „Hintergrund-Agents“ ausreicht:** Die Doku sagt nichts darüber, ob Plugins Hintergrund-Agents
dauerhaft betreiben dürfen. Sie müssen es nicht. Claude Codes **Bash-Tool kann Befehle im Hintergrund starten** und
Claude wird geweckt, wenn der Befehl endet. `omni-agent run` ist ein normaler, blockierender Befehl. Claude startet ihn im
Hintergrund. Kein Daemon, keine Warteschlange, kein eigener Prozess. Das ist auch der Weg, der heute im Wrapper funktioniert.

Hooks laufen **ab Sitzungsbeginn**, nicht erst beim Skill-Aufruf. Der Matcher gehört eng gefasst. Exit 2 blockiert, andere
Fehlercodes lassen die Aktion durch (fail-open).

---

## 9. Installation, Scopes, Updates

**Für Nutzer in Claude Code:**

```text
/plugin marketplace add <account>/omni-agent
/plugin install omni-agent@omni-agent
```
oder in einem Schritt: `/plugin install omni-agent --marketplace <account>/omni-agent` (ab 2.1.275).
Auf einen Stand festlegen: `<account>/omni-agent#v0.1.0`.

**In der Shell:** `claude plugin install | uninstall | enable | disable | update | list | details | validate | tag`.

| Scope | Schreibt in | Wirkung |
|---|---|---|
| `user` (Standard) | `~/.claude/settings.json` | alle Projekte auf dem Rechner |
| `project` | `.claude/settings.json` | alle, die das Repo klonen (müssen trotzdem einmal installieren) |
| `local` | `.claude/settings.local.json` | nur du, nur dieses Repo |

**Wo liegt was:** `~/.claude/plugins/cache/…` (Kopie), `…/data/…` (dauerhafte Daten), `…/marketplaces/…` (Klon des Katalogs),
`installed_plugins.json`, `known_marketplaces.json`.

**Updates:**
- Die Version ist `version` aus `plugin.json`. Fehlt sie, zählt der Commit-SHA.
- **Ist `version` gesetzt und du pushst ohne Erhöhung, bekommt niemand etwas.** Das ist die häufigste Update-Falle.
- Auto-Update ist für fremde Marketplaces **standardmäßig aus**; Nutzer schalten es unter `/plugin` → Marketplaces ein
  oder aktualisieren mit `claude plugin update`.
- Laufende Sitzungen merken es erst nach `/reload-plugins`.

**Empfehlung für Omni-Agent:** In der Entwicklung `version` **weglassen** (jeder Push = Update, gut für den Unterricht).
Zum Release `version` setzen und Tags mit `claude plugin tag --push`.

---

## 10. Entwickeln und testen

```bash
claude plugin validate --strict ./omni-agent     # Aufbau prüfen (Exit 0 = gut)
claude --plugin-dir ./omni-agent                 # Plugin nur für diese Sitzung laden
/reload-plugins                                 # nach jeder Änderung
/plugin                                         # Reiter „Errors“
claude --debug                                  # Hooks nachvollziehen
```

Bei `--plugin-dir` erscheint der `userConfig`-Dialog **nicht**; dann `/plugin configure omni-agent@omni-agent`.
`claude plugin install` fragt `userConfig` ebenfalls nicht ab (Optionen: `--config KEY=VALUE`).

---

## 11. Unsere beiden Manifeste (so legen wir sie an)

`.claude-plugin/plugin.json`
```json
{
  "name": "omni-agent",
  "description": "Startet Hintergrund-Agents mit austauschbarem Modell-Anbieter und austauschbarer Agent-CLI",
  "author": { "name": "Alex" },
  "license": "MIT",
  "repository": "https://github.com/<account>/omni-agent",
  "keywords": ["agents", "deepseek", "openrouter", "ollama", "codex", "opencode"]
}
```

`.claude-plugin/marketplace.json`
```json
{
  "name": "omni-agent",
  "owner": { "name": "Alex", "url": "https://github.com/<account>" },
  "description": "Marketplace für das Omni-Agent-Plugin",
  "plugins": [
    { "name": "omni-agent", "source": "./", "description": "Hintergrund-Agents mit Fremdmodellen" }
  ]
}
```

Hinweis: `version` fehlt absichtlich (siehe Abschnitt 9). `userConfig` fehlt absichtlich (Abschnitt 7, Weg A).

---

## 12. Verteilen

| Weg | Aufwand | Wann |
|---|---|---|
| **Öffentliches GitHub-Repo mit Plugin + Marketplace** | keiner | **jetzt**, Unterricht und Familie |
| Team-Einstellung `extraKnownMarketplaces` + `enabledPlugins` in `.claude/settings.json` | klein | für feste Gruppen. Auch dann installiert jede Person einmal selbst |
| Privates Repo | klein | Claude Code nutzt die git-Zugangsdaten des Rechners (SSH-Agent oder `gh auth setup-git`) |
| Anthropic-Verzeichnis | Antrag über `claude.ai/directory/manage`, bezahlter Plan nötig | später. Prüfdauer **nicht belegt** |

**Die Bitte „Claude, installiere mir das, hier ist die URL“:** Ob Claude das aus einer bloßen URL selbständig tut,
ist **nicht belegt**. Deshalb liegt eine `INSTALL.md` im Repo, geschrieben **für Claude** als Schrittliste mit Prüfschritten.
Wer dem Claude nur die URL gibt, bekommt damit trotzdem eine geführte Installation (Klonen, `install.sh`, Prüfen).
Cloud-Sitzungen (claude.ai/code) laden lokal installierte Plugins **nicht**.

---

## 13. Sicherheit

- **Ein Plugin läuft mit den Rechten des Nutzers.** Hooks, MCP, Monitore laufen außerhalb der Sandbox.
- Befehle aus `bin/`, die Claude per Bash startet, unterliegen den normalen Berechtigungsregeln. `allowed-tools:
  Bash(omni-agent *)` in unseren Skills sorgt dafür, dass genau dieser Befehl ohne Rückfrage läuft.
- Skills sind nur Text, aber Text, dem Claude folgt. Eine veröffentlichte Skill ist also auch Angriffsfläche.
- **Auto-Update kann geprüfte Dateien ändern.** Wer Omni-Agent installiert, vertraut dem Repo. Darum: kleine Dateiliste,
  keine Nachlader, keine Lifecycle-Skripte, README nennt jede Datei, die ausgeführt wird.
- Geheimnisse nie in Skill-Text, `.mcp.json` oder Skripten im Klartext.
- Deinstallieren löscht Optionen, Geheimnisse und den Datenordner (außer `--keep-data`).

---

## 14. Die 12 wichtigsten Fallen (nur die, die uns treffen)

| # | Falle | Folge für uns |
|---|---|---|
| 1 | Komponenten in `.claude-plugin/` laden nicht | Nur die zwei JSON-Dateien dort |
| 2 | Plugin wird in den Cache kopiert | Alles im Ordner, keine Pfade nach außen |
| 3 | `version` gesetzt, aber nicht erhöht | Version in der Entwicklung weglassen |
| 4 | `$CLAUDE_PLUGIN_ROOT` fehlt in Bash-Tool-Befehlen | Kern findet sich aus dem eigenen Pfad |
| 5 | Geheime `userConfig`-Werte kommen nicht in Skill-Text und nicht in `bin/` | Schlüssel über Umgebung oder `~/.omni-agent/env` |
| 6 | `CLAUDE.md` im Plugin wird nicht geladen | Anweisungen als Skill, plus `INSTALL.md` |
| 7 | `allowed-tools` schränkt nicht ein, sie erlaubt nur | Einschränkung machen wir im Kern (Werkzeugliste je Lauf) |
| 8 | Manifest-Name ≠ Eintrags-Name ergibt „Plugin not found“ | beide `omni-agent` |
| 9 | Ausführungsrecht der Skripte nicht belegt | `chmod +x` setzen, Git speichert den Modus, Aufruf in Skills über den Befehlsnamen |
| 10 | Cloud-Sitzungen laden lokale Plugins nicht | im README vermerken |
| 11 | Windows: Skripte laufen über Git Bash oder PowerShell | Ziel zuerst macOS, Linux, WSL |
| 12 | Hooks laufen schon beim Sitzungsstart | wenn überhaupt, nur ein schneller Selbsttest |

---

## 15. Was man mit Plugins sonst alles bauen kann (zum Lernen und für den Unterricht)

| Idee | Bausteine | Aufwand |
|---|---|---|
| Team-Regelwerk (Stil, Prüfpunkte) | Skills + Output-Style | klein |
| Automatischer Wächter („nie `rm -rf`“) | Hook mit Exit 2 | klein |
| Prüfer-Gespann (Sicherheit, Tests, Stil) | Agents + ein Orchestrator-Skill | mittel |
| Anbindung an einen Dienst (Tickets, CRM) | MCP-Server + `userConfig` für Schlüssel | mittel |
| Sprachunterstützung | LSP-Server | mittel |
| Live-Anzeige im Claude-Fenster | Mod (Plugin mit JS-Modul) | mittel |
| Fertige Abläufe aus mehreren Agents | Workflows | Doku-Details offen |

Omni-Agent berührt davon: Skills, bin, optional Hook. Das reicht, ist klein und lässt sich im Unterricht Zeile für Zeile erklären.

---

## 16. Nicht belegt, selbst prüfen beim Bauen

- Ob `sensitive`-Werte auf dem Mac im Schlüsselbund liegen.
- Ob Claude aus einer bloßen Repo-URL selbständig installiert (daher `INSTALL.md`).
- Ob `bin/`-Dateien zwingend `chmod +x` brauchen.
- Windows-Verhalten von `bin/`.
- Ob `/plugin marketplace add` ohne `owner/` geht (die Doku nennt nur `owner/repo`).
- Ob lang laufende Hintergrundprozesse über die Plugin-Mechanik selbst erlaubt sind (wir brauchen es nicht: Bash-Hintergrund).
