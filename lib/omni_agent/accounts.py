"""Named Claude accounts: any number, each with its own name and its own key.

An account is a provider entry in ~/.omni-agent/providers.d/account-<name>.json (no secret inside)
plus a line OMNI_AGENT_ACCOUNT_<NAME>=... in ~/.omni-agent/env. Use it with: --provider claude-<name>.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from .config import ConfigError, env_file, home, read_key_file

NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")
KINDS = {
    "api": ("ANTHROPIC_API_KEY", "API key (recommended)"),
    "token": ("CLAUDE_CODE_OAUTH_TOKEN", "Subscription token"),
}
TOKEN_NOTE = (
    "Subscription token (CLAUDE_CODE_OAUTH_TOKEN): whether an unattended run with it is allowed under Anthropic's terms "
    "is not documented. Omni-Agent stores the token only in the key file."
)


def check_name(name: str) -> str:
    if not NAME_PATTERN.match(name or ""):
        raise ConfigError(
            f"Account name '{name}' is invalid. Allowed: lowercase letters, digits, hyphen, at most 31 characters, "
            "starting with a letter or digit (e.g. felipe, fps)."
        )
    return name


def account_id(name: str) -> str:
    return f"claude-{check_name(name)}"


def account_env(name: str) -> str:
    return "OMNI_AGENT_ACCOUNT_" + check_name(name).upper().replace("-", "_")


def account_file(name: str) -> Path:
    return home() / "providers.d" / f"account-{check_name(name)}.json"


def _entry(name: str, kind: str, title: str | None) -> dict:
    note = (
        "Own quota of this account. "
        + (TOKEN_NOTE if kind == "token" else "Billed through this account's API key.")
    )
    return {
        "id": account_id(name),
        "name": title or f"Claude account {name}",
        "protocols": ["anthropic"],
        "base_url": None,
        "key_envs": [account_env(name)],
        "account_kind": kind,
        "models": {"default": "sonnet", "small": "haiku", "strong": "opus"},
        "all_tiers": False,
        "region": "Anthropic",
        "verified": False,
        "note": note,
    }


def create(name: str, kind: str, title: str | None = None, overwrite: bool = False) -> Path:
    if kind not in KINDS:
        raise ConfigError(f"Kind '{kind}' is unknown. Allowed: {', '.join(KINDS)}")
    file_path = account_file(name)
    if file_path.exists() and not overwrite:
        raise ConfigError(f"Account '{name}' already exists ({file_path}). Overwrite with --replace or pick another name.")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(home(), 0o700)
    file_path.write_text(json.dumps({"providers": [_entry(name, kind, title)]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return file_path


def list_items() -> list:
    """All named accounts: name, art, titel, schluessel (set/missing)."""
    folder = home() / "providers.d"
    if not folder.is_dir():
        return []
    data_file = read_key_file()
    final_answer = []
    for file_path in sorted(folder.glob("account-*.json")):
        try:
            doc = json.loads(file_path.read_text(encoding="utf-8"))
            e = doc["providers"][0]
        except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError):
            continue
        env = e["key_envs"][0]
        final_answer.append({
            "name": file_path.stem.split("-", 1)[1],
            "id": e["id"],
            "kind": e.get("account_kind") or "api",
            "title": e.get("name", ""),
            "key_values": "set" if (os.environ.get(env) or data_file.get(env)) else "missing",
            "env": env,
        })
    return final_answer


def _write_env(lines: list) -> None:
    """Atomic and with mode 600; the key file is never half-written."""
    target_file = env_file()
    fd, tmp = tempfile.mkstemp(dir=target_file.parent, prefix=".env-")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(lines).rstrip("\n") + "\n")
        os.replace(tmp, target_file)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _lines() -> list:
    file_path = env_file()
    if not file_path.exists():
        return []
    read_key_file()  # refuses permissions that are too open
    return file_path.read_text(encoding="utf-8").splitlines()


def _name_of_line(line: str) -> str:
    z = line.strip()
    if not z or z.startswith("#") or "=" not in z:
        return ""
    if z.startswith("export "):
        z = z[len("export "):]
    return z.partition("=")[0].strip()


def set_key(env_name: str, value: str) -> None:
    lines = _lines()
    new, is_set = [], False
    for z in lines:
        if _name_of_line(z) == env_name:
            if not is_set:
                new.append(f"{env_name}={value}")
                is_set = True
            continue
        new.append(z)
    if not is_set:
        new.append(f"{env_name}={value}")
    _write_env(new)


def rename_key(old: str, new: str) -> None:
    """Re-uses an existing entry under a new name without touching the value."""
    lines = _lines()
    if not any(_name_of_line(z) == old for z in lines):
        raise ConfigError(f"There is no line {old}=... in {env_file()}")
    if any(_name_of_line(z) == new for z in lines):
        raise ConfigError(f"{env_file()} already has {new}.")
    final_answer = []
    for z in lines:
        if _name_of_line(z) == old:
            raw = z.strip()
            raw = raw[len("export "):] if raw.startswith("export ") else raw
            final_answer.append(new + "=" + raw.partition("=")[2])
        else:
            final_answer.append(z)
    _write_env(final_answer)


def remove_entry(name: str, with_key: bool = False) -> None:
    file_path = account_file(name)
    if not file_path.exists():
        raise ConfigError(f"Account '{name}' does not exist. Existing: omni-agent account list")
    file_path.unlink()
    if with_key:
        gone = {account_env(name)}
        lines = _lines()
        rest = [z for z in lines if _name_of_line(z) not in gone]
        if len(rest) != len(lines):
            _write_env(rest)


# ---------- usage / limits ----------

USAGE_MODEL = "claude-haiku-5-5"
MESSAGES_URL = "https://api.anthropic.com/v1/messages"


def _fetch_headers(env_name: str, kind: str, key_values: str) -> dict:
    """One one-token request to the smallest model; the response carries the limits as headers.

    Costs practically nothing but counts as one request. The key goes only to api.anthropic.com.
    """
    import urllib.request
    head = {"anthropic-version": "2023-06-01", "content-type": "application/json", "User-Agent": "omni-agent"}
    system = None
    if kind == "token":
        head["Authorization"] = f"Bearer {key_values}"
        head["anthropic-beta"] = "oauth-2025-04-20"
        system = "You are Claude Code, Anthropic's official CLI for Claude."
    else:
        head["x-api-key"] = key_values
    body = {"model": USAGE_MODEL, "max_tokens": 1, "messages": [{"role": "user", "content": "."}]}
    if system:
        body["system"] = system
    req = urllib.request.Request(MESSAGES_URL, data=json.dumps(body).encode(), headers=head)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return {k.lower(): v for k, v in response.headers.items()}
    except Exception as exc:  # HTTPError carries headers and status, network errors do not
        header_lines = getattr(exc, "headers", None)
        code = getattr(exc, "code", None)
        if header_lines is not None and code == 429:
            return {k.lower(): v for k, v in header_lines.items()} | {"_status": "429"}
        raise ConfigError(f"HTTP {code}" if code else f"not reachable ({type(exc).__name__})") from None


def _time_text(epoch: str) -> str:
    from datetime import datetime
    try:
        t = datetime.fromtimestamp(int(epoch))
        return f"{('Mon','Tue','Wed','Thu','Fri','Sat','Sun')[t.weekday()]} {t:%m-%d %H:%M}"
    except (ValueError, OSError):
        return "?"


def _time_left(epoch: str) -> str:
    import time
    try:
        rest = int(epoch) - int(time.time())
    except ValueError:
        return ""
    if rest <= 0:
        return "now"
    days, std, minutes = rest // 86400, rest % 86400 // 3600, rest % 3600 // 60
    return f"{days}d {std}h" if days else (f"{std}h {minutes}m" if std else f"{minutes}m")


def _percent(value: str | None) -> str:
    try:
        return f"{round(float(value) * 100)}%"
    except (TypeError, ValueError):
        return "-"


def usage_text(header: dict, kind: str) -> str:
    """Turns the rate-limit headers into one line. A missing window means none is active right now."""
    if kind == "token":
        parts = []
        for window, name in (("5h", "5 h"), ("7d", "7 days")):
            u = header.get(f"anthropic-ratelimit-unified-{window}-utilization")
            r = header.get(f"anthropic-ratelimit-unified-{window}-reset")
            parts.append(f"{name} {_percent(u)}" + (f", resets {_time_text(r)} (in {_time_left(r)})" if u is not None and r else ""))
        status = header.get("anthropic-ratelimit-unified-status", "")
        extra_text = "" if status in ("", "allowed") else f"   STATUS: {status}"
        return "  |  ".join(parts) + extra_text
    parts = []
    for key_values, name in (("requests", "Requests"), ("tokens", "Tokens")):
        rest = header.get(f"anthropic-ratelimit-{key_values}-remaining")
        ceiling = header.get(f"anthropic-ratelimit-{key_values}-limit")
        if rest is not None and ceiling is not None:
            parts.append(f"{name} left {rest}/{ceiling}")
    return "   ".join(parts) or "no limit information in the response"


def usage(account: dict, fetch=_fetch_headers) -> str:
    """Usage line for an account from liste(). Errors become text, never an exception."""
    if account["key_values"] != "set":
        return "key missing"
    data_file = read_key_file()
    value = os.environ.get(account["env"]) or data_file.get(account["env"])
    try:
        return usage_text(fetch(account["env"], account["kind"], value), account["kind"])
    except ConfigError as exc:
        return f"Query failed: {exc}"
