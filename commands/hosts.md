---
description: Shows the remote targets (Mac mini, servers via ssh/Tailscale) on which Omni-Agent can execute runs with --host
argument-hint: '[test NAME]'
disable-model-invocation: true
allowed-tools: Bash(omni-agent:*)
---

!`omni-agent host $ARGUMENTS`

Pass the output on briefly. The user adds or installs targets in the terminal (`omni-agent host add NAME --ssh user@address`, `omni-agent host install NAME`); keys and logins are set up by the user on the target itself, never in chat. Without an argument the command shows the list (`list`); for `test NAME` it says what is missing on the target. `default NAME` makes a host the target of `run`, `review`, `status` and the like (`--host local` runs here again). Projects and files travel to the host as a copy; `/omni-agent:apply` fetches the changes back.
