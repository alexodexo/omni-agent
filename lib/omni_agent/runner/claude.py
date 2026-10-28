"""Runner `claude`: Claude Code im Headless-Modus (`claude -p`). Standard, am besten dokumentiert."""
import json

from .basis import Befehl, LaufKontext, Runner, grundumgebung, kurz

# neutral -> Claude-Code-Werkzeugnamen
ABBILDUNG = {
    "lesen": ("Read", "Glob", "Grep"),
    "schreiben": ("Write", "Edit"),
    "web_suche": ("WebSearch",),
    "web_laden": ("WebFetch",),
    "shell": ("Bash",),
}


class ClaudeRunner(Runner):
    name = "claude"
    binary = "claude"
    protokolle = ("anthropic",)
    kann = frozenset(ABBILDUNG)
    hinweis = "Standard. Feine Werkzeug-Freigabe, stream-json-Ausgabe."

    def baue(self, ctx: LaufKontext) -> Befehl:
        a = ctx.anbieter
        env = grundumgebung()
        env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"

        if ctx.base_url:
            # Fremdanbieter oder lokaler Übersetzer: Adresse, Zugang und ALLE Modellstufen setzen,
            # sonst scheitern Hintergrundstufen (Haiku, Subagenten) still.
            env["ANTHROPIC_BASE_URL"] = ctx.base_url
            token = next(iter(ctx.schluessel.values()), None) or a.key_platzhalter or ""
            env["ANTHROPIC_AUTH_TOKEN"] = token
            for name in a.leere_vars:
                env[name] = ""
            # Die kleine Stufe des Anbieters nur, wenn das Standardmodell läuft; ein ausdrücklich
            # gewähltes Modell gilt für alle Stufen.
            klein = a.modelle.get("klein") if ctx.modell == a.modelle.get("standard") else None
            env["ANTHROPIC_MODEL"] = ctx.modell
            env["ANTHROPIC_DEFAULT_OPUS_MODEL"] = ctx.modell
            env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = ctx.modell
            env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = klein or ctx.modell
            env["CLAUDE_CODE_SUBAGENT_MODEL"] = ctx.modell
        else:
            # Anderes Claude-Konto: Schlüssel unter seinem eigenen Namen, kein Base-URL-Eingriff.
            env.update(ctx.schluessel)
            env["ANTHROPIC_MODEL"] = ctx.modell

        tools = []
        for neutral in ctx.werkzeuge:
            tools.extend(ABBILDUNG[neutral])

        argv = [
            self.pfad() or self.binary, "-p", ctx.prompt,
            "--output-format", "stream-json", "--verbose",
            "--strict-mcp-config", "--setting-sources", "project",
            "--permission-mode", "dontAsk",
            "--no-session-persistence",
        ]
        if tools:
            argv += ["--allowed-tools", *tools]
        return Befehl(argv=argv, env=env)

    def fortschritt(self, zeile: str, zustand: dict) -> list:
        try:
            o = json.loads(zeile)
        except ValueError:
            return []
        typ = o.get("type")
        aus = []
        if typ == "system" and o.get("subtype") == "init":
            aus.append(f"Start, Modell: {o.get('model')}")
        elif typ == "assistant":
            for c in (o.get("message") or {}).get("content") or []:
                if c.get("type") == "text" and (c.get("text") or "").strip():
                    aus.append(f"Agent: {kurz(c['text'])}")
                elif c.get("type") == "tool_use":
                    zustand["runden"] = zustand.get("runden", 0) + 1
                    eingabe = c.get("input") or {}
                    detail = eingabe.get("query") or eingabe.get("url") or eingabe.get("file_path") or ""
                    aus.append(f"Werkzeug {zustand['runden']}: {c.get('name')} {kurz(detail)}")
        elif typ == "result":
            zustand["ergebnis"] = o.get("result")
            aus.append(
                f"FERTIG ({o.get('subtype')}), {o.get('num_turns')} Runden, "
                f"{(o.get('duration_ms') or 0) // 1000}s, Kosten laut CLI: ${o.get('total_cost_usd')}"
            )
        return aus
