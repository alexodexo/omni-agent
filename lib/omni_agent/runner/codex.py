"""Runner `codex`: OpenAI Codex CLI (`codex exec`). Spricht nur die Responses-API.

Stand: laut Herstellerdoku gebaut, NICHT live geprüft (codex war nicht installiert).
Codex kann keine einzelnen Werkzeuge verbieten, seine Shell ist immer da (nur durch die Sandbox begrenzt).
Darum verlangt der Kern hier ausdrücklich `--werkzeuge +shell`.
"""
import json

from .basis import Befehl, LaufKontext, Runner, grundumgebung, kurz


class CodexRunner(Runner):
    name = "codex"
    binary = "codex"
    protokolle = ("openai-responses",)
    kann = frozenset({"lesen", "schreiben", "shell"})
    nicht_verbietbar = frozenset({"shell"})
    hinweis = "Nur Responses-API. Shell ist immer da (Sandbox workspace-write). Nicht live geprüft."

    def baue(self, ctx: LaufKontext) -> Befehl:
        a = ctx.anbieter
        env = grundumgebung()
        key_env = a.key_envs[0] if a.key_envs else "OMNI_AGENT_KEY"
        if key_env in ctx.schluessel:
            env[key_env] = ctx.schluessel[key_env]
        env["CODEX_HOME"] = str(ctx.ordner / ".codex-home")  # eigene, leere Konfiguration

        anbieter_toml = (
            '{ name = "%s", base_url = "%s", env_key = "%s", wire_api = "responses" }'
            % (a.name, ctx.base_url, key_env)
        )
        argv = [
            self.pfad() or self.binary, "exec",
            "--json", "--skip-git-repo-check",
            "--sandbox", "workspace-write",
            "--cd", str(ctx.ordner),
            "-c", f"model_provider={json.dumps(a.id)}",
            "-c", f"model_providers.{a.id}={anbieter_toml}",
            "--model", ctx.modell,
            ctx.prompt,
        ]
        return Befehl(argv=argv, env=env)

    def fortschritt(self, zeile: str, zustand: dict) -> list:
        try:
            o = json.loads(zeile)
        except ValueError:
            return [kurz(zeile, 160)] if zeile.strip() else []
        item = o.get("item") or {}
        art = item.get("type") or o.get("type") or ""
        if art in ("command_execution", "file_change", "web_search", "mcp_tool_call") and o.get("type") == "item.started":
            zustand["runden"] = zustand.get("runden", 0) + 1
            return [f"Werkzeug {zustand['runden']}: {art}"]
        if art == "agent_message" and item.get("text"):
            return [f"Agent: {kurz(item['text'])}"]
        return []
