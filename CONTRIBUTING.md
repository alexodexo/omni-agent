# Contributing

Glad you want to help. The core is the Python standard library with no dependencies, and that should stay so.

## Getting started

```bash
git clone https://github.com/alexodexo/omni-agent && cd omni-agent
python3 -m unittest discover -s tests -v     # No test talks to a real provider
claude plugin validate --strict .            # plugin and marketplace
claude --plugin-dir .                        # load the plugin locally, /reload-plugins after changes
```

## Rules

1. **New flags go into the parser first** (`lib/omni_agent/cli.py`); only then document them in `commands/`, `agents/` or `skills/`. A test checks every documented command against the real parser.
2. **Write tests along with the code.** New behaviour gets a test that runs without network and without a real provider (a stand-in instead of the real `claude`).
3. **Keep the version equal** in `lib/omni_agent/__init__.py` and `.claude-plugin/plugin.json`, and raise it if users should get the change. Otherwise they get no update. A test checks that they are equal.
4. **Mark honestly what has been verified.** `verified: true` in `providers.json` means: tried live, not only read in the docs.
5. **No keys, no personal paths** in code, tests, docs or commits.

## Adding a new provider

A JSON file following the schema of [providers.json](providers.json); to try it out, put it in `~/.omni-agent/providers.d/`. For inclusion in the repo: link the vendor documentation, state the data location and run the provider through once live.

More on the structure: [docs/02-architecture.md](docs/02-architecture.md) and [AGENTS.md](AGENTS.md).
