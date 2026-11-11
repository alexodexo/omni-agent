"""Remote hosts: run Omni-Agent on another machine (Mac mini, server, cloud VM) over SSH.

`--host NAME` forwards the command to `omni-agent` on the host. Keys, agent CLIs and runs live there. With
`--project` or `--files` the folder is copied there first (remote_project.py); changes come back with `apply`. Tailscale is nothing special: any name or address `ssh` can reach
(Tailscale IP, MagicDNS name, Tailscale SSH) works.

Only how to reach the host is stored (`hosts.json`), never a secret.
"""
from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
import sys

from .config import ConfigError, claude_session, home

NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")
DEFAULT_COMMAND = "omni-agent"
INSTALL_DIR = ".omni-agent-app"
REPO = "https://github.com/alexodexo/omni-agent"


def data_file():
    return home() / "hosts.json"


def load() -> dict:
    try:
        d = json.loads(data_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def save(doc: dict) -> None:
    home().mkdir(parents=True, exist_ok=True)
    data_file().write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def names_only() -> dict:
    return {k: v for k, v in load().items() if k != "_default"}


def check_name(name: str) -> str:
    if not NAME.match(name or ""):
        raise ConfigError("Host name: lowercase letters, digits and hyphen, e.g. mini")
    return name


def lookup(name: str) -> dict:
    entries = names_only()
    if name not in entries:
        existing = ", ".join(entries) or "none"
        raise ConfigError(f"Host '{name}' does not exist. Existing: {existing}. Add it: omni-agent host add {name} --ssh USER@ADDRESS")
    return entries[name]


def default_name() -> str | None:
    name = load().get("_default")
    return name if isinstance(name, str) and name in load() else None


def set_default(name: str | None) -> None:
    doc = load()
    if name is None:
        doc.pop("_default", None)
    else:
        if name not in doc:
            raise ConfigError(f"Host '{name}' does not exist")
        doc["_default"] = name
    save(doc)


def add_entry(name: str, ssh: str, command: str | None = None, overwrite: bool = False) -> None:
    check_name(name)
    if not ssh or ssh.startswith("-") or any(c.isspace() for c in ssh):
        raise ConfigError("--ssh expects a target like user@address (name, IP or Tailscale name), without spaces and without a leading hyphen")
    entries = load()
    if name in entries and not overwrite:
        raise ConfigError(f"Host '{name}' already exists. Overwrite: --replace")
    entries[name] = {"ssh": ssh, "command": command or DEFAULT_COMMAND}
    save(entries)


def remove_entry(name: str) -> None:
    entries = load()
    if name not in entries:
        raise ConfigError(f"Host '{name}' does not exist")
    del entries[name]
    if entries.get("_default") == name:
        del entries["_default"]
    save(entries)


def ssh_argv(entry: dict, remote: str, tty: bool = False) -> list:
    exe = shutil.which("ssh")
    if not exe:
        raise ConfigError("ssh is not installed (command 'ssh' not on PATH)")
    return [
        exe, "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=30",
        *(["-t"] if tty else []), "--", entry["ssh"], remote,
    ]


def remote_command(entry: dict, argv: list) -> str:
    """The line that runs on the host. The Claude session goes along so status/result there mean the same session."""
    lead = "OMNI_AGENT_ON_HOST=1 "  # the host must not forward again to a default host of its own
    if claude_session():
        lead += f"OMNI_AGENT_SESSION={shlex.quote(claude_session())} "
    command = entry.get("command") or DEFAULT_COMMAND
    # The command may start with ~ or $HOME (path to the script); the arguments are always quoted.
    return lead + command + " " + " ".join(shlex.quote(a) for a in argv)


def without_host(argv: list) -> list:
    """Removes --host NAME / --host=NAME from the argument list."""
    out, i = [], 0
    while i < len(argv):
        if argv[i] == "--host":
            i += 2
            continue
        if argv[i].startswith("--host="):
            i += 1
            continue
        out.append(argv[i])
        i += 1
    return out


def forward(name: str, argv: list, args=None) -> int:
    """Runs `omni-agent <argv>` on the host; output and exit code come back unchanged."""
    entry = lookup(name)
    argv = without_host(argv)
    command = getattr(args, "command", "") if args is not None else ""
    if command == "run":
        from . import remote_project
        # Project or files: copy them to the host first and point the command at the copy there
        argv = remote_project.rewrite_run_argv(name, argv, args)
        # The task file is local: send its content as --text
        if getattr(args, "task", None):
            from pathlib import Path
            source = Path(args.task).expanduser()
            if source.is_file() and args.task in argv:
                argv.remove(args.task)
                argv += ["--text", source.read_text(encoding="utf-8")]
    running = subprocess.run(ssh_argv(entry, remote_command(entry, argv)))
    if command == "run" and running.returncode != 255 and getattr(args, "project", None) is not None and getattr(args, "writable", False):
        print(f"The agent worked on a copy on '{name}'. Look at its changes: omni-agent apply --host {name}   (add --yes to write them into your project)")
    if running.returncode == 255:
        print(f"Error: ssh to '{name}' ({entry['ssh']}) failed. Reachable? Key installed (BatchMode, no password prompt)? Check: omni-agent host test {name}", file=sys.stderr)
    return running.returncode


def test_target(name: str) -> tuple:
    """(ok, text). Runs `omni-agent doctor` on the host and says what is missing."""
    entry = lookup(name)
    try:
        res = subprocess.run(
            ssh_argv(entry, (entry.get("command") or DEFAULT_COMMAND) + " doctor"),
            capture_output=True, text=True, timeout=60,
        )
    except subprocess.TimeoutExpired:
        return False, "Timed out while connecting"
    if res.returncode == 255:
        return False, "ssh failed: " + (res.stderr.strip().splitlines() or ["no message"])[-1]
    if res.returncode == 127 or "not found" in res.stderr or "nicht gefunden" in res.stderr:
        return False, "Connection works, but '" + (entry.get("command") or DEFAULT_COMMAND) + f"' does not exist there. Install it: omni-agent host install {name}"
    if res.returncode != 0:
        return False, (res.stderr.strip() or res.stdout.strip() or f"exit code {res.returncode}")[:400]
    return True, res.stdout


def install_on_target(name: str) -> str:
    """Fetches Omni-Agent onto the host with git (~/.omni-agent-app) and stores the path as its command.

    Keys and logins are set up there by hand (omni-agent setup via ssh). Nothing is transferred."""
    entry = lookup(name)
    script = (
        "set -e; command -v git >/dev/null || { echo 'git is missing on the host' >&2; exit 3; }; "
        "command -v python3 >/dev/null || { echo 'python3 is missing on the host' >&2; exit 3; }; "
        f"python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 4)' || {{ echo 'Python 3.9 or newer required' >&2; exit 4; }}; "
        f"if [ -d \"$HOME/{INSTALL_DIR}/.git\" ]; then git -C \"$HOME/{INSTALL_DIR}\" pull --ff-only -q; "
        f"else git clone --depth 1 -q {shlex.quote(REPO)} \"$HOME/{INSTALL_DIR}\"; fi; "
        f"echo \"$HOME/{INSTALL_DIR}/bin/omni-agent\""
    )
    res = subprocess.run(ssh_argv(entry, script), capture_output=True, text=True, timeout=180)
    if res.returncode != 0:
        raise ConfigError("Installation on the host failed: " + (res.stderr.strip().splitlines() or [f"exit code {res.returncode}"])[-1])
    file_path = (res.stdout.strip().splitlines() or [""])[-1]
    if not file_path.endswith("/bin/omni-agent"):
        raise ConfigError("Installation on the host returned no path")
    entries = load()
    entries[name]["command"] = shlex.quote(file_path)
    save(entries)
    return file_path
