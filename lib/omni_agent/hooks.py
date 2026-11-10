"""Entry points for the plugin hooks (SessionStart, SessionEnd, Stop) and the review gate.

Hooks read a JSON from Claude Code on stdin. A hook must never disturb the session: any problem
(no git, no provider, timeout) means "let it pass" here, plus one line on stderr.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import signal
import sys
import tempfile
import time
from pathlib import Path

from . import review
from .config import ConfigError, home, runs_dir, read_config, review_gate_an, default_provider
from .engine import all_runs, execute, read_status, process_is_omni_agent

GATE_TASK = """You are the stop guard of a Claude Code session. Review the changes Claude just made (file changes.patch, file list in changed_files.txt, Claude's last answer in last_answer.md).

Question whether exactly this work and its design decisions should ship as they are: follow-on bugs, empty states, retries, stale state, rollback, permissions.

Your first line in report.md must be exactly one of these two, with nothing before it:
ALLOW: <short reason>
BLOCK: <short reason>

Use ALLOW if you see no bug that must be fixed before stopping. Use BLOCK only for a provable bug in the diff, which you name with file and location. You only see the diff: anything that depends on invisible context is no reason to block. Invent nothing. Do not change the code.
"""

MAX_GATE_CHARS = 150_000
MAX_BLOCKS_PER_SESSION = 3


def read_input() -> dict:
    try:
        raw = sys.stdin.read().strip()
        return json.loads(raw) if raw else {}
    except (OSError, ValueError):
        return {}


def _shell_quote(value: str) -> str:
    return "'" + str(value).replace("'", "'\"'\"'") + "'"


def hook_start(entry_text: dict) -> int:
    """Expose the session ID to all Bash commands of this session (including subagents) as an environment variable."""
    data_file = os.environ.get("CLAUDE_ENV_FILE")
    session = entry_text.get("session_id")
    if data_file and session:
        with open(data_file, "a", encoding="utf-8") as f:
            f.write(f"export OMNI_AGENT_SESSION={_shell_quote(session)}\n")
    return 0


def active_in_session(session: str | None) -> list:
    if not session:
        return []
    return [p for p in all_runs(session) if (read_status(p) or {}).get("state") == "running"]


def hook_end(entry_text: dict) -> int:
    """End runs that were started in this session and are still running (no orphan run at the user's expense).
    On /clear they keep running, since the session continues right away. Reports stay in place."""
    if entry_text.get("reason") == "clear":
        return 0
    for folder in active_in_session(entry_text.get("session_id") or os.environ.get("OMNI_AGENT_SESSION") or None):
        pid = (read_status(folder) or {}).get("pid")
        if process_is_omni_agent(pid):
            with contextlib.suppress(OSError, ValueError):
                os.kill(int(pid), signal.SIGTERM)
    return 0


# ---------- Review gate ----------

def _gate_file() -> Path:
    return home() / "gate.json"


def _read_gate() -> dict:
    try:
        doc = json.loads(_gate_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _write_gate(doc: dict) -> None:
    home().mkdir(parents=True, exist_ok=True)
    tmp = _gate_file().with_suffix(".tmp")
    tmp.write_text(json.dumps(doc) + "\n", encoding="utf-8")
    os.replace(tmp, _gate_file())


def _note(text: str) -> None:
    print(text, file=sys.stderr)


def check_gate(entry_text: dict) -> tuple:
    """Return (block, reason). Expensive only if the diff changed since the last check."""
    session = entry_text.get("session_id") or "no-session"
    provider = read_config().get("review_gate_provider") or default_provider()
    if not provider:
        _note("Review gate is on but no provider is set: omni-agent account default NAME (or config review_gate_provider).")
        return False, ""
    cwd = entry_text.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    os.chdir(cwd)
    try:
        doc = review.collect(None, worktree_only=True)
        if not doc["diff"].strip():
            return False, ""
        review.verify(doc, force=False)  # raises on secrets or an oversized diff
    except ConfigError as exc:
        _note(f"Review gate skipped: {exc}")
        return False, ""
    if len(doc["diff"]) > MAX_GATE_CHARS:
        _note(f"Review gate skipped: diff over {MAX_GATE_CHARS // 1000} KB.")
        return False, ""

    fingerprint = hashlib.sha256(doc["diff"].encode("utf-8")).hexdigest()
    state = _read_gate()
    own_name = state.get(session, {})
    if own_name.get("diff") == fingerprint:
        return False, ""  # we already checked this state: do not block a second time, no loop
    if int(own_name.get("blocks") or 0) >= MAX_BLOCKS_PER_SESSION:
        _note("Review gate: block limit of this session reached, letting it pass.")
        return False, ""

    run_dir = runs_dir() / (time.strftime("%Y%m%d-%H%M%S") + f"-{os.getpid()}-gate")
    with tempfile.TemporaryDirectory() as files:
        (Path(files) / "changes.patch").write_text(doc["diff"], encoding="utf-8")
        (Path(files) / "changed_files.txt").write_text(doc["names"], encoding="utf-8")
        (Path(files) / "last_answer.md").write_text(str(entry_text.get("last_assistant_message") or "(not provided)"), encoding="utf-8")
        args = argparse.Namespace(
            task=None, text=GATE_TASK, provider=provider, model=read_config().get("review_gate_model"), runner=None, tool_list="read,write",
            max_turns=8, time_limit=600, folder=str(run_dir), files=files, via_litellm=False, resume=None,
            effort=None, project=None, writable=False, kind="gate",
        )
        try:
            with open(os.devnull, "w") as quiet, contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
                code = execute(args)
        except ConfigError as exc:
            _note(f"Review gate skipped: {exc}")
            return False, ""
    report = run_dir / "report.md"
    first = ""
    if code == 0 and report.is_file():
        first = (report.read_text(encoding="utf-8").strip().splitlines() or [""])[0].strip()
    state[session] = {"diff": fingerprint, "blocks": int(own_name.get("blocks") or 0)}
    if first.startswith("BLOCK:"):
        state[session]["blocks"] += 1
        _write_gate(state)
        return True, f"The review gate (Omni-Agent, {provider}) found problems to fix before stopping: {first[6:].strip()}"
    _write_gate(state)
    if not first.startswith("ALLOW:"):
        _note("Review gate: unclear or missing answer, letting it pass.")
    return False, ""


def hook_stop(entry_text: dict) -> int:
    note_text = ""
    active = active_in_session(entry_text.get("session_id"))
    if active:
        note_text = f"Omni-Agent: {len(active)} run(s) of this session are still running (omni-agent status; cancel: omni-agent cancel)."
        _note(note_text)
    if not review_gate_an():
        return 0
    try:
        do_block, reason = check_gate(entry_text)
    except Exception as exc:  # a hook must never hold the session
        _note(f"Review gate skipped ({exc.__class__.__name__}: {exc})")
        return 0
    if do_block:
        print(json.dumps({"decision": "block", "reason": (note_text + " " if note_text else "") + reason}, ensure_ascii=False))
    return 0


def run_hook(name: str) -> int:
    if os.environ.get("OMNI_AGENT_RUN") == "1":
        return 0  # we are inside an Omni-Agent run ourselves: do nothing, no loop
    entry_text = read_input()
    if name == "start":
        return hook_start(entry_text)
    if name == "end":
        return hook_end(entry_text)
    if name == "stop":
        return hook_stop(entry_text)
    print(f"Unknown hook '{name}'", file=sys.stderr)
    return 0
