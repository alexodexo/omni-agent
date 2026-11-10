"""Paths, key sources and shared error classes. Standard library only."""
from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from urllib.parse import urlparse

# lib/omni_agent/konfig.py -> repo or plugin folder
ROOT = Path(__file__).resolve().parents[2]

EXIT_OK = 0
EXIT_RUN = 1
EXIT_CONFIG = 2
EXIT_ENDPOINT = 3
EXIT_TIMEOUT = 124


class ConfigError(Exception):
    """Something is missing or misconfigured (exit 2)."""

    exit_code = EXIT_CONFIG


class EndpointError(ConfigError):
    """The provider is not reachable (exit 3)."""

    exit_code = EXIT_ENDPOINT


def home() -> Path:
    return Path(os.environ.get("OMNI_AGENT_HOME") or Path.home() / ".omni-agent")


def env_file() -> Path:
    return home() / "env"


def runs_dir() -> Path:
    """Folder with all runs (~/.omni-agent/runs)."""
    return home() / "runs"


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def read_key_file() -> dict:
    """Read NAME=value from ~/.omni-agent/env. The file is never executed as shell code.

    Refuses the file if group or others can read it.
    """
    file_path = env_file()
    if not file_path.exists():
        return {}
    if file_path.stat().st_mode & 0o077:
        raise ConfigError(f"Permissions of {file_path} are too open. Please run: chmod 600 {file_path}")
    vals = {}
    for line in file_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        name, _, value = line.partition("=")
        value = _unquote(value)
        if name.strip() and value:
            vals[name.strip()] = value
    return vals


def get_key(name: str, data_file: dict | None = None) -> str | None:
    """Environment before file. Empty values count as unset."""
    value = os.environ.get(name)
    if value:
        return value
    if data_file is None:
        data_file = read_key_file()
    return data_file.get(name) or None


def check_reachable(base_url: str, time_limit: float = 5.0) -> None:
    """TCP connection to the endpoint. Raises EndpunktFehler on failure."""
    if os.environ.get("OMNI_AGENT_NO_NETCHECK") == "1":
        return
    parts = urlparse(base_url)
    host = parts.hostname
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=time_limit):
            return
    except OSError as exc:
        raise EndpointError(f"{host}:{port} not reachable ({exc.__class__.__name__}: {exc})") from exc


def config_file() -> Path:
    return home() / "config.json"


def read_config() -> dict:
    """config.json (keys: default_provider, review_gate_provider, review_gate_model, review_gate)."""
    try:
        doc = json.loads(config_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _write_config(doc: dict) -> None:
    home().mkdir(parents=True, exist_ok=True)
    config_file().write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def default_provider() -> str | None:
    """Provider used when --provider is not given. Only set if the user explicitly wants it."""
    value = read_config().get("default_provider")
    return value if isinstance(value, str) and value else None


def set_default_provider(provider_id: str | None) -> None:
    doc = read_config()
    if provider_id:
        doc["default_provider"] = provider_id
    else:
        doc.pop("default_provider", None)
    _write_config(doc)


def set_config(key_values: str, value) -> None:
    """Set one key of config.json (None deletes it)."""
    doc = read_config()
    if value is None:
        doc.pop(key_values, None)
    else:
        doc[key_values] = value
    _write_config(doc)


def claude_session() -> str | None:
    """ID of the Claude Code session this command runs in (set by the SessionStart hook). Groups runs by session."""
    return os.environ.get("OMNI_AGENT_SESSION") or None


def review_gate_an() -> bool:
    return read_config().get("review_gate") is True
