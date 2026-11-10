"""Contract between the core and a runner (agent CLI)."""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# Neutral tools. Each adapter translates them into its own language.
TOOLS = ("read", "write", "web_search", "web_fetch", "shell")
DEFAULT_TOOLS = ("read", "write", "web_search", "web_fetch")

# Variables that are not secrets and are needed behind corporate proxies.
PASS_THROUGH = (
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY",
    "http_proxy", "https_proxy", "no_proxy", "all_proxy",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "NODE_EXTRA_CA_CERTS", "REQUESTS_CA_BUNDLE",
    "LANG", "LC_ALL",
)


@dataclass
class RunContext:
    prompt: str                      # frame + task
    folder: Path                     # empty working folder
    provider: object                 # anbieter.Anbieter
    model: str
    base_url: str | None             # effective address (the local one with LiteLLM)
    protocol: str                   # effective protocol
    key_values: dict                 # only the keys this run needs: name -> value
    tool_list: tuple
    max_turns: int
    extra: dict = field(default_factory=dict)
    project: Path | None = None      # working folder = the user's project (instead of the empty run folder); the report comes from the final answer
    writable: bool = False         # files may be changed in the project (otherwise read-only)

    @property
    def work_dir(self) -> Path:
        return self.project or self.folder


@dataclass
class Command:
    argv: list
    env: dict
    stdin_text: str | None = None


def base_env() -> dict:
    """The bare minimum. Nothing from the orchestrator session (sign-in, base URL) gets through."""
    env = {
        "HOME": str(Path.home()),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "TERM": "dumb",
        "OMNI_AGENT_RUN": "1",  # the hooks of this plugin use this to detect that they are inside a run, and do nothing
    }
    for name in PASS_THROUGH:
        if os.environ.get(name):
            env[name] = os.environ[name]
    return env


class Runner:
    name = ""
    binary = ""
    protocols: tuple = ()
    can: frozenset = frozenset()            # which neutral tools it can control
    cannot_forbid: frozenset = frozenset()  # tools it always has
    in_sandbox: bool = False                 # tools that cannot be forbidden run in an OS sandbox (write only in the folder, no network)
    experimental = False
    note = ""

    def file_path(self) -> str | None:
        return shutil.which(self.binary)

    def version(self) -> str | None:
        file_path = self.file_path()
        if not file_path:
            return None
        try:
            res = subprocess.run([file_path, "--version"], capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            return "unknown"
        text = (res.stdout or res.stderr).strip().splitlines()
        return text[0] if text else "unknown"

    def speaks(self, protocol: str) -> bool:
        return protocol in self.protocols

    def build(self, ctx: RunContext) -> Command:  # pragma: no cover - interface
        raise NotImplementedError

    def progress(self, line: str, state: dict) -> list:
        """Translate an output line into readable progress lines. Counts zustand['runden']."""
        return [line.rstrip()] if line.strip() else []


def shorten(text, n: int = 110) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"
