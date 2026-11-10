# Claude Code plugins: theory and practice (as of Claude Code 2.1.304)

Sources: the official docs at code.claude.com/docs (pages are named per section) and local practice under `~/.claude/plugins/`. verified = stated in the fetched docs or checked locally. not documented = not found in the docs.

Scope: The local skill `/plugin-authoring` (mods) concerns UI panes. A mod is a plugin with a JavaScript hooks module (`modules` in `hooks/hooks.json`). That is not what Omni-Agent needs. See `plugins/mods/overview` and `plugins/overview`.

---

## 1. Terms and components

Plugin = a folder with an optional manifest `.claude-plugin/plugin.json` that bundles components and loads them as one unit. Marketplace = a catalog (`.claude-plugin/marketplace.json`) that lists plugins and their sources. Source: `plugins/overview`, `plugins/create-marketplace`.

| Component | Default location in the plugin | What it does | Source |
|---|---|---|---|
| Skills | `skills/<name>/SKILL.md` | Instructions that Claude loads when the `description` matches; can also be invoked as `/plugin:skill` | `plugins/components`, `skills` |
| Commands (old) | `commands/*.md` | Like skills, but a single file. Use skills for new plugins | `plugins/components` |
| Agents (subagents) | `agents/*.md` | Separate assistant with its own context; the Markdown body is the system prompt | `plugins/components`, `sub-agents` |
| Hooks | `hooks/hooks.json` | Shell, HTTP, MCP tool or prompt actions on lifecycle events | `plugins/components`, `hooks` |
| MCP servers | `.mcp.json` (or key `mcpServers`) | Tools from external processes or services | `plugins/components`, `mcp` |
| LSP servers | `.lsp.json` | Diagnostics and navigation for a language | `plugins/components` |
| Output styles | `output-styles/<name>.md` | Response style, appears in `/output-style` as `<plugin>:<name>` | `plugins/components` |
| Themes | `themes/<slug>.json` (manifest `experimental.themes`) | Color scheme for `/theme` | `plugins/components`, `manifest-reference` |
| Monitors | `monitors/monitors.json` (manifest `experimental.monitors`) | Background shell command whose output Claude receives as a notification. Does not start with `-p` | `plugins/components` |
| `bin/` | `bin/<file>` | Files are put on the PATH of the Bash tool while the plugin is active | `plugins/components` |
| `settings.json` | Plugin root | Only two keys take effect: `agent`, `subagentStatusLine`. The rest is discarded | `plugins/components` |
| Workflows | `workflows/*.js` (manifest `workflows`) | Scripts that orchestrate several subagents | `manifest-reference` (only the field is verified, details not read) |
| Channels | Manifest `channels` + MCP server | Messages from outside into a session | `plugins/components`, `manifest-reference` |
| Mods (JS modules) | `modules` in `hooks/hooks.json` | JavaScript inside the Claude Code process, see above | `plugins/mods/overview` |
| CLAUDE.md in the plugin root | – | NOT loaded. Instructions belong in a skill | `plugins/components`, `manifest-reference` |

Marketplace and plugin: A marketplace is only a catalog. The plugins live elsewhere (in the same repo, on GitHub, at a git URL, as an npm package, as an archive). Source: `plugins/marketplace-reference`.

---

## 2. Directory layout

Plugin root = the folder that contains `.claude-plugin/`. Only `plugin.json` belongs in `.claude-plugin/`. Everything else (skills, hooks, bin, ...) lives in the root. Source: `plugins/manifest-reference` (Standard layout), `plugins/create`.

```text
omni-agent/
├── .claude-plugin/
│   ├── plugin.json          # manifest (optional, but needed for name/version/userConfig)
│   └── marketplace.json     # only if the repo is also a marketplace
├── skills/agent-start/SKILL.md
├── agents/
├── hooks/hooks.json
├── .mcp.json
├── bin/omni-agent            # chmod +x recommended (see section 8)
├── scripts/
├── package.json + package-lock.json   # only if there are npm dependencies
└── settings.json            # optional, only agent/subagentStatusLine
```

Local example: `~/.claude/plugins/marketplaces/claude-plugins-official/plugins/feature-dev/` follows exactly this pattern (`.claude-plugin/plugin.json`, `commands/feature-dev.md`, `agents/*.md`, `README.md`, `LICENSE`).

---

## 3. `.claude-plugin/plugin.json`

Source: `plugins/manifest-reference` (Fields, Path rules, User configuration). The only required field is `name`.

| Field | Type | Required | Note |
|---|---|---|---|
| `name` | string | yes | kebab-case, no spaces, `@`, `:` or path separators. Namespace for all components |
| `displayName` | string | no | display only |
| `version` | string | no | not checked for semver. If set, users stay on this version until it changes |
| `description` | string | no | Text shown in `/plugin` |
| `author` | object | no | `name` required; `email`, `url` optional |
| `homepage` | string | no | must parse as a URL, otherwise the plugin does not load |
| `repository` | string | no | not validated |
| `license` | string | no | SPDX, e.g. `MIT` |
| `keywords` | string[] | no | search |
| `metadata` | object | no | free-form, Claude Code does not read it (from 2.1.222) |
| `icon`, `documentationUrl`, `supportUrl`, `privacyPolicyUrl`, `termsOfServiceUrl` | string | no | only for the Anthropic directory |
| `defaultEnabled` | boolean | no | default `true` |
| `dependencies` | (string \| object)[] | no | `"name"`, `"name@marketplace"` or `{name, marketplace?, version?}` |
| `settings` | object | no | only `agent`, `subagentStatusLine` take effect |
| `userConfig` | object | no | values asked for on activation (section 6) |
| `channels` | object[] | no | binds a channel to an MCP server |
| `skills` | path \| path[] | no | IN ADDITION to the default `skills/`. `"."` or `"./"` = root |
| `commands` | path \| path[] \| object | no | REPLACES the default `commands/` |
| `agents` | path \| path[] | no | REPLACES `agents/`; `.md` files only |
| `hooks` | path \| object \| array | no | IN ADDITION to `hooks/hooks.json` |
| `mcpServers` | path \| object \| array | no | IN ADDITION to `.mcp.json`; same name = the later one replaces the earlier one |
| `lspServers` | path \| object \| array | no | IN ADDITION to `.lsp.json` |
| `outputStyles` | path \| path[] | no | REPLACES `output-styles/` |
| `workflows` | path \| path[] | no | REPLACES `workflows/` |
| `experimental` | object | no | `themes`, `monitors`, `evals` (shape may change) |

Path rules: Every component path starts with `./` (except `"."` for `skills`), stays inside the plugin root, and exists. `..` and backslashes on macOS/Linux are rejected.

Minimal example (source: `plugins/create`):
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

Source: `plugins/marketplace-reference`, `plugins/create-marketplace`, `plugins/host-marketplace`.

Top level:

| Field | Required | Note |
|---|---|---|
| `name` | yes | Letters, digits, `.`, `_`, `-`. Users type it after `@`: `plugin@<name>` |
| `owner` | yes | `{ "name": ..., "email"?, "url"? }` |
| `plugins` | yes | Array of plugin entries |
| `description`, `version` | no | A missing `description` triggers a validator warning |
| `metadata.pluginRoot` | no | Base folder so that `"source": "formatter"` resolves to `./plugins/formatter` (from 2.1.239) |
| `renames` | no | old name → new name or `null` (removes). Prevents "not found" after a rename |
| `forceRemoveDeletedPlugins` | no | `true` = removed plugins are uninstalled for users |
| `allowCrossMarketplaceDependenciesOn` | no | Allows dependencies from other marketplaces |

Plugin entry (`plugins[]`): `name` and `source` are required. Also `description`, `version`, `category`, `tags`, `strict` (default `true`), `defaultEnabled`, `displayName`, `dependencies`, `metadata`, `headers`/`headersHelper` (only for `archive`), `relevance`. All fields from `plugin.json` are allowed as well.

`source` variants (source: `plugins/marketplace-reference` → "Plugin sources"):

| Form | Example | Note |
|---|---|---|
| Relative path (string) | `"./"` or `"./plugins/x"` | Must start with `./`, path relative to the marketplace root (not to `.claude-plugin/`) |
| `github` | `{"source":"github","repo":"owner/repo","ref":"v1","sha":"<40 hex>"}` | `ref`/`sha` optional |
| `url` | `{"source":"url","url":"https://host/x.git","ref":"main"}` | any git URL |
| `git-subdir` | `{"source":"git-subdir","url":"owner/mono","path":"tools/x"}` | Subfolder of a repo, sparse checkout |
| `npm` | `{"source":"npm","package":"@org/x","version":"^2.0.0"}` | Lifecycle scripts do not run |
| `archive` | `{"source":"archive","url":"https://...zip","sha256":"<64 hex>"}` | https only; `sha256` verifies the download |
| `command` | `{"source":"command","command":"tool path"}` | Command prints a directory; the user must confirm the command |

Note on `strict`: If the plugin has its own `plugin.json` and the entry sets `commands`, `agents`, `skills`, `hooks`, `outputStyles` or `themes`, then: `strict: true` (default) = appended (for `hooks`, the matchers replace per event). `strict: false` = conflict, the plugin does not load.

`version` resolution (`plugins/loading`, "Versions and updates"): 1. `version` in `plugin.json`, 2. `version` in the entry, 3. depending on the source: github/url/git-subdir = commit SHA (12 characters); archive = sha256; relative path in a git marketplace = commit SHA of the folder; npm = `unknown`.

Example marketplace in the same repo (source: `plugins/publish`):
```json
{
  "name": "your-marketplace",
  "owner": { "name": "Your Name" },
  "plugins": [
    { "name": "deploy-helper", "source": "./" }
  ]
}
```

Local example: `~/.claude/plugins/marketplaces/claude-plugins-official/.claude-plugin/marketplace.json` has `$schema`, `name`, `description`, `owner`, `renames` and `plugins[]` with `git-subdir` sources including `ref` and `sha`.

---

## 5. Namespaces, skills vs. commands, frontmatter

Namespaces (source: `plugins/components`, `skills`, `sub-agents`):
- Skill `skills/review/SKILL.md` in plugin `my-plugin` → `/my-plugin:review`. The frontmatter `name` replaces only the last segment.
- Command `commands/db/migrate.md` → `/my-plugin:db:migrate`.
- Agent `agents/security-reviewer.md` → `my-plugin:security-reviewer`; invoked as `@agent-my-plugin:security-reviewer`. Subfolders become part of the name (`agents/review/security.md` → `my-plugin:review:security`).
- Manifest name ≠ entry name: installation uses the entry name; the namespace of the components is the manifest name. Keep them identical (`plugins/marketplace-reference`).

Skills vs. commands (source: `skills`, `plugins/components`): Commands are the older form. Skills additionally support helper files in the folder and auto-loading. The same file can be both; both keep working.

Skill frontmatter fields (source: `skills`, Frontmatter section; not read completely, list as returned by the fetch):

| Field | Meaning |
|---|---|
| `name` | Command name (default: folder name) |
| `description` | When the skill applies; truncated together with `when_to_use` to 1,536 characters |
| `when_to_use` | additional trigger text |
| `argument-hint` | Autocomplete hint, e.g. `[task]` |
| `arguments` | named arguments for `$name` |
| `disable-model-invocation: true` | only the user can invoke |
| `user-invocable: false` | only Claude can invoke, not in the `/` menu |
| `allowed-tools` | Tools without a prompt during the skill's turn. Does NOT restrict. Cleared at the next user message |
| `disallowed-tools` | Remove tools while the skill is active |
| `model`, `effort` | for the current turn only |
| `context: fork` | Runs in a subagent. No access to the conversation history |
| `agent` | Subagent type for `context: fork` (default `general-purpose`) |
| `background` | with `fork`: default `true`; `false` waits for the result |
| `hooks` | Hooks registered on invocation that stay until the session ends |
| `paths` | Glob patterns for automatic activation |
| `shell` | `bash` (default) or `powershell` for `` !`cmd` `` |

Substitutions in skill text: `$ARGUMENTS`, `$0`/`$ARGUMENTS[0]`, `$name` (with `arguments`), `${CLAUDE_SKILL_DIR}`, `${CLAUDE_SESSION_ID}`, `${CLAUDE_EFFORT}`, `${CLAUDE_PROJECT_DIR}`, `${CLAUDE_PLUGIN_ROOT}`, `${CLAUDE_PLUGIN_DATA}` (plugin skills only). `` !`command` `` runs before sending; if it fails, the invocation aborts.

Agent frontmatter in a plugin (source: `plugins/components`, Agents): supports `name`, `description`, `model`, `effort`, `maxTurns`, `tools`, `disallowedTools`, `skills`, `memory`, `background`, `isolation` (`worktree` only), `color`, among others. IGNORED are `permissionMode`, `hooks`, `mcpServers`, `initialPrompt`. Hooks and MCP servers therefore belong in the plugin, not in the agent file.

Local example `feature-dev/commands/feature-dev.md`: `description`, `argument-hint`. `feature-dev/agents/code-reviewer.md`: `name`, `description`, `tools`, `model`, `color`.

---

## 6. Variables, data, userConfig, environment variables

Path variables (source: `plugins/manifest-reference` → Environment variables; `plugins/components` → Path variables):

| Variable | Value | Purpose |
|---|---|---|
| `${CLAUDE_PLUGIN_ROOT}` | Install folder of the active version (`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`) | Scripts and binaries. CHANGES on update, so store nothing there |
| `${CLAUDE_PLUGIN_DATA}` | `~/.claude/plugins/data/<id>/` (id: characters other than letters/digits/`_`/`-` → `-`) | Persists across updates: `node_modules`, venvs, caches, state. Deleted on uninstall from the last scope (unless `--keep-data`) |
| `${CLAUDE_PROJECT_DIR}` | Project root | Project-local files |

Where resolved (source: `plugins/manifest-reference`, table "Where each variable resolves"):
- Hook `command`/`args`: substitution and environment.
- Monitor `command`: substitution, no environment variables.
- MCP stdio `command`/`args`/`env`: substitution; the environment receives `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA`.
- MCP http/sse/ws `url`/`headers`: substitution.
- LSP `command`/`args`/`env`/`workspaceFolder`.
- Skill, command and agent text: substitution in the Markdown.
- Not in the environment of commands that Claude runs through the Bash tool. Docs wording: "The variables aren't present in the environment of commands Claude runs through the Bash tool." Consequence: a `bin/` script cannot read `${CLAUDE_PLUGIN_ROOT}` from the environment. Recommendation (our own conclusion, not the docs): derive the path from `$0`, e.g. `ROOT="$(cd "$(dirname "$0")/.." && pwd)"`.

Environment variables for processes (hooks additionally get `CLAUDE_PLUGIN_OPTION_<KEY>`; monitors get NO option values).

### userConfig (source: `plugins/manifest-reference` → User configuration; `plugins/components` → Ask the user for configuration values)

Fields per option (strict, unknown keys = error):

| Field | Required | Note |
|---|---|---|
| `type` | yes | `string`, `number`, `boolean`, `directory`, `file` |
| `title` | yes | Dialog label |
| `description` | yes | Help text |
| `required` | no | Dialog does not accept empty input |
| `default` | no | string, number, boolean or string[] |
| `options` | no | fixed choice (`string` only, not `sensitive`/`multiple`; from 2.1.271) |
| `multiple` | no | string[] |
| `sensitive` | no | masked, stored in secure storage |
| `min`, `max` | no | for `number` |

Keys: letters, digits, underscore, must not start with a digit.

Storage location: Non-sensitive values go in `pluginConfigs` in `settings.json`. Sensitive values go to the "platform's secure credential store". Whether that is the Keychain app on a Mac is NOT stated in the text that was read (not documented).

Retrieving the value:
- `${user_config.KEY}`: in MCP config (`command`, `args`, `env`, `url`, `headers`), LSP config, exec-form hook `args`, skill and agent text. In skill and agent text, sensitive values are NOT substituted but replaced by a placeholder.
- `CLAUDE_PLUGIN_OPTION_<KEY>`: as an environment variable for hooks (uppercase). Shell-form hooks read e.g. `$CLAUDE_PLUGIN_OPTION_API_KEY`.
- Forbidden with `${user_config.*}`: shell-form hook `command`, monitor `command`, MCP `headersHelper`. This produces an error.

Dialog: appears on installation in `/plugin`, on `/plugin install` in the session, and on activation in the "Installed" tab. Afterwards: `/plugin configure <plugin>@<marketplace>`. `claude plugin install` does NOT ask: pass values with `--config KEY=VALUE` or `claude plugin configure <plugin> --values-stdin` (JSON via stdin). With `--plugin-dir` the dialog does not appear (docs error example).

Local example: `code-modernization/.claude-plugin/plugin.json` has `userConfig` with `type`, `title`, `description`, `default` and `options`.

Environment for hooks (source: `plugins/components`, Hooks): `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA`, `CLAUDE_PLUGIN_OPTION_<KEY>`, and `CLAUDE_PROJECT_DIR`.

---

## 7. Installation and lifecycle

### Commands in the session (source: `plugins/install`, `plugins/cli-reference`)

| Command | Effect |
|---|---|
| `/plugin` | Panel with tabs Discover, Installed, Marketplaces, Errors |
| `/plugin install <name>@<marketplace>` | opens details, scope choice |
| `/plugin install <name> --marketplace <owner/repo>` | adds the marketplace and installs (from 2.1.275) |
| `/plugin marketplace add <source>` / `list` / `update [name]` / `remove <name>` | Marketplace management |
| `/plugin configure <plugin>@<marketplace>` | userConfig dialog |
| `/reload-plugins` (`--force`) | reloads changes (without restart) |

### Commands in the shell (source: `plugins/cli-reference`, checked locally: `claude plugin --help`)

| Command | Important options |
|---|---|
| `claude plugin install <plugin> [--scope user\|project\|local] [--config K=V] [-y] [--json] [--marketplace <src>]` | Default scope `user` |
| `claude plugin uninstall <plugin> [--scope ...] [--keep-data] [--prune] [-y]` | Alias `remove` |
| `claude plugin enable <plugin> [--scope]` / `disable [plugin] [--scope] [-a]` | |
| `claude plugin update <plugin> [--scope ...] [-y]` | |
| `claude plugin list [--json] [--available]` | |
| `claude plugin details <name>` | Component list and token cost |
| `claude plugin configure <plugin> [--values-stdin]` | |
| `claude plugin validate <path> [--strict] [--json]` | Exit 0 on success; `--strict` turns warnings into errors |
| `claude plugin init <name> [--with skills hooks mcp ...] [--description] [--force]` | creates a plugin under `~/.claude/skills/<name>/` |
| `claude plugin tag [path] [--push] [--dry-run]` | creates `<name>--v<version>` |
| `claude plugin prune` | removes auto-dependencies that are no longer needed |
| `claude plugin marketplace add <source> [--scope project] [--sparse] [--claudeai]` / `list` / `update` / `remove` | |
| `claude --plugin-dir <path>` (repeatable) | loads a folder or `.zip` for this session only |
| `claude --plugin-url <zip-url>` | loads a zip from a URL for one session |
| Env `CLAUDE_CODE_PLUGIN_DIRS=/abs/path` | like `--plugin-dir`; project settings cannot set it (from 2.1.280) |

Exit codes (source: `plugins/cli-reference`): 0 success, 1 error; `validate` additionally returns 2 on an unexpected error.

### Scopes (source: `plugins/install` → "Choose an install scope"; `plugins/loading`)

| Scope | Writes to | Effect |
|---|---|---|
| `user` | `~/.claude/settings.json` (`enabledPlugins`) | all projects on the machine |
| `project` | `.claude/settings.json` (commit it) | everyone who clones the repo; each team member still has to install once |
| `local` | `.claude/settings.local.json` | this repo only, for you only |
| `managed` | Managed settings | Admin, update only |

Precedence on conflict: local overrides project, project overrides user (docs wording in `plugins/install`). Key: `"<name>@<marketplace>": true|false` in `enabledPlugins`.

### Where things are on disk (source: `plugins/loading` → "Find plugins on disk"; checked locally)

| Path (under `~/.claude/plugins/`) | Contents |
|---|---|
| `cache/<marketplace>/<plugin>/<version>/` | copied plugin version; load target of `${CLAUDE_PLUGIN_ROOT}` |
| `data/<id>/` | `${CLAUDE_PLUGIN_DATA}` |
| `marketplaces/<name>/` | Clone of the marketplace (GitHub/Git) |
| `installed_plugins.json` | Install list with scope, `installPath`, `version`, `gitCommitSha` |
| `known_marketplaces.json` | Marketplace source and `lastUpdated` |
| `.orphaned_at` in the version folder | Marker; cleaned up after 14 days |

Checked locally: `installed_plugins.json` contains `feature-dev@claude-plugins-official` with scope `user`, `installPath` in `cache/...`, version `1.0.1`, `gitCommitSha`. `known_marketplaces.json` lists `source: github` with `repo: anthropics/claude-plugins-official`.

Copy rule (source: `plugins/loading` → "In-place and copied plugins"): Marketplace plugins are COPIED into the cache. Files outside the plugin folder (e.g. `../shared`) are then missing. Exceptions that load directly from the source folder: `--plugin-dir`, skills-dir plugins, relative paths in a marketplace that was added from a local path.

### Updates (source: `plugins/loading` → "Versions and updates", "When auto-update runs"; `plugins/install` → "Keep plugins updated")

- A user gets a new version only if the computed version changes.
- A set `version` in `plugin.json` = users stay on it, even with new commits. Without `version` (in both places) = the commit SHA serves as the version (for github/url/git-subdir).
- Auto-update: ON by default for official marketplaces (`claude-plugins-official` and others), OFF for all others. Toggle: `/plugin` → Marketplaces → "Enable auto-update", or `autoUpdate` in `extraKnownMarketplaces`.
- Flow: After the first message, Claude Code waits up to 10 minutes (random), then updates. The running session keeps the old version; message "Run /reload-plugins to apply". Hooks/MCP/LSP switch after `/reload-plugins`, monitors need a restart.
- Manual: `claude plugin update <plugin>@<marketplace>`.
- Relative plugins loaded locally in place: every session loads the current state, regardless of `version`.

### Development loop (source: `plugins/create`, `plugins/components`, `plugins/troubleshooting`)

1. Create the folder, write `plugin.json`.
2. `claude plugin validate ./omni-agent`.
3. Start `claude --plugin-dir ./omni-agent`; in the test, invoke `/omni-agent:<skill>`.
4. Changes: `/reload-plugins`. Checks: `/plugin` → Errors, `claude plugin list`, `/mcp`, `claude --debug` for hooks.

### Dependencies (source: `plugins/dependencies`, `plugins/loading` → "Node.js package dependencies")

- `dependencies` in `plugin.json` (see section 3). Dependencies are installed and activated along with the plugin.
- Other marketplace: only if the root marketplace is listed in `allowCrossMarketplaceDependenciesOn`.
- Version ranges (`"~2.1.0"`, `"^2.0"`) are resolved against git tags `<plugin>--v<version>`.
- Node dependencies: Claude Code installs them automatically into the cache if `package.json` AND a lockfile exist (`bun.lock`, `npm-shrinkwrap.json` or `package-lock.json`, npm lockfileVersion 2 or 3). Rules: registry packages with an exact version only; no lifecycle scripts (`--ignore-scripts`); no `overrides`/`patchedDependencies`; timeout 60 s. This cannot be turned off. A Yarn or pnpm lockfile = skipped.
- Alternative per the docs: a SessionStart hook installs into `${CLAUDE_PLUGIN_DATA}` (example in `plugins/components`). Also applies to Python, git dependencies, Yarn/pnpm.

---

## 8. Distribution

### Own public GitHub marketplace in the same repo (source: `plugins/publish` → "Publish through your own marketplace", `plugins/host-marketplace`, `plugins/install`)

- Repo layout: `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` (entry `"source": "./"`). One repo can be both.
- Anyone with a public repo can let others install it without a submission. The docs do not require approval.
- User commands (docs pattern, replace the placeholders):
  - `/plugin marketplace add <user>/omni-agent` (or `claude plugin marketplace add <user>/omni-agent`)
  - `/plugin install omni-agent@<marketplace-name>`. Claude Code reads the marketplace name from `marketplace.json`, NOT from the repo name. If both are called `omni-agent`: `omni-agent@omni-agent`.
  - Or in one step: `/plugin install omni-agent --marketplace <user>/omni-agent` (from 2.1.275).
  - Pin to a branch or tag: `<user>/omni-agent#v0.1.0`.
- The request "give the repo URL to Claude": the docs describe installation by the user through a command. Whether Claude installs on its own from a bare URL is not documented.
- Versioning: Either maintain `version` in `plugin.json` and raise it on every release, or leave it out (then the commit SHA counts). Docs: "Don't set version in both".
- Release tag: `claude plugin tag --push` creates `omni-agent--v<version>` (only needed if other plugins set version ranges against it).

### Team setup (source: `plugins/loading` → "Plugins shared through a repository"; `plugins/install`)

- In `.claude/settings.json` (commit it): `extraKnownMarketplaces` (source of the marketplace) and `enabledPlugins` (`"omni-agent@omni-agent": true`).
- Caution: A plugin with an external source is NOT installed automatically for colleagues if only the project enables it. `/plugin` then reports "enabled in project settings but isn't installed". Fix per the docs: each colleague runs `claude plugin install omni-agent@omni-agent --scope project`. Exception: relative path sources or seed directories.
- Cloud sessions (claude.ai/code) do NOT load locally installed plugins (`plugins/install`).

### Private repos (source: `plugins/host-marketplace` → "Grant access to a private marketplace")

- No token field in `marketplace.json`. Claude Code uses the machine's git credentials, without prompting.
- SSH: key without a passphrase prompt (ssh-agent), host in `known_hosts`.
- HTTPS: a credential helper stores the access (`gh auth login` + `gh auth setup-git`).
- For the `owner/repo` shorthand, Claude Code tries SSH first. With `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1` it always uses HTTPS.

### Anthropic directory (source: `plugins/publish` → "Submit to Anthropic's directory")

- Submission through `claude.ai/directory/manage`. Prerequisite per the docs: a paid claude.ai plan (Pro/Max own account; Team/Enterprise: owner).
- The official marketplace `claude-plugins-official` does not take submissions through the portal; contact an Anthropic partner contact for that.
- After approval: users with a claude.ai account get the plugin, Claude Code loads it as `<name>@synced`.
- Review and deadlines: not documented (points to claude.com pages, not read).

### Naming rules (source: `plugins/manifest-reference` → `name`; `plugins/marketplace-reference` → Reserved names)

- A plugin name must not start with `claude-`, `anthropic-`, `anthropics-`, `cc-plugin-` (error). Also not `claude`, `anthropic`, `claude-code`, `claude-mods`. `omni-agent` is allowed.
- Reserved marketplace names include: `inline`, `builtin`, `skills-dir`, `synced`, `npm`, `pip`, `uv`, `cargo`, `github`, `gh`, `claude-plugin-test`, and all official Anthropic names.

---

## 9. Security (source: `plugins/security`, `hooks`, `plugins/org`)

- A plugin runs code with the user's permissions (docs wording, paraphrased). Hooks, monitors, MCP servers, LSP servers and mod processes run OUTSIDE the sandbox.
- Commands from `bin/` that Claude starts through the Bash tool are tool calls and are subject to the permission rules.
- Skills, agents and commands act as instructions to Claude (prompt level), not as code.
- Trust warning on installation (wording): "Make sure you trust a plugin before installing, updating, or using it. Anthropic does not control what MCP servers, files, or other software are included in plugins...". Organizations can append `pluginTrustMessage`.
- Check before installing: `/plugin` → Details → "Will install". Otherwise read the files: `hooks/hooks.json`, `.mcp.json`, `bin/`. Also `claude --plugin-dir <folder> plugin details <name>`.
- Auto-update can change the files you reviewed (docs warning in `plugins/security`).
- Project plugins from the repo: load only after the folder trust check; MCP servers need individual approval; background monitors do not load; MCP bundles from the repo are skipped.
- Admin control (managed settings): `strictKnownMarketplaces`, `blockedMarketplaces`, `allowManagedHooksOnly`, `disableCommandPluginSources`, `strictPluginOnlyCustomization`, disabling `--plugin-dir`/`CLAUDE_CODE_PLUGIN_DIRS`, `syncClaudeAiPlugins`.
- Hooks (source: `hooks`): Exit 2 blocks, stderr is shown as the reason. Other exit codes let the action proceed. Default is "fail-open"; `"onFailure": "block"` (from 2.1.295) changes that. The `if` filter is "best-effort". Use permissions for hard rules.
- Secrets: Sensitive values via `userConfig` with `sensitive: true`. Never in plain text in `.mcp.json` or scripts. For `headersHelper`, Claude Code strips credential-like environment variables (source: `plugins/host-marketplace`).
- Uninstalling from the last scope deletes stored options, secrets and the data folder (source: `plugins/cli-reference`, exception `--keep-data`).

---

## 10. Pitfalls and limits

| # | Pitfall | Source / status |
|---|---|---|
| 1 | Components inside `.claude-plugin/` do not load (only `plugin.json` belongs there) | `plugins/create` |
| 2 | Paths without `./` are rejected; `..` forbidden; backslash forbidden on macOS/Linux | `plugins/manifest-reference` |
| 3 | `CLAUDE.md` in the plugin root is not loaded. Put instructions in a skill | `plugins/components` |
| 4 | Marketplace plugins are copied. Files outside the plugin folder are missing in the cache | `plugins/loading` |
| 5 | `version` set + new commits without a bump = users get nothing | `plugins/loading` |
| 6 | Plugin name and entry name differ = "Plugin not found" | `plugins/marketplace-reference` |
| 7 | Hooks as a file path in a marketplace `plugins[]` entry: never run; inline object only | `plugins/marketplace-reference` |
| 8 | `settings.json` in the plugin: only `agent` and `subagentStatusLine` | `plugins/components` |
| 9 | `hooks`/`mcpServers`/`permissionMode` in agent frontmatter are ignored | `plugins/components` |
| 10 | `${CLAUDE_PLUGIN_ROOT}` in shell-form hooks: put it in quotes; otherwise `validate` warns | `plugins/manifest-reference` |
| 11 | `${CLAUDE_PLUGIN_ROOT}` is NOT in the environment of Bash tool commands. `bin/` scripts: derive the path from `$0` (our own recommendation) | `plugins/manifest-reference` |
| 12 | Sensitive `userConfig` values do NOT appear in skill or agent text (placeholder). They must go in MCP `env` or hook `args` | `plugins/manifest-reference` |
| 13 | Shell-form hooks, monitors and `headersHelper` do not accept `${user_config.*}` | `plugins/manifest-reference` |
| 14 | Monitors do not start with `-p`; no `${user_config.*}`; keep running after deactivation until the session ends | `plugins/components` |
| 15 | Node dependencies only with a lockfile (npm/bun); Yarn/pnpm lockfile = no installation; no lifecycle scripts; 60 s | `plugins/loading` |
| 16 | With `--plugin-dir` the userConfig dialog does not appear; use `/plugin configure` | `plugins/components` |
| 17 | `claude plugin install` does not ask for userConfig values (`--config` or `configure --values-stdin`) | `plugins/components` |
| 18 | Hooks run from session start, not only when a skill is invoked; keep matchers narrow | `plugins/components` |
| 19 | Hooks with the same plugin name from two marketplaces: one is not executed | `plugins/loading` |
| 20 | `validate --strict` fails on a missing `version`/`description`/`author` | `plugins/manifest-reference` |
| 21 | Windows: shell-form hooks run through Git Bash, otherwise PowerShell. Exec form needs a real `.exe`; call `.cmd` shims through `node <script>` | `hooks`, `plugins/manifest-reference` |
| 22 | Windows: `${CLAUDE_PLUGIN_ROOT}` with forward slashes (`C:/...`) in Git Bash hooks | `plugins/troubleshooting` |
| 23 | Execute permission for `bin/`: the docs example uses `chmod +x`; not explicitly verified as required. Some plugins in the local marketplace have mode 644 (e.g. `code-modernization/scripts/telemetry.sh`) but run through `sh …`. Safe: call scripts with `sh "${CLAUDE_PLUGIN_ROOT}/…"` or set `chmod +x` | checked locally |
| 24 | Changes to hooks/MCP after an update: old path until `/reload-plugins`; monitors only with a restart | `plugins/loading` |
| 25 | Cloud sessions do not load locally installed plugins | `plugins/install` |
| 26 | Paths outside the plugin folder (e.g. `../shared`) are missing after copying into the cache | `plugins/loading` |
| 27 | A dependency on `@synced` plugins is satisfied via claude.ai only if the plugin is also loaded there | `plugins/dependencies` |
| 28 | Files stored with Git LFS are not fetched on clone (pointer files) | `plugins/host-marketplace` |
| 29 | Private marketplaces: background auto-update works only with stored credentials | `plugins/host-marketplace` |

Limits (not capabilities of plugins): There is no plugin counterpart to Managed Agents; background processes come through MCP servers, monitors, `bin/` commands or subagents with the `background` field. Whether that is enough for background agents with third-party models is a design question that the docs do not answer (not documented).

---

## 11. Minimal working examples

### 11.1 plugin.json (with userConfig and a secret)
```json
{
  "name": "omni-agent",
  "version": "0.1.0",
  "description": "Starts background agents with third-party models",
  "author": { "name": "Alex" },
  "repository": "https://github.com/<user>/omni-agent",
  "license": "MIT",
  "userConfig": {
    "eurouter_api_key": {
      "type": "string",
      "title": "EUrouter API key",
      "description": "Key for the model gateway",
      "sensitive": true,
      "required": true
    },
    "default_model": {
      "type": "string",
      "title": "Default model",
      "description": "Model for new agents",
      "default": "auto"
    }
  }
}
```

### 11.2 marketplace.json (the repo is also the marketplace)
```json
{
  "name": "omni-agent",
  "owner": { "name": "Alex", "url": "https://github.com/<user>" },
  "description": "Marketplace for the Omni-Agent plugin",
  "plugins": [
    {
      "name": "omni-agent",
      "source": "./",
      "description": "Background agents with third-party models"
    }
  ]
}
```
Location: `.claude-plugin/marketplace.json`. User: `/plugin marketplace add <user>/omni-agent`, then `/plugin install omni-agent@omni-agent`.

### 11.3 Slash command with arguments (skill)
`skills/agent-start/SKILL.md`:
```markdown
---
description: Starts a background agent with a third-party model
argument-hint: "[task]"
disable-model-invocation: true
allowed-tools: Bash(omni-agent *)
---
Start a background agent for the task: $ARGUMENTS

Run `omni-agent start "$ARGUMENTS"` and then report the job ID.
```
Invocation: `/omni-agent:agent-start Research on tariffs`. `$ARGUMENTS` is the rest of the input; `$0` would be the first word.

### 11.4 Skill (loaded automatically)
`skills/model-selection/SKILL.md`:
```markdown
---
description: Chooses the third-party model for a background task. Use when the user names a model for an agent or asks a cost/quality question about models.
---
Read the model list with `omni-agent models` and pick the cheapest model that meets the task according to the user's requirements. Name the model and the reason in one sentence.
```
Without `disable-model-invocation`, Claude may load the skill itself.

### 11.5 Hook (exec form, with a path variable)
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
Exit 2 in the script blocks, stderr is the reason. Exec form (with `args`) needs no quotes.

### 11.6 bin/ command (path from $0, because the ROOT variable is missing in the Bash tool)
`bin/omni-agent` (`chmod +x`, or call it through `sh` in scripts):
```bash
#!/bin/sh
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
case "${1:-}" in
  start) shift; exec node "$ROOT/dist/cli.js" start "$@" ;;
  status) exec node "$ROOT/dist/cli.js" status ;;
  *) echo "Usage: omni-agent start|status ..." >&2; exit 2 ;;
esac
```

### 11.7 MCP server with a secret from userConfig
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
Tools are named `mcp__plugin_omni-agent_omni-agent__<tool>`. The server appears in `/mcp` as `plugin:omni-agent:omni-agent`.

---

## 12. Consequences for Omni-Agent (derived from the docs)

1. Repo with `.claude-plugin/plugin.json` (name `omni-agent`) and `.claude-plugin/marketplace.json` (source `./`) in the root.
2. API keys only through `userConfig` with `sensitive: true`, and only used in MCP `env` or hook `args`. Not in skill text.
3. Background agents as an MCP server or as a `bin/` command with its own data folder in `${CLAUDE_PLUGIN_DATA}` (state, logs, job list). Do not write to `${CLAUDE_PLUGIN_ROOT}`.
4. Maintain the version deliberately. Without `version`, users follow the commit.
5. Install path for users: `/plugin marketplace add <user>/omni-agent`, then `/plugin install omni-agent@omni-agent`. Short form with `--marketplace`.
6. Before publishing: `claude plugin validate --strict ./`, then test locally with `claude --plugin-dir ./`.

---

## 13. not documented (not found in the docs or not read completely)

- Whether `sensitive` userConfig values are stored in the Keychain on macOS. The docs only say "platform's secure credential store".
- Whether Claude installs on its own from a bare repo URL in chat.
- Whether `bin/` files strictly need `chmod +x` (the docs example uses it, requirement not stated).
- Complete frontmatter and hook fields (hooks: docs read only up to the section "Exit codes" and security; the page is very long; individual event inputs unchecked).
- Workflow format (`workflows/*.js`) and channels: mentioned only, no details.
- Review and approval deadlines of the Anthropic directory.
- Whether background agents with third-party models may run permanently through plugin mechanics (no docs statement; monitors and `background` are only partial answers).
- Whether `/plugin marketplace add` works with a bare repo name without an owner (the docs name only `owner/repo`).
- Windows behavior for `bin/` in the Bash tool: only a pointer to the PowerShell tool; no statement on execute permissions.
