"""Command line: omni-agent setup | doctor | run | status | providers | runners | extras."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from . import VERSION, extras
from .providers import load_providers
from .config import (
    EXIT_CONFIG, ConfigError, ROOT, claude_session, review_gate_an, set_config, set_default_provider, default_provider,
    env_file, get_key, home, read_key_file, check_reachable,
)
from .engine import (
    all_runs, duration_text, print_report, find_run, execute, runs_in_view, read_status, check_alive,
    start_detached, wait_and_report,
)
from .runner import RUNNER, fits

SHIM_MARKER = "omni-agent-shim"
SHIM = """#!/usr/bin/env python3
# omni-agent-shim: finds the installed plugin version, even after updates (the call never changes)
import glob, json, os, sys
home = os.path.expanduser("~")
ziel = None
try:
    with open(os.path.join(home, ".claude", "plugins", "installed_plugins.json"), encoding="utf-8") as f:
        for eintrag in json.load(f).get("plugins", {}).get("omni-agent@omni-agent", []):
            kandidat = os.path.join(eintrag["installPath"], "bin", "omni-agent")
            if os.path.isfile(kandidat):
                ziel = kandidat
except (OSError, ValueError, KeyError, TypeError):
    pass
if ziel is None:
    treffer = glob.glob(os.path.join(home, ".claude", "plugins", "cache", "omni-agent", "omni-agent", "*", "bin", "omni-agent"))
    ziel = max(treffer, key=os.path.getmtime) if treffer else None
if ziel is None:
    sys.exit("omni-agent: plugin not found. Install it with: claude plugin install omni-agent@omni-agent")
os.execv(sys.executable, [sys.executable, ziel] + sys.argv[1:])
"""

ENV_TEMPLATE = """# Omni-Agent: keys. One line per provider, format NAME=value, no quotes needed.
# This file stays on your machine (mode 600). Never commit it, never paste it into a chat.
# Alternatively set the variable in the shell (export NAME=value); the environment takes precedence.
#
# DEEPSEEK_API_KEY=
# OPENROUTER_API_KEY=
# MOONSHOT_API_KEY=
# EUROUTER_API_KEY=
# NVIDIA_API_KEY=
# ANTHROPIC_API_KEY=            # Claude with another account (recommended: API key)
# CLAUDE_CODE_OAUTH_TOKEN=      # Subscription token: terms for unattended runs are not documented
# Ollama (local) needs no key.
"""

# ---------- doctor ----------

def _login_status(provider) -> str:
    """Login state of the agent CLI (e.g. `codex login status`). No secret is read or shown."""
    runner = RUNNER.get(provider.runner_only or "")
    exe = runner.file_path() if runner else None
    if not exe:
        return "CLI missing"
    try:
        res = subprocess.run([exe, "login", "status"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return "logged in" if res.returncode == 0 and "logged in" in (res.stdout + res.stderr).lower() else "NOT logged in"


def cmd_doctor(args) -> int:
    ok = True
    print(f"Omni-Agent {VERSION}, Python {sys.version_info.major}.{sys.version_info.minor}, folder {home()}")
    file_path = env_file()
    if file_path.exists():
        too_open = bool(file_path.stat().st_mode & 0o077)
        print(f"Key file: {file_path} ({'PERMISSIONS TOO OPEN, chmod 600' if too_open else 'permissions ok'})")
        ok = ok and not too_open
    else:
        print(f"Key file: missing ({file_path}). Create it with: omni-agent setup")
    try:
        data_file = read_key_file()
    except ConfigError as exc:
        print(f"  {exc}")
        data_file, ok = {}, False

    print("\nRunners (agent CLIs):")
    for r in RUNNER.values():
        v = r.version()
        marker = "EXPERIMENTAL, " if r.experimental else ""
        print(f"  {r.name:<9} {'installed ' + str(v) if v else 'not installed':<42} {marker}speaks {', '.join(r.protocols)}")
    if not any(r.file_path() for r in RUNNER.values() if not r.experimental):
        print("  -> Install at least one agent CLI (default: Claude Code).")
        ok = False

    print("\nProviders:")
    provider = load_providers()
    print(f"  {'Provider':<16}{'Key':<13}{'Region':<20}{'Verified':<9}Matching runners")
    for a in provider.values():
        if a.account_kind == "login":
            key = _login_status(a)
        elif not a.needs_key:
            key = "not needed"
        else:
            key = "set" if any(get_key(n, data_file) for n in a.key_envs) else "missing"
        matching = [n for n, r in RUNNER.items() if fits(a, r)]
        via = [n for n, r in RUNNER.items() if fits(a, r, True) and n not in matching]
        line = ", ".join(matching) or "-"
        if via:
            line += f"  (+ {', '.join(via)} via LiteLLM)"
        installed = [n for n in matching if RUNNER[n].file_path()]
        line += "" if installed else "   [none of them installed]"
        print(f"  {a.id:<16}{key:<13}{a.region:<20}{'yes' if a.verified else 'no':<9}{line}")
        if args.network and a.base_url and (key != "missing"):
            try:
                check_reachable(a.base_url, 4)
                print(f"      Endpoint reachable: {a.base_url}")
            except ConfigError as exc:
                print(f"      Endpoint NOT reachable: {exc}")
    print(f"\nReview gate: {'ON' if review_gate_an() else 'off'} | Default provider: {default_provider() or 'none'} | Claude session: {claude_session() or 'not detected (the hook only runs inside Claude Code)'}")
    print(f"\n{extras.status_text()}")
    print("\nNote: 'Verified: no' means built from the vendor docs, not tried live. Data location per provider: omni-agent providers")
    return 0 if ok else EXIT_CONFIG


# ---------- setup ----------

def cmd_setup(args) -> int:
    head_text = home()
    head_text.mkdir(parents=True, exist_ok=True)
    os.chmod(head_text, 0o700)
    data_file = env_file()
    if not data_file.exists():
        fd = os.open(data_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(ENV_TEMPLATE)
        print(f"Key file created: {data_file} (mode 600)")
    else:
        os.chmod(data_file, 0o600)
        print(f"Key file exists: {data_file}")

    bin_target = Path.home() / ".local" / "bin"
    link = bin_target / "omni-agent"
    existing = shutil.which("omni-agent")
    our_file = link.is_symlink() or (link.is_file() and SHIM_MARKER in link.read_text(encoding="utf-8", errors="ignore"))
    if our_file or not existing:
        try:
            bin_target.mkdir(parents=True, exist_ok=True)
            if link.is_symlink() or link.exists():
                link.unlink()
            link.write_text(SHIM, encoding="utf-8")
            os.chmod(link, 0o755)
            print(f"Command installed: {link} (follows the installed plugin version automatically)")
            if str(bin_target) not in os.environ.get("PATH", "").split(os.pathsep):
                print(f"Note: {bin_target} is not in PATH. Add to your shell config: export PATH=\"$HOME/.local/bin:$PATH\"")
        except OSError as exc:
            print(f"Could not install the command ({exc}). Call it directly: {ROOT / 'bin' / 'omni-agent'}")
    else:
        print(f"Command 'omni-agent' is on PATH: {existing}")

    if args.provider:
        a = load_providers().get(args.provider)
        if not a:
            raise ConfigError(f"Unknown provider '{args.provider}'")
        print(f"\nProvider {a.name} ({a.id})")
        if a.needs_key:
            print(f"  1. Open {data_file} in your editor (not in the chat).")
            print(f"  2. Add a line:  {a.key_envs[0]}=your-key")
            print("  3. Check: omni-agent doctor")
        else:
            print("  No key needed. Is the service running? Check: omni-agent doctor --network")
        print(f"  Data location: {a.region}. {a.note}")
    else:
        print("\nNext steps:\n  1. Pick a provider (omni-agent providers) and add its key to the file: omni-agent setup --provider deepseek")
        print("  2. Check: omni-agent doctor")
        print("  3. First run: omni-agent run --text \"Summarize in three sentences what a background agent is\" --provider deepseek")
    if args.review_gate == "on":
        if not default_provider():
            raise ConfigError("The review gate needs a provider: first set one with `omni-agent account default NAME`.")
        set_config("review_gate", True)
        print(f"Review gate ON: before a Claude session ends, every new diff of unreviewed changes is sent to {default_provider()} "
              "(mind cost and data leaving your machine). Off: omni-agent setup --review-gate off")
    elif args.review_gate == "off":
        set_config("review_gate", None)
        print("Review gate OFF.")
    if args.open_flag:
        os.system(f"open -t {data_file}" if sys.platform == "darwin" else f"${{EDITOR:-nano}} {data_file}")
    print()
    return cmd_doctor(argparse.Namespace(network=False))


# ---------- run ----------

def cmd_run(args) -> int:
    if args.account and args.provider:
        raise ConfigError("--account and --provider are mutually exclusive.")
    if args.account:
        from .accounts import account_id
        args.provider = account_id(args.account)
    if not args.provider and args.resume is None:
        args.provider = default_provider()
        if not args.provider:
            raise ConfigError(
                "No provider given and no default set. Either pass --provider/--account "
                "or set a default: omni-agent account default NAME"
            )
        print(f"No provider given, default: {args.provider}")
    if args.resume is not None and args.text is None and not args.task:
        raise ConfigError("--resume needs the follow-up: --text \"...\"")
    if args.background or args.wait_seconds is not None:
        return start_detached(_without_flags(args._argv), args.wait_seconds)
    return execute(args)


def _without_flags(argv: list) -> list:
    """The command's arguments without --background/--wait (for the detached child process)."""
    out, i = [], 0
    while i < len(argv):
        a = argv[i]
        if a == "--background":
            i += 1
        elif a == "--wait":
            i += 2
        elif a.startswith("--wait="):
            i += 1
        else:
            out.append(a)
            i += 1
    return out


# ---------- review / cancel / result ----------

def cmd_review(args) -> int:
    from .review import run_review
    if args.account and args.provider:
        raise ConfigError("--account and --provider are mutually exclusive.")
    if args.account:
        from .accounts import account_id
        args.provider = account_id(args.account)
    if not args.provider:
        args.provider = default_provider()
        if not args.provider:
            raise ConfigError("No provider given and no default set (--account/--provider or: omni-agent account default NAME)")
        print(f"No provider given, default: {args.provider}")
    if (args.background or args.wait_seconds is not None) and not args.preview:
        return start_detached(_without_flags(args._argv), args.wait_seconds)
    return run_review(args)


def cmd_cancel(args) -> int:
    if args.run_name:
        folder = find_run(args.run_name)
    else:
        active = [p for p in runs_in_view() if (read_status(p) or {}).get("state") == "running"]
        if not active:
            print("No run is active.")
            return 0
        folder = active[0]
    was_running = (read_status(folder) or {}).get("state") == "running"
    status = check_alive(folder)
    if status.get("state") != "running":
        if was_running:
            print(f"{folder.name}: process was already gone, state set to 'failed'.")
        else:
            print(f"{folder.name}: not running ({status.get('state', 'unknown')}).")
        return 0
    os.kill(int(status["pid"]), signal.SIGTERM)
    for _ in range(40):
        time.sleep(0.5)
        if (read_status(folder) or {}).get("state") != "running":
            print(f"{folder.name}: cancelled.")
            return 0
    print(f"{folder.name}: cancel requested, the run is still shutting down.")
    return 0


def cmd_result(args) -> int:
    if args.run_name:
        folder = find_run(args.run_name)
    else:
        with_report = [p for p in runs_in_view() if (p / "report.md").is_file()]
        if not with_report:
            raise ConfigError("No run with a report yet. Runs: omni-agent status")
        folder = with_report[0]
    report = folder / "report.md"
    status = check_alive(folder)
    if not report.is_file():
        raise ConfigError(f"{folder.name}: no report ({status.get('state', 'unknown')}). See: omni-agent status {folder.name}")
    if args.file_path:
        print(report)
        return 0
    if status.get("state") == "running":
        print("[still running] This is an interim report.\n")
    print_report(folder, status)
    return 0


def cmd_wait(args) -> int:
    """Waits for a run (at most --max seconds) and reports its state; for forwarders that start runs detached."""
    return wait_and_report(find_run(args.run_name), args.max)


def cmd_resumable(args) -> int:
    """Is there a run of this Claude session that a follow-up could go to? (For the "resume or start new" question.)"""
    session = claude_session()
    candidates = all_runs(session) if session else []
    for folder in candidates:
        status = check_alive(folder)
        if status.get("session") and status.get("state") in ("done", "failed", "cancelled") and status.get("kind", "run") == "run":
            response = {"available": True, "run": folder.name, "provider": status.get("provider"), "model": status.get("model"),
                       "state": status.get("state"), "task": status.get("task")}
            break
    else:
        response = {"available": False}
    print(json.dumps(response, ensure_ascii=False))
    return 0


# ---------- status ----------

def _line(folder: Path) -> dict:
    s = check_alive(folder)
    return {"run": folder.name, "state": s.get("state", "unknown"), "kind": s.get("kind", "run"), "provider": s.get("provider"),
            "model": s.get("model"), "turns": s.get("turns"), "duration": duration_text(s), "task": s.get("task") or "",
            "resumable": bool(s.get("session")), "project": s.get("project")}


STATUS_LABELS = (("state", "State"), ("kind", "Kind"), ("provider", "Provider"), ("model", "Model"), ("runner", "Runner"),
                 ("turns", "Turns"), ("exitcode", "Exit code"), ("remark", "Note"), ("project", "Project"), ("task", "Task"))


def cmd_status(args) -> int:
    if args.run_name:
        folder = find_run(args.run_name)
        status = check_alive(folder) or {"state": "unknown"}
        report = folder / "report.md"
        if args.json:
            print(json.dumps({**status, "folder": str(folder), "report": str(report) if report.exists() else None}, ensure_ascii=False))
        else:
            print(f"{'Run:':<12}{folder}")
            for k, label in STATUS_LABELS:
                if status.get(k) is not None:
                    print(f"{label + ':':<12}{status[k]}")
            print(f"{'Duration:':<12}{duration_text(status)}")
            print(f"{'Report:':<12}{report if report.exists() else 'not there yet'}")
            if status.get("session"):
                print("Resumable: yes (omni-agent run --resume RUN --text \"follow-up\")")
            if status.get("state") == "running":
                print("Cancel: omni-agent cancel " + folder.name)
        return 0
    session = claude_session()
    source = all_runs() if args.show_all or not session else (all_runs(session) or all_runs())
    lines = [_line(p) for p in source[: args.limit]]
    if args.json:
        print(json.dumps(lines, ensure_ascii=False))
        return 0
    if not lines:
        print("No runs yet.")
        return 0
    if args.md:
        print("| Run | State | Provider / Model | Duration | Task |\n|---|---|---|---|---|")
        for z in lines:
            task = z["task"][:70].replace("|", "/")
            print(f"| `{z['run']}` | {z['state']}{' (review)' if z['kind'] == 'review' else ' (gate)' if z['kind'] == 'gate' else ''} | "
                  f"{z['provider'] or '-'} / {z['model'] or '-'} | {z['duration'] or '-'} | {task} |")
        print("\nReport: `omni-agent result RUN` · Cancel: `omni-agent cancel RUN` · Follow-up: `omni-agent run --resume RUN --text \"...\"`")
        return 0
    for z in lines:
        print(f"{z['run']:<34}{z['state']:<12}{(z['provider'] or '-') + ' / ' + (z['model'] or '-'):<44}{z['duration']}")
    return 0


def cmd_hook(args) -> int:
    from .hooks import run_hook
    return run_hook(args.name)


# ---------- account ----------

def cmd_account(args) -> int:
    from . import accounts
    if args.operation == "default":
        if args.delete:
            set_default_provider(None)
            print("Default removed: nothing runs without --provider any more.")
        elif args.name:
            acc_id = accounts.account_id(args.name)
            if acc_id not in load_providers():
                raise ConfigError(f"Account '{args.name}' does not exist. Existing: omni-agent account list")
            set_default_provider(acc_id)
            print(f"Default is now {acc_id}: `omni-agent run ...` without --provider uses this account.")
        else:
            print(f"Default: {default_provider() or 'none set'}")
        return 0
    if args.operation == "list":
        show_all = accounts.list_items()
        if not show_all:
            print("No named account yet. Add one: omni-agent account add NAME --kind api|token")
            return 0
        for k in show_all:
            std = "  [DEFAULT]" if k["id"] == default_provider() else ""
            print(f"{k['name']:<12} --provider {k['id']:<18} {accounts.KINDS[k['kind']][1]}{std}")
            print(f"{'':<12} Key {k['key_values']} ({k['env']})")
            if not args.no_usage:
                print(f"{'':<12} Usage: {accounts.usage(k)}")
        if not args.no_usage:
            print("\nUsage = one one-token request per account to api.anthropic.com (Haiku); --no-usage skips it.")
        return 0
    if not args.name:
        raise ConfigError("Please give an account name, e.g.: omni-agent account add felipe --kind token")
    if args.operation == "remove":
        accounts.remove_entry(args.name, args.with_key)
        print(f"Account '{args.name}' removed." + (" Key line deleted." if args.with_key else f" The line {accounts.account_env(args.name)} in the key file stays (--with-key deletes it)."))
        return 0
    # add
    file_path = accounts.create(args.name, args.kind, args.title, args.overwrite)
    env = accounts.account_env(args.name)
    print(f"Account '{args.name}' created ({file_path.name}). Use it with: --provider {accounts.account_id(args.name)}")
    if args.adopt:
        accounts.rename_key(args.adopt, env)
        print(f"Key adopted from {args.adopt}, now stored as {env}.")
    elif sys.stdin.isatty():
        import getpass
        value = getpass.getpass(f"{accounts.KINDS[args.kind][1]} for '{args.name}' (input hidden, Enter skips): ").strip()
        if value:
            accounts.set_key(env, value)
            print(f"Key saved as {env} (mode 600).")
    if not any(k["name"] == args.name and k["key_values"] == "set" for k in accounts.list_items()):
        print(f"Key still missing. In your terminal (not in the chat) run again: omni-agent account add {args.name} --kind {args.kind} --replace")
        print(f"or add a line to {env_file()}:  {env}=your-key")
    if args.kind == "token":
        print("Note: " + accounts.TOKEN_NOTE)
    return 0


# ---------- remote hosts ----------

def cmd_host(args) -> int:
    from . import hosts
    if args.operation == "list":
        entries = hosts.load()
        if not entries:
            print("No host yet. Add one: omni-agent host add mini --ssh user@address   (a Tailscale name or IP works too)")
            return 0
        for name, e in entries.items():
            print(f"{name:<12} ssh {e['ssh']:<32} command: {e.get('command') or hosts.DEFAULT_COMMAND}")
        print("\nUse it: omni-agent run --host NAME ...  (also status, result, cancel, wait, usage, doctor)")
        return 0
    if not args.name:
        raise ConfigError("Please give a host name, e.g.: omni-agent host add mini --ssh user@address")
    if args.operation == "add":
        if not args.ssh:
            raise ConfigError("--ssh USER@ADDRESS is missing (name, IP or Tailscale name)")
        hosts.add_entry(args.name, args.ssh, args.command_path, args.overwrite)
        print(f"Host '{args.name}' added ({args.ssh}). Check it: omni-agent host test {args.name}")
        return 0
    if args.operation == "remove":
        hosts.remove_entry(args.name)
        print(f"Host '{args.name}' removed.")
        return 0
    if args.operation == "install":
        file_path = hosts.install_on_target(args.name)
        print(f"Omni-Agent is installed on '{args.name}' at {file_path}. Set up keys and logins there: omni-agent host setup {args.name}")
        return 0
    if args.operation == "setup":
        return hosts.forward(args.name, ["setup"])
    ok, text = hosts.test_target(args.name)
    print(text.rstrip() if ok else f"Host '{args.name}': {text}")
    return 0 if ok else EXIT_CONFIG


# ---------- usage ----------

def cmd_usage(args) -> int:
    """Usage and balance, as far as each provider exposes it. All queries run in parallel."""
    from concurrent.futures import ThreadPoolExecutor
    from . import accounts, usage
    selector = (args.selector or "").lower()
    jobs = []  # (name, kind, function)
    for k in accounts.list_items():
        if selector in ("", "accounts", "claude", k["name"], k["id"]):
            jobs.append((k["id"], "Claude account", lambda k=k: accounts.usage(k)))
    if selector in ("", "codex") and RUNNER["codex"].file_path():
        jobs.append(("codex", "Codex CLI login", usage.codex_usage))
    data_file = read_key_file()
    for a in load_providers().values():
        if a.account_kind or a.id.startswith("claude-") or (selector and selector != a.id) or (not selector and a.id not in usage.BALANCE_QUERIES):
            continue
        key_values = next((w for n in a.key_envs if (w := get_key(n, data_file))), None)
        if not key_values and not selector:
            continue  # without a key, report only on request; otherwise it is noise
        jobs.append((a.id, a.name, lambda a=a, s=key_values: usage.balance(a.id, s)))
    if not jobs:
        print("Nothing to show: no Claude account, no Codex, no provider with a key. Set up: omni-agent setup")
        return 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda t: t[2](), jobs))
    for (name, kind, _), text in zip(jobs, results):
        print(f"{name:<16} {kind}")
        print(f"{'':<16} {text}")
    print("\nSources: Claude accounts = rate-limit headers (one one-token request per account), Codex = `codex app-server`, "
          "other providers = their balance endpoint. Without such an endpoint nothing is shown.")
    return 0


# ---------- providers / runners ----------


def cmd_providers(args) -> int:
    for a in load_providers().values():
        print(f"{a.id}  ({a.name})")
        print(f"  Protocol: {', '.join(a.protocols)}   Address: {a.base_url or 'Claude Code default'}")
        models = ', '.join(f'{k}={v}' for k, v in a.models.items()) or 'choose with --model'
        print(f"  Key:      {' or '.join(a.key_envs) or 'none'}   Models: {models}")
        print(f"  Data location: {a.region}   Verified live: {'yes' if a.verified else 'no'}")
        print(f"  {a.note}\n")
    return 0


def cmd_runners(args) -> int:
    for r in RUNNER.values():
        v = r.version()
        print(f"{r.name}  {'installed ' + str(v) if v else 'not installed'}{'  [experimental]' if r.experimental else ''}")
        print(f"  speaks: {', '.join(r.protocols)}   controls: {', '.join(sorted(r.can))}")
        print(f"  {r.note}\n")
    return 0


# ---------- extras ----------

def cmd_extras(args) -> int:
    if args.operation == "install":
        extras.install(args.force)
    elif args.operation == "start":
        if not args.provider:
            raise ConfigError("Give a provider: omni-agent extras litellm start <provider> [--model M]")
        from .engine import find_key
        a = load_providers().get(args.provider)
        if not a:
            raise ConfigError(f"Unknown provider '{args.provider}'")
        key_values = next(iter(find_key(a).values()), "")
        address, _ = extras.start_proxy(a, a.pick_model(args.model), key_values)
        print(f"Proxy running on {address} (local only)")
    elif args.operation == "stop":
        print("Proxy stopped." if extras.stop_proxy() else "Proxy was not running.")
    else:
        print(extras.status_text())
    return 0


# ---------- parser ----------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="omni-agent",
        description="Background agents with a swappable provider (model source) and runner (agent CLI).",
    )
    p.add_argument("--version", action="version", version=f"omni-agent {VERSION}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("setup", help="Set up folder, key file and command, then check")
    s.add_argument("--provider", dest="provider", help="print instructions for this provider")
    s.add_argument("--open", dest="open_flag", action="store_true", help="open the key file in your editor")
    s.add_argument("--review-gate", choices=["on", "off"], help="turn the check before a Claude session ends on or off (default: off)")
    s.set_defaults(fn=cmd_setup)

    s = sub.add_parser("doctor", help="What is there, what is missing (runners, keys, fit)")
    s.add_argument("--network", dest="network", action="store_true", help="also check that the endpoints are reachable")
    s.set_defaults(fn=cmd_doctor)

    s = sub.add_parser("run", help="Run a task (blocking; Claude starts it in the background)")
    s.add_argument("task", nargs="?", metavar="task_file", help="task file (Markdown)")
    s.add_argument("--text", help="the task as text instead of a file")
    s.add_argument("--provider", dest="provider", help="see: omni-agent providers; without it the default applies (omni-agent account default)")
    s.add_argument("--account", dest="account", help="shorthand for --provider claude-<name>, e.g. --account felipe")
    s.add_argument("--model", dest="model", help="model name or tier (default, strong, small)")
    s.add_argument("--runner", help="claude, opencode, codex or dsh; without it the first matching installed one")
    s.add_argument("--tools", dest="tool_list", help="e.g. 'read,write', '+shell', '-web_search' (default: read,write,web_search,web_fetch)")
    s.add_argument("--max-turns", dest="max_turns", type=int, default=12, help="upper bound for tool calls per the task frame (default 12)")
    s.add_argument("--timeout", dest="time_limit", type=int, default=900, help="time limit in seconds (default 900)")
    s.add_argument("--dir", dest="folder", help="own, empty working folder instead of ~/.omni-agent/runs/...")
    s.add_argument("--files", dest="files", help="folder whose content is copied into the working folder before the start")
    s.add_argument("--via-litellm", dest="via_litellm", action="store_true", help="translate OpenAI providers for Claude Code through the LiteLLM extra")
    s.add_argument("--resume", dest="resume", nargs="?", const="", default=None, metavar="RUN", help="follow-up to an earlier run (without a name: the latest); --text is the follow-up")
    s.add_argument("--effort", dest="effort", choices=["minimal", "low", "medium", "high", "xhigh"], help="reasoning effort (Codex only)")
    s.add_argument("--project", dest="project", nargs="?", const="", default=None, metavar="DIR", help="work in the project folder (without a value: current directory), read-only (works with any provider, the decision is yours)")
    s.add_argument("--write", dest="writable", action="store_true", help="with --project: files in the project may be changed")
    s.add_argument("--background", dest="background", action="store_true", help="start as a detached process and report the run name immediately")
    s.add_argument("--wait", dest="wait_seconds", type=int, metavar="SEC", help="start detached and wait at most this long for the end (then reports state or report)")
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("review", help="Have another model review your git changes (the diff leaves your machine)")
    s.add_argument("focus", nargs="*", metavar="focus", help="focus as free text, e.g. permissions and data loss")
    s.add_argument("--base", help="review against this branch, e.g. main (without it: all changes against HEAD)")
    s.add_argument("--adversarial", action="store_true", help="also challenge the chosen approach")
    s.add_argument("--provider", dest="provider", help="see: omni-agent providers; without it the default")
    s.add_argument("--account", dest="account", help="shorthand for --provider claude-<name>")
    s.add_argument("--model", dest="model")
    s.add_argument("--runner")
    s.add_argument("--effort", dest="effort", choices=["minimal", "low", "medium", "high", "xhigh"], help="reasoning effort (Codex only)")
    s.add_argument("--max-turns", dest="max_turns", type=int, default=10)
    s.add_argument("--timeout", dest="time_limit", type=int, default=900)
    s.add_argument("--background", dest="background", action="store_true", help="start as a detached process and report the run name immediately")
    s.add_argument("--wait", dest="wait_seconds", type=int, metavar="SEC", help="start detached and wait at most this long for the end")
    s.add_argument("--preview", dest="preview", action="store_true", help="only show what would be sent; send nothing")
    s.add_argument("--force", dest="force", action="store_true", help="send even if the diff may contain secrets")
    s.set_defaults(fn=cmd_review)

    s = sub.add_parser("cancel", help="Cancel a running run (without a name: the active one)")
    s.add_argument("run_name", nargs="?", metavar="run")
    s.set_defaults(fn=cmd_cancel)

    s = sub.add_parser("result", help="Show the report of a run (without a name: the newest with a report)")
    s.add_argument("run_name", nargs="?", metavar="run")
    s.add_argument("--path", dest="file_path", action="store_true", help="print only the path to report.md")
    s.set_defaults(fn=cmd_result)

    s = sub.add_parser("status", help="Show runs (of this Claude session, otherwise all)")
    s.add_argument("run_name", nargs="?", metavar="run", help="part of the run name; without it the latest runs")
    s.add_argument("--limit", dest="limit", type=int, default=10)
    s.add_argument("--all", dest="show_all", action="store_true", help="also runs of other sessions")
    s.add_argument("--md", action="store_true", help="as a Markdown table")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("wait", help="Wait for a run (at most --max seconds) and report state or report")
    s.add_argument("run_name", nargs="?", metavar="run", help="part of the run name; without it the newest")
    s.add_argument("--max", type=int, default=540, help="seconds (default 540, below the 10-minute limit of the Bash tool)")
    s.set_defaults(fn=cmd_wait)

    sub.add_parser("resumable", help="JSON: is there a run of this session that can be resumed?").set_defaults(fn=cmd_resumable)

    s = sub.add_parser("hook", help="Entry point for the plugin's hooks (reads JSON from stdin)")
    s.add_argument("name", choices=["start", "end", "stop"])
    s.set_defaults(fn=cmd_hook)

    sub.add_parser("providers", help="List providers with their data location").set_defaults(fn=cmd_providers)
    s = sub.add_parser("host", help="Remote hosts (Mac mini, server) for --host: add, list, remove, test, install, setup")
    s.add_argument("operation", nargs="?", default="list", metavar="action", choices=["add", "list", "remove", "test", "install", "setup"])
    s.add_argument("name", nargs="?", help="host name, e.g. mini")
    s.add_argument("--ssh", metavar="USER@ADDRESS", help="ssh target: name, IP or Tailscale name")
    s.add_argument("--command", dest="command_path", help="path to omni-agent on the host (default: omni-agent on PATH; host install sets it itself)")
    s.add_argument("--replace", dest="overwrite", action="store_true", help="overwrite an existing host of the same name")
    s.set_defaults(fn=cmd_host)
    s = sub.add_parser("usage", help="Usage and balance: Claude accounts, Codex, DeepSeek, Kimi, OpenRouter, EUrouter")
    s.add_argument("selector", nargs="?", metavar="target", help="show only this account or provider (accounts, codex, deepseek, ...)")
    s.set_defaults(fn=cmd_usage)
    s = sub.add_parser("account", help="Named Claude accounts (any number): add, list, remove, default")
    s.add_argument("operation", metavar="action", choices=["add", "list", "remove", "default"])
    s.add_argument("name", nargs="?", help="account name, e.g. felipe or fps")
    s.add_argument("--kind", dest="kind", choices=["api", "token"], default="api", help="api = ANTHROPIC_API_KEY (recommended), token = subscription token")
    s.add_argument("--title", dest="title", help="display name, e.g. 'Felipe's account'")
    s.add_argument("--adopt", dest="adopt", metavar="ENV_NAME", help="reuse an existing key-file line under the account name (e.g. CLAUDE_CODE_OAUTH_TOKEN)")
    s.add_argument("--delete", dest="delete", action="store_true", help="with default: remove the default")
    s.add_argument("--replace", dest="overwrite", action="store_true", help="overwrite an existing account of the same name")
    s.add_argument("--with-key", dest="with_key", action="store_true", help="with remove: also delete the key line")
    s.add_argument("--no-usage", dest="no_usage", action="store_true", help="with list: skip the limit query (no network)")
    s.set_defaults(fn=cmd_account)
    sub.add_parser("runners", help="List runners").set_defaults(fn=cmd_runners)

    s = sub.add_parser("extras", help="Optional extras")
    s.add_argument("name", choices=["litellm"])
    s.add_argument("operation", metavar="action", choices=["install", "start", "stop", "status"])
    s.add_argument("provider", nargs="?", metavar="provider")
    s.add_argument("--model", dest="model")
    s.add_argument("--force", dest="force", action="store_true", help="install despite a different Python version")
    s.set_defaults(fn=cmd_extras)
    for name in ("run", "review", "status", "result", "cancel", "wait", "doctor", "usage"):
        sub.choices[name].add_argument("--host", metavar="TARGET", help="run on a remote host (omni-agent host add), via ssh; keys and projects live there")
    # English metavars in --help (the internal dest names stay German for now)
    metavars = {"provider": "PROVIDER", "limit": "N", "command_path": "PATH", "account": "ACCOUNT", "files": "DIR",
                "max_turns": "N", "model": "MODEL", "folder": "DIR", "title": "TITLE", "tool_list": "TOOLS", "time_limit": "SECONDS"}
    for sp in sub.choices.values():
        for a in sp._actions:
            if a.option_strings and a.nargs != 0 and a.metavar is None and a.choices is None and a.dest in metavars:
                a.metavar = metavars[a.dest]
    return p


def main(argv=None) -> int:
    argv = list(argv) if argv is not None else sys.argv[1:]
    args = build_parser().parse_args(argv)
    args._argv = argv
    if getattr(args, "host", None):
        from . import hosts
        try:
            return hosts.forward(args.host, args._argv, args)
        except ConfigError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return exc.exit_code
    if args.command == "run" and not args.task and args.text is None:
        print("Give a task file or --text", file=sys.stderr)
        return EXIT_CONFIG
    try:
        return args.fn(args)
    except ConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        return 130
