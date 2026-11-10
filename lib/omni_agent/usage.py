"""Usage and balance per provider: show as much as the provider exposes.

- Codex: window utilization, plan, credits and reset credits via `codex app-server`
  (method `account/rateLimits/read`, using the Codex CLI login itself; Omni-Agent stores nothing).
- DeepSeek, Kimi (Moonshot), OpenRouter, EUrouter: balance via the query endpoint of the provider.
  The key goes only to the provider it belongs to.
- Claude accounts: see konten.py (rate-limit headers).
- All others (Ollama, Nvidia, custom providers): no data, and the output says so.

Every query turns an error into text, never an exception.
"""
from __future__ import annotations

import json
import select
import subprocess
import time
import urllib.request

from .config import ConfigError
from .accounts import _time_left, _time_text


def _window_name(minutes) -> str:
    try:
        m = int(minutes)
    except (TypeError, ValueError):
        return "Window"
    if m % 10080 == 0:
        return "7 days" if m == 10080 else f"{m // 10080} weeks"
    if m % 1440 == 0:
        return f"{m // 1440} days"
    if m % 60 == 0:
        return f"{m // 60} h"
    return f"{m} min"


def codex_text(response: dict) -> str:
    """Turns the response of account/rateLimits/read into one line."""
    r = response.get("rateLimits") or {}
    parts = []
    plan = r.get("planType")
    if plan and plan != "unknown":
        parts.append(f"Plan {plan}")
    for key_values in ("primary", "secondary"):
        f = r.get(key_values)
        if not f:
            continue
        line = f"{_window_name(f.get('windowDurationMins'))} {f.get('usedPercent', '?')}% used"
        if f.get("resetsAt"):
            line += f", resets {_time_text(str(f['resetsAt']))} (in {_time_left(str(f['resetsAt']))})"
        parts.append(line)
    if not any(r.get(k) for k in ("primary", "secondary")):
        parts.append("no windows reported")
    credits = r.get("credits") or {}
    if credits.get("unlimited"):
        parts.append("credits unlimited")
    elif credits.get("balance") not in (None, "", "0", "0.0"):
        parts.append(f"credits {credits['balance']}")
    reset_credits = (response.get("rateLimitResetCredits") or {}).get("availableCount")
    if reset_credits:
        parts.append(f"{reset_credits} reset credit{'s' if reset_credits != 1 else ''} available")
    status = []
    if response.get("ordinaryUsageAllowed") is False:
        status.append("normal usage blocked")
    if r.get("rateLimitReachedType"):
        status.append(f"limit reached ({r['rateLimitReachedType']})")
    if status:
        parts.append("STATUS: " + ", ".join(status))
    return "  |  ".join(parts)


def _app_server_query(exe: str, timeout: int = 25) -> dict:
    """Asks `codex app-server` (JSON lines over stdin/stdout) for the limits of the logged-in account."""
    try:
        p = subprocess.Popen([exe, "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, text=True)
    except OSError as exc:
        raise ConfigError(f"codex cannot be started ({type(exc).__name__})") from None

    def send_json(o):
        p.stdin.write(json.dumps(o) + "\n")
        p.stdin.flush()

    def read_reply(number):
        end = time.time() + timeout
        while time.time() < end:
            ready, _, _ = select.select([p.stdout], [], [], 1)
            if not ready:
                continue
            line = p.stdout.readline()
            if not line:
                break
            try:
                o = json.loads(line)
            except ValueError:
                continue
            if o.get("id") == number:
                return o
        raise ConfigError("no response from codex app-server")

    try:
        send_json({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "omni-agent", "title": "Omni-Agent", "version": "1"}}})
        read_reply(1)
        send_json({"method": "initialized"})
        send_json({"id": 2, "method": "account/rateLimits/read"})
        response = read_reply(2)
    except (BrokenPipeError, OSError):
        raise ConfigError("codex app-server closed the connection") from None
    finally:
        p.terminate()
    if response.get("error"):
        raise ConfigError(str((response["error"] or {}).get("message") or "error from codex"))
    return response.get("result") or {}


def codex_usage(fetch=_app_server_query) -> str:
    from .runner import RUNNER
    exe = RUNNER["codex"].file_path()
    if not exe:
        return "codex not installed"
    try:
        return codex_text(fetch(exe))
    except ConfigError as exc:
        return f"Query failed: {exc}"


# ---------- balance of third-party providers ----------

def _fetch_json(url: str, key_values: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key_values}", "Accept": "application/json", "User-Agent": "omni-agent"})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        code = getattr(exc, "code", None)
        raise ConfigError(f"HTTP {code}" if code else f"not reachable ({type(exc).__name__})") from None


def _amount(value) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def _deepseek(key_values: str, lookup=_fetch_json) -> str:
    d = lookup("https://api.deepseek.com/user/balance", key_values)
    parts = []
    for b in d.get("balance_infos") or []:
        line = f"Balance {_amount(b.get('total_balance'))} {b.get('currency', '')}".strip()
        extra = []
        if b.get("granted_balance") not in (None, "0.00", "0"):
            extra.append(f"granted {_amount(b['granted_balance'])}")
        if b.get("topped_up_balance") not in (None, "0.00", "0"):
            extra.append(f"topped up {_amount(b['topped_up_balance'])}")
        parts.append(line + (f" ({', '.join(extra)})" if extra else ""))
    if d.get("is_available") is False:
        parts.append("STATUS: balance too low for requests")
    return "  |  ".join(parts) or "no data"


def _kimi(key_values: str, lookup=_fetch_json) -> str:
    d = (lookup("https://api.moonshot.ai/v1/users/me/balance", key_values).get("data")) or {}
    parts = [f"available {_amount(d.get('available_balance'))}"]
    if d.get("voucher_balance") not in (None, 0, "0"):
        parts.append(f"vouchers {_amount(d['voucher_balance'])}")
    if d.get("cash_balance") not in (None, 0, "0"):
        parts.append(f"cash {_amount(d['cash_balance'])}")
    return "Balance " + ", ".join(parts)


def _credits(head_text: str, unit: str):
    def query(key_values: str, lookup=_fetch_json) -> str:
        d = (lookup(f"{head_text}/credits", key_values).get("data")) or {}
        total, used = d.get("total_credits"), d.get("total_usage")
        if total is None:
            return "no data"
        try:
            rest = float(total) - float(used or 0)
            return f"Balance {rest:.2f} {unit} (loaded {float(total):.2f}, used {float(used or 0):.2f})"
        except (TypeError, ValueError):
            return f"Balance loaded {total}, used {used}"
    return query


BALANCE_QUERIES = {
    "deepseek": _deepseek,
    "kimi": _kimi,
    "openrouter": _credits("https://openrouter.ai/api/v1", "USD"),
    "eurouter": _credits("https://api.eurouter.ai/api/v1", "EUR"),
}


def balance(provider_id: str, key_values: str | None, queries=None) -> str:
    """One balance line, or an honest sentence on why there is none."""
    queries = BALANCE_QUERIES if queries is None else queries
    if provider_id == "ollama":
        return "runs locally, no balance"
    if provider_id not in queries:
        return "no query known"
    if not key_values:
        return "key missing"
    try:
        return queries[provider_id](key_values)
    except ConfigError as exc:
        return f"Query failed: {exc}"
