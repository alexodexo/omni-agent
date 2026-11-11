"""Providers: who serves the model, in which format, with which key."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .config import ROOT, ConfigError, home

PROTOCOLS = ("anthropic", "openai-chat", "openai-responses")

# Model tiers in the provider table (providers.json "models", --model): default, strong, small.
TIERS = ("default", "strong", "small")


@dataclass
class Provider:
    id: str
    name: str
    protocols: tuple
    base_url: str | None
    key_envs: tuple
    models: dict
    region: str = "not documented"
    note: str = ""
    verified: bool = False
    empty_vars: tuple = ()
    key_placeholder: str | None = None
    all_tiers: bool = True
    model_required: bool = False
    account_kind: str | None = None  # 'api'/'token' (Claude account) or 'login' (sign-in of the agent CLI itself)
    only_runner: str | None = None  # a provider without an address runs only through exactly this runner
    litellm: dict = field(default_factory=dict)
    base_urls: dict = field(default_factory=dict)  # address per protocol, when it differs from base_url
    claude_env: dict = field(default_factory=dict)  # extra environment for Claude Code on this provider (compatibility switches)

    def address(self, protocol: str | None) -> str | None:
        """Address for the protocol that runner and provider agreed on."""
        return self.base_urls.get(protocol) or self.base_url

    @property
    def local(self) -> bool:
        return bool(self.base_url) and ("localhost" in self.base_url or "127.0.0.1" in self.base_url)

    @property
    def runner_only(self) -> str | None:
        """Runner this provider can run through alone (accounts without an address); otherwise None."""
        if self.only_runner:
            return self.only_runner
        return "claude" if self.base_url is None else None

    @property
    def needs_key(self) -> bool:
        return bool(self.key_envs)

    def pick_model(self, requested: str | None) -> str:
        if requested:
            # Short name from the provider table (default/strong/small) or a free model name
            return self.models.get(requested, requested)
        if self.model_required or "default" not in self.models:
            raise ConfigError(f"{self.id}: please give a model with --model (a name from the provider's catalog)")
        return self.models["default"]


def _from_dict(d: dict, source: str) -> Provider:
    for mandatory in ("id", "protocols", "key_envs", "models"):
        if mandatory not in d:
            raise ConfigError(f"{source}: field '{mandatory}' is missing")
    unknown_text = [p for p in d["protocols"] if p not in PROTOCOLS]
    if unknown_text:
        raise ConfigError(f"{source}: unknown protocol {unknown_text} (allowed: {', '.join(PROTOCOLS)})")
    if d.get("account_kind") not in (None, "api", "token", "login"):
        raise ConfigError(f"{source}: account_kind must be 'api', 'token' or 'login'")
    if not d.get("model_required") and "default" not in d["models"]:
        raise ConfigError(f"{source}: 'models.default' is missing (or set 'model_required': true)")
    return Provider(
        id=d["id"],
        name=d.get("name", d["id"]),
        protocols=tuple(d["protocols"]),
        base_url=d.get("base_url"),
        key_envs=tuple(d["key_envs"]),
        models=dict(d["models"]),
        region=d.get("region", "not documented"),
        note=d.get("note", ""),
        verified=bool(d.get("verified", False)),
        empty_vars=tuple(d.get("empty_vars", ())),
        key_placeholder=d.get("key_placeholder"),
        all_tiers=bool(d.get("all_tiers", True)),
        model_required=bool(d.get("model_required", False)),
        account_kind=d.get("account_kind"),
        only_runner=d.get("runner_only"),
        litellm=dict(d.get("litellm", {})),
        base_urls=dict(d.get("base_urls", {})),
        claude_env={str(k): str(v) for k, v in dict(d.get("claude_env", {})).items()},
    )


def _load_file(file_path) -> list:
    try:
        doc = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConfigError(f"{file_path}: not readable ({exc})") from exc
    entries = doc.get("providers") if isinstance(doc, dict) else doc
    if not isinstance(entries, list):
        raise ConfigError(f"{file_path}: expected a list of providers (or an object with a 'providers' list)")
    return [_from_dict(e, str(file_path)) for e in entries]


def load_providers() -> dict:
    """providers.json from the repo, then own entries from ~/.omni-agent/providers.d/*.json (they override equal ids)."""
    final_answer = {}
    for a in _load_file(ROOT / "providers.json"):
        final_answer[a.id] = a
    own = home() / "providers.d"
    if own.is_dir():
        for file_path in sorted(own.glob("*.json")):
            for a in _load_file(file_path):
                final_answer[a.id] = a
    return final_answer


def get_provider(provider_id: str) -> Provider:
    show_all = load_providers()
    if provider_id not in show_all:
        raise ConfigError(f"Unknown provider '{provider_id}'. Known: {', '.join(sorted(show_all))}")
    return show_all[provider_id]
