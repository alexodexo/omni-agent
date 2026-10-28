"""Runner `opencode`: spricht OpenAI-kompatible Anbieter selbst, ohne Übersetzer.

Stand: laut Herstellerdoku gebaut, NICHT live geprüft (opencode war nicht installiert).
Zwei Versionslinien existieren, Exit-Codes sind nicht dokumentiert: der Fertig-Beweis ist bericht.md.
"""
import json

from .basis import Befehl, LaufKontext, Runner, grundumgebung, kurz


class OpencodeRunner(Runner):
    name = "opencode"
    binary = "opencode"
    protokolle = ("openai-chat", "openai-responses", "anthropic")
    kann = frozenset({"lesen", "schreiben", "web_suche", "web_laden", "shell"})
    hinweis = "Zweite Wahl. Spricht OpenAI-Formate direkt (EUrouter, Nvidia). Nicht live geprüft."

    def baue(self, ctx: LaufKontext) -> Befehl:
        a = ctx.anbieter
        env = grundumgebung()
        key_env = a.key_envs[0] if a.key_envs else None
        if key_env and key_env in ctx.schluessel:
            env[key_env] = ctx.schluessel[key_env]

        npm = "@ai-sdk/anthropic" if ctx.protokoll == "anthropic" else "@ai-sdk/openai-compatible"
        optionen = {"baseURL": ctx.base_url}
        if key_env:
            optionen["apiKey"] = "{env:%s}" % key_env
        erlaubt = set(ctx.werkzeuge)
        konfig = {
            "$schema": "https://opencode.ai/config.json",
            "autoupdate": False,
            "share": "disabled",
            "provider": {a.id: {"npm": npm, "name": a.name, "options": optionen, "models": {ctx.modell: {"name": ctx.modell}}}},
            "permission": {
                "read": "allow" if "lesen" in erlaubt else "deny",
                "list": "allow" if "lesen" in erlaubt else "deny",
                "glob": "allow" if "lesen" in erlaubt else "deny",
                "grep": "allow" if "lesen" in erlaubt else "deny",
                "edit": "allow" if "schreiben" in erlaubt else "deny",
                "bash": "allow" if "shell" in erlaubt else "deny",
                "webfetch": "allow" if "web_laden" in erlaubt else "deny",
                "websearch": "allow" if "web_suche" in erlaubt else "deny",
                "external_directory": "deny",
            },
        }
        env["OPENCODE_CONFIG_CONTENT"] = json.dumps(konfig)
        argv = [self.pfad() or self.binary, "run", "--format", "json", "--model", f"{a.id}/{ctx.modell}", ctx.prompt]
        return Befehl(argv=argv, env=env)

    def fortschritt(self, zeile: str, zustand: dict) -> list:
        try:
            o = json.loads(zeile)
        except ValueError:
            return [kurz(zeile, 160)] if zeile.strip() else []
        typ = str(o.get("type", ""))
        if "tool" in typ:
            zustand["runden"] = zustand.get("runden", 0) + 1
            teil = o.get("part") or {}
            return [f"Werkzeug {zustand['runden']}: {teil.get('tool') or typ}"]
        if typ == "text":
            text = (o.get("part") or {}).get("text") or ""
            return [f"Agent: {kurz(text)}"] if text.strip() else []
        return []
