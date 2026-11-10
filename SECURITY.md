# Security

## Reporting a vulnerability

Please do **not** open a public issue. Use [Private Vulnerability Reporting](https://github.com/alexodexo/omni-agent/security/advisories/new) on GitHub. You will get a reply as soon as possible.

## What Omni-Agent protects

- Every run starts in a clean environment and gets only the one key it needs.
- Keys live in `~/.omni-agent/env` (mode 600) and are redacted in logs. Omni-Agent refuses the file if others can read it.
- No shell by default. In project mode, agents only read unless you set `--write`.
- Review sends nothing if the diff contains possible secrets or `.env` files.

The full list is in the [Security section of the README](README.md#security).

## What is not protected

Everything you write in a task goes to the chosen provider. `omni-agent providers` shows the data location.
