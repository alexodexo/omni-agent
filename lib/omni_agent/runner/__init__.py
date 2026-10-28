"""Runner-Register und Passungsregel (Protokoll des Anbieters x Protokolle des Runners)."""
from ..konfig import KonfigFehler
from .basis import STANDARD_WERKZEUGE, WERKZEUGE, Runner
from .claude import ClaudeRunner
from .codex import CodexRunner
from .dsh import DshRunner
from .opencode import OpencodeRunner

RUNNER = {r.name: r for r in (ClaudeRunner(), OpencodeRunner(), CodexRunner(), DshRunner())}
AUTO_REIHENFOLGE = ("claude", "opencode", "codex")  # dsh nie automatisch


def wirksames_protokoll(anbieter, runner: Runner, ueber_litellm: bool) -> str | None:
    """Welches Protokoll Runner und Anbieter gemeinsam sprechen, oder None."""
    if ueber_litellm:
        # Der lokale Übersetzer macht aus einem OpenAI-Anbieter einen Anthropic-Endpunkt.
        if "openai-chat" in anbieter.protokolle and runner.spricht("anthropic"):
            return "anthropic"
        return None
    for protokoll in anbieter.protokolle:
        if runner.spricht(protokoll):
            return protokoll
    return None


def passt(anbieter, runner: Runner, ueber_litellm: bool = False) -> bool:
    if runner.name == "dsh" and anbieter.id != "deepseek":
        return False
    if anbieter.base_url is None and runner.name != "claude":
        return False  # Claude-Konto läuft nur über Claude Code selbst
    return wirksames_protokoll(anbieter, runner, ueber_litellm) is not None


def waehle_runner(anbieter, wunsch: str | None, ueber_litellm: bool = False) -> Runner:
    """Ohne Wunsch: erster INSTALLIERTER Runner der Reihe claude, opencode, codex, der passt."""
    if wunsch:
        if wunsch not in RUNNER:
            raise KonfigFehler(f"Unbekannter Runner '{wunsch}'. Bekannt: {', '.join(RUNNER)}")
        runner = RUNNER[wunsch]
        if not runner.pfad():
            raise KonfigFehler(f"Runner '{wunsch}' ist nicht installiert (Befehl '{runner.binary}' nicht im PATH)")
        if not passt(anbieter, runner, ueber_litellm):
            raise KonfigFehler(erklaere_unpassend(anbieter, runner, ueber_litellm))
        return runner

    installiert = [RUNNER[n] for n in AUTO_REIHENFOLGE if RUNNER[n].pfad()]
    if not installiert:
        raise KonfigFehler("Kein Runner installiert. Mindestens eine Agent-CLI nötig: claude, opencode oder codex")
    for runner in installiert:
        if passt(anbieter, runner, ueber_litellm):
            return runner
    raise KonfigFehler(
        f"Kein installierter Runner passt zu '{anbieter.id}' (Protokoll: {', '.join(anbieter.protokolle)}). "
        + erklaere_unpassend(anbieter, installiert[0], ueber_litellm)
    )


def erklaere_unpassend(anbieter, runner: Runner, ueber_litellm: bool) -> str:
    if runner.name == "dsh" and anbieter.id != "deepseek":
        return "Runner 'dsh' ist nur für den Anbieter 'deepseek' gedacht."
    if anbieter.base_url is None and runner.name != "claude":
        return f"Anbieter '{anbieter.id}' (anderes Claude-Konto) läuft nur über den Runner 'claude'."
    sprichst = ", ".join(anbieter.protokolle)
    text = f"Anbieter '{anbieter.id}' spricht {sprichst}, Runner '{runner.name}' spricht {', '.join(runner.protokolle)}."
    if "openai-chat" in anbieter.protokolle and runner.spricht("anthropic") and not ueber_litellm:
        text += " Optionen: --runner opencode, oder Claude Code über das Extra LiteLLM (--ueber-litellm)."
    elif "openai-responses" not in anbieter.protokolle and runner.name == "codex":
        text += " Codex spricht nur die Responses-API."
    else:
        text += " Wähle einen anderen Runner (omni-agent runner)."
    return text


def loese_werkzeuge(wunsch: str | None, runner: Runner) -> tuple:
    """Wandelt --werkzeuge in eine Liste neutraler Werkzeuge. Verweigert, was der Runner nicht kann.

    Ohne Angabe: Standard (ohne shell), auf das reduziert, was der Runner kann.
    Syntax: 'lesen,schreiben' ersetzt den Standard, '+shell' fügt hinzu, '-web_suche' nimmt weg.
    """
    aktuell = set(STANDARD_WERKZEUGE)
    genannt = set()  # was die Nutzerin ausdrücklich verlangt hat
    if wunsch:
        teile = [t for t in wunsch.replace(",", " ").split() if t]
        ersetzt = False
        for teil in teile:
            op, name = (teil[0], teil[1:]) if teil[0] in "+-" else ("=", teil)
            if name not in WERKZEUGE:
                raise KonfigFehler(f"Unbekanntes Werkzeug '{name}'. Bekannt: {', '.join(WERKZEUGE)}")
            if op == "=":
                if not ersetzt:
                    aktuell = set()
                    ersetzt = True
                aktuell.add(name)
                genannt.add(name)
            elif op == "+":
                aktuell.add(name)
                genannt.add(name)
            else:
                aktuell.discard(name)

    fehlt = aktuell - runner.kann
    verlangt_aber_unmoeglich = fehlt & genannt
    if verlangt_aber_unmoeglich:
        raise KonfigFehler(
            f"Runner '{runner.name}' kann {', '.join(sorted(verlangt_aber_unmoeglich))} nicht steuern. "
            f"Verweigert, statt still weniger zu tun. Kann: {', '.join(sorted(runner.kann))}"
        )
    aktuell -= fehlt  # nur Standard-Werkzeuge schrumpfen, ohne dass es jemand verlangt hat

    unverboten = runner.nicht_verbietbar - aktuell
    if unverboten:
        raise KonfigFehler(
            f"Runner '{runner.name}' hat {', '.join(sorted(unverboten))} immer. "
            f"Bitte ausdrücklich zulassen: --werkzeuge +{sorted(unverboten)[0]}"
        )
    return tuple(w for w in WERKZEUGE if w in aktuell)
