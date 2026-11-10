"""LiteLLM extra: local translator from the Anthropic format to OpenAI chat. Optional, never required.

Supply chain: the version is pinned and installed with a hash lock (extras/litellm/requirements.lock)
in its own virtual environment. The proxy listens only on 127.0.0.1 and gets only ONE provider key.
Background: litellm 1.107.0 was compromised on 2026-10-21 (PyPI and Docker images). Before changing the pin,
read the incident page of the vendor.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from .config import ROOT, ConfigError, home

LOCK_FILE = ROOT / "extras" / "litellm" / "requirements.lock"
LOCK_PYTHON = (3, 14)  # version the lock file was built for
KNOWN_BAD = ("litellm_init.pth",)  # marker of the March 2026 attack


def folder():
    return home() / "extras" / "litellm"


def port() -> int:
    return int(os.environ.get("OMNI_AGENT_LITELLM_PORT", "4000"))


def pinned_version() -> str:
    hits = re.search(r"^litellm==([\w.\-]+)", LOCK_FILE.read_text(encoding="utf-8"), re.M)
    return hits.group(1) if hits else "unknown"


def venv_python():
    return folder() / "venv" / "bin" / "python"


def installed() -> bool:
    return (folder() / "venv" / "bin" / "litellm").exists()


def install(force: bool = False) -> None:
    if sys.version_info[:2] != LOCK_PYTHON and not force:
        raise ConfigError(
            f"The lock file was built for Python {LOCK_PYTHON[0]}.{LOCK_PYTHON[1]}, this is "
            f"{sys.version_info[0]}.{sys.version_info[1]}. Try at your own risk with --force "
            f"or use --runner opencode instead of the translator."
        )
    proxy_dir = folder()
    proxy_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(home(), 0o700)
    venv = proxy_dir / "venv"
    print(f"Creating isolated environment: {venv}", flush=True)
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    print(f"Installing litellm=={pinned_version()} with hash check ...", flush=True)
    res = subprocess.run(
        [str(venv_python()), "-m", "pip", "install", "--require-hashes", "--no-deps", "--disable-pip-version-check",
         "-r", str(LOCK_FILE)],
    )
    if res.returncode != 0:
        raise ConfigError("Installation failed (hash check or network). Nothing was enabled.")
    for name in KNOWN_BAD:
        if any(venv.rglob(name)):
            raise ConfigError(f"WARNING: {name} found. Delete environment {venv} and rotate all keys!")
    output = subprocess.run(
        [str(venv_python()), "-c", "import importlib.metadata as m; print(m.version('litellm'))"],
        capture_output=True, text=True,
    ).stdout.strip()
    print(f"Done: litellm {output}. Start with: omni-agent extras litellm start <provider>", flush=True)


def _state_file():
    return folder() / "running.json"


def _state() -> dict | None:
    try:
        z = json.loads(_state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    try:
        os.kill(z["pid"], 0)
    except (OSError, KeyError):
        return None
    return z


def _healthy() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port()}/health/liveliness", timeout=3) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def make_config(provider, model: str) -> str:
    """config.yaml without secrets: the key comes from the environment of the proxy."""
    lt = provider.litellm or {}
    provider_prefix = lt.get("prefix") or "openai"
    key_env = lt.get("key_env") or (provider.key_envs[0] if provider.key_envs else "OMNI_AGENT_PROVIDER_KEY")
    api_base = lt["api_base"] if "api_base" in lt else provider.base_url
    lines = [
        "model_list:",
        f"  - model_name: {json.dumps(model)}",
        "    litellm_params:",
        f"      model: {json.dumps(f'{provider_prefix}/{model}')}",
        f"      api_key: os.environ/{key_env}",
    ]
    if api_base:
        lines.append(f"      api_base: {json.dumps(api_base)}")
    lines += ["litellm_settings:", "  telemetry: false", "  drop_params: true"]
    return "\n".join(lines) + "\n"


def start_proxy(provider, model: str, provider_key: str):
    """Starts (or reuses) the proxy for exactly this provider and model. Returns (base_url, access key)."""
    if not installed():
        raise ConfigError("The LiteLLM extra is not installed. First run: omni-agent extras litellm install")
    proxy_dir = folder()
    key_file = proxy_dir / "masterkey"
    if not key_file.exists():
        fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write("sk-local-" + secrets.token_hex(16))
    master = key_file.read_text(encoding="utf-8").strip()
    address = f"http://127.0.0.1:{port()}"

    z = _state()
    if z and z.get("provider") == provider.id and z.get("model") == model and _healthy():
        return address, master
    if z:
        stop_proxy()

    (proxy_dir / "config.yaml").write_text(make_config(provider, model), encoding="utf-8")
    lt = provider.litellm or {}
    key_env = lt.get("key_env") or provider.key_envs[0]
    env = {
        "HOME": str(Path.home()), "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        key_env: provider_key, "LITELLM_MASTER_KEY": master,
    }
    log_file = open(proxy_dir / "proxy.log", "ab")
    proc = subprocess.Popen(
        [str(proxy_dir / "venv" / "bin" / "litellm"), "--config", str(proxy_dir / "config.yaml"),
         "--host", "127.0.0.1", "--port", str(port())],
        env=env, stdout=log_file, stderr=log_file, stdin=subprocess.DEVNULL, start_new_session=True,
    )
    _state_file().write_text(json.dumps({"pid": proc.pid, "provider": provider.id, "model": model}), encoding="utf-8")
    for _ in range(90):
        if _healthy():
            return address, master
        if proc.poll() is not None:
            break
        time.sleep(1)
    raise ConfigError(f"LiteLLM proxy does not start. See {proxy_dir / 'proxy.log'}")


def stop_proxy() -> bool:
    z = _state()
    if not z:
        return False
    try:
        os.killpg(z["pid"], signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        _state_file().unlink()
    except OSError:
        pass
    return True


def status_text() -> str:
    if not installed():
        return "LiteLLM: not installed (optional). Install: omni-agent extras litellm install"
    z = _state()
    head_text = f"LiteLLM {pinned_version()} installed"
    if z and _healthy():
        return f"{head_text}, running on 127.0.0.1:{port()} for {z['provider']} / {z['model']}"
    return f"{head_text}, not running"
