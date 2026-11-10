"""Einstiege für die Hooks des Plugins (SessionStart, SessionEnd, Stop) und der Review-Gate.

Hooks lesen ein JSON von Claude Code auf stdin. Ein Hook darf nie die Sitzung stören: jede Störung
(kein Git, kein Anbieter, Zeitüberschreitung) heißt hier „durchlassen" und eine Zeile auf stderr.
"""
import argparse
import contextlib
import hashlib
import json
import os
import signal
import sys
import tempfile
import time
from pathlib import Path

from . import review
from .konfig import KonfigFehler, home, laeufe_ordner, lese_config, review_gate_an, standard_anbieter
from .lauf import alle_laeufe, fuehre_aus, lies_status, prozess_ist_omni_agent

GATE_AUFTRAG = """Du bist der Stoppwächter einer Claude-Code-Sitzung. Prüfe die Änderungen, die Claude gerade gemacht hat (Datei aenderungen.patch, Dateiliste in geaenderte_dateien.txt, Claudes letzte Antwort in letzte_antwort.md).

Stelle in Frage, ob genau diese Arbeit und ihre Entwurfsentscheidungen so ausgeliefert werden sollten: Folgefehler, Leerzustände, Wiederholungen, veralteter Zustand, Rückgängigmachen, Rechte.

Deine erste Zeile in bericht.md muss exakt eine dieser beiden sein, davor nichts:
ALLOW: <kurzer Grund>
BLOCK: <kurzer Grund>

Nutze ALLOW, wenn du keinen Fehler siehst, der vor dem Beenden behoben werden muss. Nutze BLOCK nur bei einem belegbaren Fehler im Diff, den du mit Datei und Stelle nennst. Du siehst nur den Diff: Was vom unsichtbaren Kontext abhängt, ist kein Grund zu blockieren. Erfinde nichts. Ändere nichts am Code.
"""

MAX_GATE_ZEICHEN = 150_000
MAX_BLOCKS_JE_SITZUNG = 3


def lies_eingabe() -> dict:
    try:
        roh = sys.stdin.read().strip()
        return json.loads(roh) if roh else {}
    except (OSError, ValueError):
        return {}


def _shell_quote(wert: str) -> str:
    return "'" + str(wert).replace("'", "'\"'\"'") + "'"


def hook_start(eingabe: dict) -> int:
    """Macht die Sitzungs-ID für alle Bash-Befehle dieser Sitzung (auch die der Subagenten) als Umgebungsvariable sichtbar."""
    datei = os.environ.get("CLAUDE_ENV_FILE")
    sitzung = eingabe.get("session_id")
    if datei and sitzung:
        with open(datei, "a", encoding="utf-8") as f:
            f.write(f"export OMNI_AGENT_SITZUNG={_shell_quote(sitzung)}\n")
    return 0


def laufende_dieser_sitzung(sitzung: str | None) -> list:
    if not sitzung:
        return []
    return [p for p in alle_laeufe(sitzung) if (lies_status(p) or {}).get("zustand") == "arbeitet"]


def hook_ende(eingabe: dict) -> int:
    """Beendet Läufe, die in dieser Sitzung gestartet wurden und noch arbeiten (kein Waisen-Lauf auf Kosten der Nutzerin).
    Bei /clear laufen sie weiter, die Sitzung geht ja gleich weiter. Berichte bleiben liegen."""
    if eingabe.get("reason") == "clear":
        return 0
    for ordner in laufende_dieser_sitzung(eingabe.get("session_id") or os.environ.get("OMNI_AGENT_SITZUNG")):
        pid = (lies_status(ordner) or {}).get("pid")
        if prozess_ist_omni_agent(pid):
            with contextlib.suppress(OSError, ValueError):
                os.kill(int(pid), signal.SIGTERM)
    return 0


# ---------- Review-Gate ----------

def _gate_datei() -> Path:
    return home() / "gate.json"


def _lies_gate() -> dict:
    try:
        daten = json.loads(_gate_datei().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return daten if isinstance(daten, dict) else {}


def _schreibe_gate(daten: dict) -> None:
    home().mkdir(parents=True, exist_ok=True)
    tmp = _gate_datei().with_suffix(".tmp")
    tmp.write_text(json.dumps(daten) + "\n", encoding="utf-8")
    os.replace(tmp, _gate_datei())


def _notiz(text: str) -> None:
    print(text, file=sys.stderr)


def pruefe_gate(eingabe: dict) -> tuple:
    """Gibt (blockieren, grund) zurück. Teuer nur, wenn sich der Diff seit der letzten Prüfung geändert hat."""
    sitzung = eingabe.get("session_id") or "ohne-sitzung"
    anbieter = lese_config().get("review_gate_anbieter") or standard_anbieter()
    if not anbieter:
        _notiz("Review-Gate an, aber kein Anbieter: omni-agent konto standard NAME (oder config review_gate_anbieter).")
        return False, ""
    cwd = eingabe.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    os.chdir(cwd)
    try:
        daten = review.sammle(None, nur_arbeitsbaum=True)
        if not daten["diff"].strip():
            return False, ""
        review.pruefe(daten, trotzdem=False)  # wirft bei Geheimnissen oder zu großem Diff
    except KonfigFehler as fehler:
        _notiz(f"Review-Gate übersprungen: {fehler}")
        return False, ""
    if len(daten["diff"]) > MAX_GATE_ZEICHEN:
        _notiz(f"Review-Gate übersprungen: Diff über {MAX_GATE_ZEICHEN // 1000} KB.")
        return False, ""

    fingerabdruck = hashlib.sha256(daten["diff"].encode("utf-8")).hexdigest()
    zustand = _lies_gate()
    mein = zustand.get(sitzung, {})
    if mein.get("diff") == fingerabdruck:
        return False, ""  # diesen Stand haben wir schon geprüft: kein zweites Mal blockieren, keine Schleife
    if int(mein.get("blocks") or 0) >= MAX_BLOCKS_JE_SITZUNG:
        _notiz("Review-Gate: Blockadegrenze dieser Sitzung erreicht, lasse durch.")
        return False, ""

    lauf_ordner = laeufe_ordner() / (time.strftime("%Y%m%d-%H%M%S") + f"-{os.getpid()}-gate")
    with tempfile.TemporaryDirectory() as material:
        (Path(material) / "aenderungen.patch").write_text(daten["diff"], encoding="utf-8")
        (Path(material) / "geaenderte_dateien.txt").write_text(daten["namen"], encoding="utf-8")
        (Path(material) / "letzte_antwort.md").write_text(str(eingabe.get("last_assistant_message") or "(nicht übermittelt)"), encoding="utf-8")
        args = argparse.Namespace(
            auftrag=None, text=GATE_AUFTRAG, anbieter=anbieter, modell=lese_config().get("review_gate_modell"), runner=None, werkzeuge="lesen,schreiben",
            max_runden=8, zeit=600, ordner=str(lauf_ordner), material=material, ueber_litellm=False, fortsetzen=None,
            aufwand=None, projekt=None, schreibend=False, art="gate",
        )
        try:
            with open(os.devnull, "w") as stumm, contextlib.redirect_stdout(stumm), contextlib.redirect_stderr(stumm):
                code = fuehre_aus(args)
        except KonfigFehler as fehler:
            _notiz(f"Review-Gate übersprungen: {fehler}")
            return False, ""
    bericht = lauf_ordner / "bericht.md"
    erste = ""
    if code == 0 and bericht.is_file():
        erste = (bericht.read_text(encoding="utf-8").strip().splitlines() or [""])[0].strip()
    zustand[sitzung] = {"diff": fingerabdruck, "blocks": int(mein.get("blocks") or 0)}
    if erste.startswith("BLOCK:"):
        zustand[sitzung]["blocks"] += 1
        _schreibe_gate(zustand)
        return True, f"Das Review-Gate (Omni-Agent, {anbieter}) hat Probleme gefunden, die vor dem Beenden zu beheben sind: {erste[6:].strip()}"
    _schreibe_gate(zustand)
    if not erste.startswith("ALLOW:"):
        _notiz("Review-Gate: unklare oder fehlende Antwort, lasse durch.")
    return False, ""


def hook_stopp(eingabe: dict) -> int:
    notiz = ""
    laufende = laufende_dieser_sitzung(eingabe.get("session_id"))
    if laufende:
        notiz = f"Omni-Agent: {len(laufende)} Lauf/Läufe dieser Sitzung arbeiten noch (omni-agent status; Abbrechen: omni-agent cancel)."
        _notiz(notiz)
    if not review_gate_an():
        return 0
    try:
        blockieren, grund = pruefe_gate(eingabe)
    except Exception as fehler:  # ein Hook darf die Sitzung nie festhalten
        _notiz(f"Review-Gate übersprungen ({fehler.__class__.__name__}: {fehler})")
        return 0
    if blockieren:
        print(json.dumps({"decision": "block", "reason": (notiz + " " if notiz else "") + grund}, ensure_ascii=False))
    return 0


def fuehre_haken_aus(name: str) -> int:
    if os.environ.get("OMNI_AGENT_LAUF") == "1":
        return 0  # wir stecken selbst in einem Omni-Agent-Lauf: nichts tun, keine Schleife
    eingabe = lies_eingabe()
    if name == "start":
        return hook_start(eingabe)
    if name == "ende":
        return hook_ende(eingabe)
    if name == "stopp":
        return hook_stopp(eingabe)
    print(f"Unbekannter Hook '{name}'", file=sys.stderr)
    return 0
