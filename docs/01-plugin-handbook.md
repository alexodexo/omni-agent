# Claude Code plugins: the handbook (applied to Omni-Agent)

As of 28 Oct 2026, Claude Code 2.1.304. Everything here comes from the official docs (`code.claude.com/docs`)
or from a locally checked plugin. Where something is not documented, the text says so explicitly. The raw version
with the doc page behind each statement: [`research/claude-code-plugin-notes.md`](research/claude-code-plugin-notes.md).

## 0. The essentials in nine lines

1. A **plugin** is a folder. Nothing more. Claude Code loads skills, hooks, MCP servers and commands from it.
2. A **marketplace** is a list (`marketplace.json`) that says: "These plugins exist, here is where they live."
3. A public GitHub repo can be **both at once**. No registration with Anthropic is needed.
4. Slash commands are **skills or commands**: `commands/run.md` in the plugin `omni-agent` becomes `/omni-agent:run`. Since 1.1.1 we use `commands/` for everything the user types (with a `!` inline for commands that need no model) and `skills/` only for internal instructions.
5. Skills are **text for Claude**, not code. Code lives in `bin/`, in hooks or in MCP servers.
6. API keys belong in `userConfig` with `sensitive: true`. **But:** this route does not reach `bin/` scripts (section 7).
7. On install, the plugin is **copied into a cache**. Everything it needs must be inside the folder.
8. Develop with: `claude plugin validate`, `claude --plugin-dir ./`, `/reload-plugins`.
9. Install for others: `/plugin marketplace add <account>/omni-agent`, then `/plugin install omni-agent@omni-agent`.

---

## 1. The mental picture

| Term | Picture | File |
|---|---|---|
| Plugin | A toolbox | Folder with `.claude-plugin/plugin.json` |
| Marketplace | A catalog that lists toolboxes | `.claude-plugin/marketplace.json` |
| Install | The toolbox is copied to `~/.claude/plugins/cache/...` | done by Claude Code |
| Enable | The toolbox is switched on in `settings.json` | `enabledPlugins` |

Without a plugin, every user would have to copy files by hand into `~/.claude/skills/`, `~/.claude/settings.json` and so on.
A plugin turns that into **one** command, one namespace, one version number and a clean uninstall.

Distinction: the local skill `plugin-authoring` ("mods") builds UI panels inside the Claude window. That is a special form
(a plugin with JavaScript in the Claude process). It is **not** what Omni-Agent means.

---

## 2. All building blocks, what they do and whether Omni-Agent needs them

| Building block | Location in the plugin | What it is | Omni-Agent |
|---|---|---|---|
| **Skills** | `skills/<name>/SKILL.md` | Instruction that Claude loads when the description fits, or that you call as `/plugin:name` | **yes**, these are our slash commands |
| Commands (old) | `commands/*.md` | Same as a skill, just one file. For new work use skills | no |
| **Agents** | `agents/*.md` | Separate assistant with its own context and system prompt | maybe later (reviewer agent) |
| **Hooks** | `hooks/hooks.json` | Command on an event (session starts, tool ran, answer done ...) | optional (self-test at start) |
| **MCP servers** | `.mcp.json` | Separate process that gives Claude **tools** | **not now**, reasoning in section 8 |
| LSP servers | `.lsp.json` | Code navigation for a language | no |
| Output styles | `output-styles/*.md` | Answer style, selectable with `/output-style` | no |
| Themes | `themes/*.json` (experimental) | Color scheme | no |
| Monitors | `monitors/monitors.json` (experimental) | Background command whose output reaches Claude as a message. Does **not** start with `-p` | conceivable later for "run finished" |
| **bin/** | `bin/<file>` | Files go on the **PATH of the Bash tool** while the plugin is active | **yes**, this is where the core `omni-agent` lives |
| settings.json | Plugin root | Only takes effect with two keys: `agent`, `subagentStatusLine` | no |
| Workflows | `workflows/*.js` | Scripts that steer several subagents (docs details not read) | no |
| Channels | Manifest `channels` | Messages from outside into a session | no |
| CLAUDE.md in the root | - | **Is not loaded.** Instructions belong in a skill | no |

Rule behind it: **Skill = text for Claude. Hook, MCP, bin = code that runs with your permissions.**

---

## 3. Folder layout

Only `plugin.json` and `marketplace.json` belong in `.claude-plugin/`. Everything else sits next to it in the root.
The most common beginner mistake is putting `skills/` inside `.claude-plugin/`: then nothing loads.

This is what Omni-Agent looks like:

```text
omni-agent/
├── .claude-plugin/
│   ├── plugin.json              Name, description, userConfig
│   └── marketplace.json         Catalog with one entry, source "./"
├── agents/worker.md         Subagent omni-agent:worker (thin forwarder)
├── commands/                /omni-agent:run, :review, :adversarial-review, :status, :result, :cancel, :accounts, :usage, :hosts, :doctor, :setup
├── hooks/hooks.json         SessionStart, SessionEnd, Stop
├── skills/
│   ├── omni-agent-runtime/SKILL.md   internal: contract of the subagent
│   ├── omni-agent-task/SKILL.md      internal: writing a task
│   └── omni-agent-results/SKILL.md   internal: passing on results
├── bin/
│   └── omni-agent                The core (executable), calls lib/
├── lib/                         Runner adapters, provider logic (Python)
├── providers.json               Providers as data
├── INSTALL.md                   written for Claude ("install this for me")
├── AGENTS.md                    the same for Codex and other orchestrators
├── README.md   LICENSE   .gitignore
└── docs/
```

---

## 4. The two manifests

### plugin.json

The only required field is `name`. The most important fields:

| Field | Note |
|---|---|
| `name` | kebab-case. Becomes the namespace of all commands. **Must not start with `claude-`, `anthropic-`, `cc-plugin-`.** `omni-agent` is allowed |
| `version` | If set, users stay on it until you raise it. **If omitted, every new commit is an update** |
| `description`, `author`, `license`, `repository`, `homepage`, `keywords` | Display and search. `homepage` must be a real URL, otherwise the plugin does not load |
| `userConfig` | Inputs asked for on activation (section 7) |
| `dependencies` | Other plugins that are installed along with it |
| `skills`, `hooks`, `mcpServers` | **Additional** paths next to the default folder |
| `commands`, `agents`, `outputStyles` | **Replace** the default folder |

Paths in the manifest start with `./`, stay inside the plugin folder and contain no `..`.

### marketplace.json

| Field | Note |
|---|---|
| `name` | What users type after the `@`: `omni-agent@omni-agent`. Comes from this file, **not** from the repo name |
| `owner` | Required, `{ "name": ... }` |
| `plugins[]` | per entry `name` and `source` |
| `renames` | old name -> new name. **Useful if we rename from `fremdagent`** |

`source` variants: relative path `"./"` (plugin lives in the same repo), `github`, `url`, `git-subdir`, `npm`, `archive`.
For Omni-Agent `"./"` is enough.

Our two files are shown in full in section 11 of this document.

---

## 5. Skills, i.e. slash commands

**Namespace:** `skills/run/SKILL.md` in the plugin `omni-agent` becomes `/omni-agent:run`. The plugin name always comes first,
so two plugins do not collide. Agents are named accordingly: `omni-agent:name`.

**Structure of a skill:** frontmatter (settings) and below it the text that Claude reads.

```markdown
---
description: Starts a background agent with a third-party model
argument-hint: "[provider] [task-file]"
disable-model-invocation: true
allowed-tools: Bash(omni-agent *)
---
Start with `omni-agent run $ARGUMENTS` in the background ...
```

| Frontmatter | Meaning |
|---|---|
| `description` | **Decisive.** This is how Claude recognizes when the skill fits |
| `argument-hint` | Hint while typing |
| `disable-model-invocation: true` | Only you can call it, Claude never on its own. Good for commands with side effects |
| `user-invocable: false` | Only Claude can load it, not in the `/` menu. Good for background knowledge |
| `allowed-tools` | These tools run **without a prompt** while the skill is active. It **restricts nothing** |
| `disallowed-tools` | removes tools |
| `context: fork` | Runs in its own subagent without the conversation history |
| `model`, `effort` | for this turn only |
| `paths` | automatically for matching files |

**Text building blocks in a skill:** `$ARGUMENTS` (everything after the command), `$0` (first word), `${CLAUDE_PLUGIN_ROOT}`,
`${CLAUDE_PLUGIN_DATA}`, `${CLAUDE_SKILL_DIR}`. `` !`command` `` runs **before** sending; if it fails, the call aborts.

**Three kinds for Omni-Agent (since 1.1.1):**
- *Command* (`commands/*.md`): `disable-model-invocation: true`, you trigger it deliberately. `status`, `result`, `cancel`, `doctor`, `accounts`
  run their command through the `!` inline, with no model in between. `run` calls the subagent.
- *Subagent* (`agents/worker.md`): so that Claude (also in `/goal`) can delegate on its own. The description is the trigger.
  Claude cannot call blocked commands itself; the subagent can.
- *Internal skills* (`user-invocable: false`): instructions that the subagent or the commands load.

---

## 6. Paths and variables

| Variable | Points to | Used for |
|---|---|---|
| `${CLAUDE_PLUGIN_ROOT}` | `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` | Scripts that ship with the plugin. **Changes on every update, never write it into files** |
| `${CLAUDE_PLUGIN_DATA}` | `~/.claude/plugins/data/<id>/` | Things that survive an update. **Deleted on uninstall** |
| `${CLAUDE_PROJECT_DIR}` | Project folder | project-local things |

**The two traps here:**

1. **Cache copy.** Marketplace plugins are copied. A file outside the plugin folder (`../shared`) is missing from the cache.
   That is why Omni-Agent lives completely in one folder.
2. **The variables do not exist in the environment of commands that Claude starts through the Bash tool.** A script in `bin/`
   therefore cannot read `$CLAUDE_PLUGIN_ROOT`. Solution (our own conclusion, not from the docs): the core finds its location from
   its own file path. We do not put persistent runs and keys in `PLUGIN_DATA` but in `~/.omni-agent/`
   (reasons: section 7 and `02-architecture.md`).

The variables are resolved in: hook commands, MCP configuration, LSP configuration and in the text of skills and agents.

---

## 7. Secrets: `userConfig`, and why it is not enough for Omni-Agent

`userConfig` holds questions that Claude Code asks when the plugin is activated.

| Field | Note |
|---|---|
| `type` | `string`, `number`, `boolean`, `directory`, `file` |
| `title`, `description` | Required, text in the dialog |
| `required`, `default`, `options`, `multiple`, `min`, `max` | as expected |
| **`sensitive: true`** | Input masked, stored in the "secure storage of the platform" instead of in `settings.json` |

Whether this secure storage is the Keychain on the Mac is **not documented**.

**Where does the value arrive?**

| Target | Works |
|---|---|
| MCP server (`env`, `args`, `url`, `headers`) via `${user_config.KEY}` | yes |
| Hook in exec format (`args`) via `${user_config.KEY}` | yes |
| Hook environment as `CLAUDE_PLUGIN_OPTION_<KEY>` | yes |
| Text in skills and agents | non-secret values only. **Secrets are replaced by a placeholder** |
| Shell hook, monitor, `headersHelper` | no, error |
| **`bin/` script that Claude starts through Bash** | **no, it does not arrive there** |

**Consequence for Omni-Agent:** The core is a `bin/` command. It does not see `userConfig` secrets. There are three ways:

| Way | How | Verdict |
|---|---|---|
| A | Core reads keys from the **environment** (`DEEPSEEK_API_KEY`) and falls back to `~/.omni-agent/env` (mode 600) | **chosen:** works in every environment, without the plugin, also under Codex |
| B | Core as an **MCP server**, keys via `${user_config.*}` | clean and plugin-native, but needs a Node or Python runtime in the MCP and moves everything into tools. Later as a comfort tier |
| C | Hook writes `userConfig` into a file | throws away the benefit of the secure storage, no |

Input without chat: `/omni-agent:setup` guides you, creates the file `~/.omni-agent/env` with empty lines and opens it.
You enter the key there yourself. It **never goes through the chat**.

---

## 8. Hooks, MCP, bin, monitor: what when

| Mechanism | Runs | Good for | Omni-Agent |
|---|---|---|---|
| Skill | as text in Claude's head | Instruction, procedure | Commands and knowledge |
| **bin/** | when Claude (or you) calls it through Bash | a real program you also need without Claude | **the core** |
| Hook | on events, automatically | Checking, blocking (exit 2), logging | optional: self-test at `SessionStart` |
| MCP server | permanently in the background | Tools with state, keys from `userConfig` | not now |
| Monitor | permanently, reports to Claude | "run finished" message | not now, not started with `-p` |

**Why bin/ instead of MCP is enough for "background agents":** The docs say nothing about whether plugins may run background agents
permanently. They do not need to. Claude Code's **Bash tool can start commands in the background** and
Claude is woken when the command ends. `omni-agent run` is an ordinary, blocking command. Claude starts it in the
background. No daemon, no queue, no separate process. This is also the route that works today in the wrapper.

Hooks run **from the start of the session**, not only when a skill is called. The matcher should be narrow. Exit 2 blocks, other
error codes let the action through (fail-open).

---

## 9. Installation, scopes, updates

**For users in Claude Code:**

```text
/plugin marketplace add <account>/omni-agent
/plugin install omni-agent@omni-agent
```
or in one step: `/plugin install omni-agent --marketplace <account>/omni-agent` (since 2.1.275).
Pin to a revision: `<account>/omni-agent#v0.1.0`.

**In the shell:** `claude plugin install | uninstall | enable | disable | update | list | details | validate | tag`.

| Scope | Writes to | Effect |
|---|---|---|
| `user` (default) | `~/.claude/settings.json` | all projects on the machine |
| `project` | `.claude/settings.json` | everyone who clones the repo (they still have to install once) |
| `local` | `.claude/settings.local.json` | only you, only this repo |

**Where things live:** `~/.claude/plugins/cache/...` (copy), `.../data/...` (persistent data), `.../marketplaces/...` (clone of the catalog),
`installed_plugins.json`, `known_marketplaces.json`.

**Updates:**
- The version is `version` from `plugin.json`. If it is missing, the commit SHA counts.
- **If `version` is set and you push without raising it, nobody gets anything.** This is the most common update trap.
- Auto-update is **off by default** for third-party marketplaces; users switch it on under `/plugin` -> Marketplaces
  or update with `claude plugin update`.
- Running sessions only notice after `/reload-plugins`.

**Recommendation for Omni-Agent:** During development **omit** `version` (every push = update, good for teaching).
For a release set `version` and tag with `claude plugin tag --push`.

---

## 10. Developing and testing

```bash
claude plugin validate --strict ./omni-agent     # check the structure (exit 0 = good)
claude --plugin-dir ./omni-agent                 # load the plugin for this session only
/reload-plugins                                 # after every change
/plugin                                         # "Errors" tab
claude --debug                                  # trace hooks
```

With `--plugin-dir` the `userConfig` dialog does **not** appear; use `/plugin configure omni-agent@omni-agent` instead.
`claude plugin install` does not ask for `userConfig` either (option: `--config KEY=VALUE`).

---

## 11. Our two manifests (this is how we set them up)

`.claude-plugin/plugin.json`
```json
{
  "name": "omni-agent",
  "description": "Starts background agents with an interchangeable model provider and agent CLI",
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
  "description": "Marketplace for the Omni-Agent plugin",
  "plugins": [
    { "name": "omni-agent", "source": "./", "description": "Background agents with third-party models" }
  ]
}
```

Note: `version` is missing on purpose (see section 9). `userConfig` is missing on purpose (section 7, way A).

---

## 12. Distribution

| Way | Effort | When |
|---|---|---|
| **Public GitHub repo with plugin + marketplace** | none | **now**, teaching and family |
| Team setting `extraKnownMarketplaces` + `enabledPlugins` in `.claude/settings.json` | small | for fixed groups. Even then each person installs once themselves |
| Private repo | small | Claude Code uses the machine's git credentials (SSH agent or `gh auth setup-git`) |
| Anthropic directory | Application via `claude.ai/directory/manage`, paid plan required | later. Review time **not documented** |

**The request "Claude, install this for me, here is the URL":** Whether Claude does this on its own from a bare URL
is **not documented**. That is why the repo contains an `INSTALL.md`, written **for Claude** as a step list with check steps.
Anyone who gives Claude only the URL still gets a guided installation (clone, `install.sh`, verify).
Cloud sessions (claude.ai/code) do **not** load locally installed plugins.

---

## 13. Security

- **A plugin runs with the user's permissions.** Hooks, MCP and monitors run outside the sandbox.
- Commands from `bin/` that Claude starts through Bash are subject to the normal permission rules. `allowed-tools:
  Bash(omni-agent *)` in our skills makes sure exactly this command runs without a prompt.
- Skills are only text, but text that Claude follows. A published skill is therefore also an attack surface.
- **Auto-update can change reviewed files.** Anyone who installs Omni-Agent trusts the repo. Hence: small file list,
  no downloaders, no lifecycle scripts, the README names every file that is executed.
- Never put secrets in skill text, `.mcp.json` or scripts in plain text.
- Uninstalling deletes options, secrets and the data folder (except with `--keep-data`).

---

## 14. The 12 most important traps (only those that affect us)

| # | Trap | Consequence for us |
|---|---|---|
| 1 | Components in `.claude-plugin/` do not load | Only the two JSON files there |
| 2 | Plugin is copied into the cache | Everything in the folder, no paths to the outside |
| 3 | `version` set but not raised | Omit the version during development |
| 4 | `$CLAUDE_PLUGIN_ROOT` is missing in Bash-tool commands | Core finds itself from its own path |
| 5 | Secret `userConfig` values do not reach skill text or `bin/` | Keys via environment or `~/.omni-agent/env` |
| 6 | `CLAUDE.md` in the plugin is not loaded | Instructions as a skill, plus `INSTALL.md` |
| 7 | `allowed-tools` does not restrict, it only permits | We do the restriction in the core (tool list per run) |
| 8 | Manifest name != entry name gives "Plugin not found" | both `omni-agent` |
| 9 | Execute permission of scripts not documented | Set `chmod +x`, Git stores the mode, skills call by command name |
| 10 | Cloud sessions do not load local plugins | note it in the README |
| 11 | Windows: scripts run via Git Bash or PowerShell | Target macOS, Linux, WSL first |
| 12 | Hooks run already at session start | if at all, only a fast self-test |

---

## 15. What else you can build with plugins (for learning and teaching)

| Idea | Building blocks | Effort |
|---|---|---|
| Team rulebook (style, checkpoints) | Skills + output style | small |
| Automatic guard ("never `rm -rf`") | Hook with exit 2 | small |
| Reviewer team (security, tests, style) | Agents + one orchestrator skill | medium |
| Connection to a service (tickets, CRM) | MCP server + `userConfig` for keys | medium |
| Language support | LSP server | medium |
| Live display in the Claude window | Mod (plugin with JS module) | medium |
| Ready-made flows from several agents | Workflows | docs details open |

Omni-Agent touches: skills, bin, optionally a hook. That is enough, it is small and can be explained line by line in a class.

---

## 16. Not documented, check yourself when building

- Whether `sensitive` values are stored in the Keychain on the Mac.
- Whether Claude installs on its own from a bare repo URL (hence `INSTALL.md`).
- Whether `bin/` files strictly need `chmod +x`.
- Windows behavior of `bin/`.
- Whether `/plugin marketplace add` works without `owner/` (the docs only name `owner/repo`).
- Whether long-running background processes are allowed through the plugin mechanism itself (we do not need it: Bash background).
