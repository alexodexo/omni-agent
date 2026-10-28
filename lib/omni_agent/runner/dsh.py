"""Runner `dsh`: DeepSeek Harness (`@deepseek-ai/dsh`). EXPERIMENTELL, wird nie automatisch gewählt.

Die Developer Preview (0.1.x, mit angekündigten Brüchen) ist per `dsh --profile headless "<Aufgabe>"` aufrufbar.
Wie das Profil seinen Schlüssel liest, ist nicht dokumentiert; Omni-Agent reicht DEEPSEEK_API_KEY durch und
verlässt sich auf bericht.md als einzigen Fertig-Beweis.
"""
from .basis import Befehl, LaufKontext, Runner, grundumgebung, kurz


class DshRunner(Runner):
    name = "dsh"
    binary = "dsh"
    protokolle = ("anthropic", "openai-chat")
    kann = frozenset({"lesen", "schreiben", "shell"})
    nicht_verbietbar = frozenset({"shell"})
    experimentell = True
    hinweis = "EXPERIMENTELL (Developer Preview). Nur nach ausdrücklicher Wahl mit --runner dsh. Nur DeepSeek-Anbieter."

    def baue(self, ctx: LaufKontext) -> Befehl:
        env = grundumgebung()
        env.update(ctx.schluessel)
        argv = [self.pfad() or self.binary, "--profile", "headless", ctx.prompt]
        return Befehl(argv=argv, env=env)

    def fortschritt(self, zeile: str, zustand: dict) -> list:
        return [kurz(zeile, 160)] if zeile.strip() else []
