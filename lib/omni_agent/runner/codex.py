"""Runner `codex`: OpenAI Codex CLI (`codex exec`). Spricht nur die Responses-API.

Zwei Arten:
- Anbieter `codex` (konto_art "login"): die Anmeldung der Codex-CLI selbst (ChatGPT-Konto oder API-Schlüssel
  aus `codex login`). Live geprüft mit dem ChatGPT-Konto. Die persönliche config.toml und die Regeln des
  Nutzers werden NICHT geladen (--ignore-user-config, --ignore-rules), nur die Anmeldung wird benutzt.
- Fremdanbieter mit Responses-API (z. B. EUrouter): eigene, leere CODEX_HOME. Nicht live geprüft.

Codex kann keine einzelnen Werkzeuge verbieten, seine Shell ist immer da (nur durch die Sandbox begrenzt).
Darum verlangt der Kern hier ausdrücklich `--werkzeuge +shell`.
"""
import json
import os
import shutil

from .basis import Befehl, LaufKontext, Runner, grundumgebung, kurz


class CodexRunner(Runner):
    name = "codex"
    binary = "codex"
    protokolle = ("openai-responses",)
    kann = frozenset({"lesen", "schreiben", "shell"})
    nicht_verbietbar = frozenset({"shell"})
    in_sandbox = True  # --sandbox workspace-write: Schreiben nur im Laufordner, kein Netz
    hinweis = "Nur Responses-API. Shell ist immer da (Sandbox workspace-write). Mit Anbieter 'codex' (Anmeldung) live geprüft."

    # Orte, an denen Codex liegt, ohne im PATH zu stehen (z. B. mit der ChatGPT-App geliefert)
    ORTE = (
        "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex",
        "/Applications/Codex.app/Contents/Resources/codex",
    )

    def pfad(self) -> str | None:
        if os.environ.get("OMNI_AGENT_CODEX") and os.access(os.environ["OMNI_AGENT_CODEX"], os.X_OK):
            return os.environ["OMNI_AGENT_CODEX"]
        gefunden = shutil.which(self.binary)
        if gefunden:
            return gefunden
        for ort in self.ORTE:
            if os.access(ort, os.X_OK):
                return ort
        return None

    def baue(self, ctx: LaufKontext) -> Befehl:
        a = ctx.anbieter
        env = grundumgebung()
        exe = self.pfad() or self.binary
        sitzung = ctx.extra.get("fortsetzen")
        aufwand = ctx.extra.get("aufwand")
        optionen = ["--json", "--skip-git-repo-check"]
        # `resume` kennt weder --sandbox noch --cd: gleiche Wirkung über -c, Ordner ist das aktuelle Verzeichnis
        optionen += ["-c", 'sandbox_mode="workspace-write"'] if sitzung else ["--sandbox", "workspace-write"]

        if a.konto_art == "login":
            # Anmeldung der CLI selbst; eigene Einstellungen und Regeln des Nutzers bleiben draußen.
            if os.environ.get("CODEX_HOME"):
                env["CODEX_HOME"] = os.environ["CODEX_HOME"]
            optionen += ["--ignore-user-config", "--ignore-rules"]
            modell_optionen = ["--model", ctx.modell]
        else:
            key_env = a.key_envs[0] if a.key_envs else "OMNI_AGENT_KEY"
            if key_env in ctx.schluessel:
                env[key_env] = ctx.schluessel[key_env]
            env["CODEX_HOME"] = str(ctx.ordner / ".codex-home")  # eigene, leere Konfiguration
            anbieter_toml = (
                '{ name = "%s", base_url = "%s", env_key = "%s", wire_api = "responses" }'
                % (a.name, ctx.base_url, key_env)
            )
            optionen += ["-c", f"model_provider={json.dumps(a.id)}", "-c", f"model_providers.{a.id}={anbieter_toml}"]
            modell_optionen = ["--model", ctx.modell]
        if aufwand:
            optionen += ["-c", f"model_reasoning_effort={json.dumps(aufwand)}"]

        if sitzung:
            argv = [exe, "exec", "resume", *optionen, *modell_optionen, sitzung, ctx.prompt]
        else:
            argv = [exe, "exec", *optionen, "--cd", str(ctx.ordner), *modell_optionen, ctx.prompt]
        return Befehl(argv=argv, env=env)

    def fortschritt(self, zeile: str, zustand: dict) -> list:
        try:
            o = json.loads(zeile)
        except ValueError:
            return [kurz(zeile, 160)] if zeile.strip() else []
        if o.get("type") == "thread.started" and o.get("thread_id"):
            zustand["sitzung"] = o["thread_id"]
            return []
        item = o.get("item") or {}
        art = item.get("type") or o.get("type") or ""
        if art in ("command_execution", "file_change", "web_search", "mcp_tool_call") and o.get("type") == "item.started":
            zustand["runden"] = zustand.get("runden", 0) + 1
            return [f"Werkzeug {zustand['runden']}: {art}"]
        if art == "agent_message" and item.get("text"):
            return [f"Agent: {kurz(item['text'])}"]
        return []
