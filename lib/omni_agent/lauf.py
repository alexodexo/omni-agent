"""Einen Auftrag ausführen: Anbieter + Runner wählen, starten, überwachen, Ergebnis festhalten."""
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from . import extras
from .anbieter import hole_anbieter
from .konfig import (
    EXIT_LAUF, EXIT_OK, EXIT_ZEIT, KonfigFehler, hole_schluessel, laeufe_ordner,
    lese_schluesseldatei, pruefe_erreichbar,
)
from .runner import loese_werkzeuge, waehle_runner, wirksames_protokoll
from .runner.basis import LaufKontext

RAHMEN = """Du arbeitest als Hintergrund-Agent in einem leeren Arbeitsordner (dein aktuelles Verzeichnis).
Regeln, die vor dem Auftrag gelten:
1. Schreibe dein Ergebnis als Markdown in die Datei bericht.md in diesem Ordner. Erst wenn bericht.md existiert, gilt der Auftrag als erledigt.
2. Benutze höchstens {max_runden} Werkzeugaufrufe. Danach schreibst du bericht.md mit dem, was du hast.
3. Behauptungen ohne Beleg kennzeichnest du als "nicht belegt". Quellen nennst du mit URL.
4. Lies und schreibe nichts außerhalb dieses Ordners.

Auftrag:
"""


def schreibe_status(ordner: Path, **felder) -> None:
    """Atomar schreiben, damit Mitleser (Statusanzeigen) nie eine halbe Datei sehen."""
    pfad = ordner / "status.json"
    tmp = ordner / ".status.json.tmp"
    tmp.write_text(json.dumps(felder, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, pfad)


def schwaerze(text: str, geheimnisse: list) -> str:
    for g in geheimnisse:
        text = text.replace(g, "***")
    return text


def neuer_laufordner(anbieter_id: str, ordner_wunsch: str | None) -> Path:
    if ordner_wunsch:
        pfad = Path(ordner_wunsch).expanduser().resolve()
        if pfad.exists() and any(pfad.iterdir()):
            raise KonfigFehler(f"Arbeitsordner {pfad} ist nicht leer. Der Agent bekommt nur einen leeren Ordner.")
        pfad.mkdir(parents=True, exist_ok=True)
        return pfad
    basis = laeufe_ordner()
    basis.mkdir(parents=True, exist_ok=True)
    os.chmod(basis.parent, 0o700)
    stempel = datetime.now().strftime("%Y%m%d-%H%M%S")
    pfad = basis / f"{stempel}-{anbieter_id}"
    zaehler = 1
    while pfad.exists():
        zaehler += 1
        pfad = basis / f"{stempel}-{anbieter_id}-{zaehler}"
    pfad.mkdir()
    return pfad


def finde_schluessel(anbieter) -> dict:
    """Genau den einen Schlüssel, den dieser Lauf braucht. Wert nie ausgeben."""
    if not anbieter.braucht_schluessel:
        return {}
    datei = lese_schluesseldatei()
    for name in anbieter.key_envs:
        wert = hole_schluessel(name, datei)
        if wert:
            return {name: wert}
    from .konfig import env_datei
    raise KonfigFehler(
        f"Schlüssel fehlt: {' oder '.join(anbieter.key_envs)}. "
        f"Als Umgebungsvariable setzen oder in {env_datei()} eintragen (Zeile NAME=wert, Rechte 600). "
        f"Hilfe: omni-agent setup --anbieter {anbieter.id}"
    )


def fuehre_aus(args) -> int:
    anbieter = hole_anbieter(args.anbieter)
    runner = waehle_runner(anbieter, args.runner, args.ueber_litellm)
    protokoll = wirksames_protokoll(anbieter, runner, args.ueber_litellm)
    modell = anbieter.modell_waehlen(args.modell)
    werkzeuge = loese_werkzeuge(args.werkzeuge, runner)
    schluessel = finde_schluessel(anbieter)
    geheimnisse = [w for w in schluessel.values() if len(w) >= 8]

    if args.text is not None:
        auftrag_text = args.text
    else:
        quelle = Path(args.auftrag).expanduser()
        if not quelle.is_file():
            raise KonfigFehler(f"Auftragsdatei nicht gefunden: {quelle}")
        auftrag_text = quelle.read_text(encoding="utf-8")
    if not auftrag_text.strip():
        raise KonfigFehler("Der Auftrag ist leer")

    base_url = anbieter.base_url
    if args.ueber_litellm:
        key_wert = next(iter(schluessel.values()), "")
        base_url, master = extras.starte_proxy(anbieter, modell, key_wert)
        schluessel = {"LITELLM_MASTER_KEY": master}
        geheimnisse.append(master)
    elif base_url:
        pruefe_erreichbar(base_url)

    ordner = neuer_laufordner(anbieter.id, args.ordner)
    (ordner / "auftrag.md").write_text(auftrag_text, encoding="utf-8")
    if args.material:
        material = Path(args.material).expanduser()
        if not material.is_dir():
            raise KonfigFehler(f"Materialordner nicht gefunden: {material}")
        shutil.copytree(material, ordner, dirs_exist_ok=True)

    prompt = RAHMEN.format(max_runden=args.max_runden) + auftrag_text
    ctx = LaufKontext(
        prompt=prompt, ordner=ordner, anbieter=anbieter, modell=modell, base_url=base_url,
        protokoll=protokoll, schluessel=schluessel, werkzeuge=werkzeuge, max_runden=args.max_runden,
    )
    befehl = runner.baue(ctx)

    start = int(time.time())
    kopf = dict(runner=runner.name, anbieter=anbieter.id, modell=modell, lauf=str(ordner), start=start)
    schreibe_status(ordner, zustand="arbeitet", **kopf)
    print(f"Omni-Agent: {anbieter.id} / {modell} über {runner.name}, Werkzeuge: {', '.join(werkzeuge) or 'keine'}", flush=True)
    print(f"Lauf: {ordner}", flush=True)
    if runner.experimentell:
        print(f"ACHTUNG: Runner '{runner.name}' ist experimentell.", flush=True)

    zustand = {"runden": 0}
    flags = {"abgebrochen": False, "zeit": False, "rundenlimit": False}
    rundenlimit = max(args.max_runden * 2, args.max_runden + 10)

    proc = subprocess.Popen(
        befehl.argv, cwd=ordner, env=befehl.env,
        stdin=subprocess.PIPE if befehl.stdin_text is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace",
        start_new_session=True,
    )

    def beende_gruppe() -> None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            time.sleep(2)
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    def bei_signal(signum, _frame):
        flags["abgebrochen"] = True
        threading.Thread(target=beende_gruppe, daemon=True).start()

    alte = {s: signal.signal(s, bei_signal) for s in (signal.SIGINT, signal.SIGTERM)}

    def zeitwaechter():
        if proc.poll() is None:
            flags["zeit"] = True
            beende_gruppe()

    timer = threading.Timer(args.zeit, zeitwaechter)
    timer.daemon = True
    timer.start()

    def lies_stderr():
        with open(ordner / "fehler.log", "w", encoding="utf-8") as f:
            for zeile in proc.stderr:
                f.write(schwaerze(zeile, geheimnisse))

    t_err = threading.Thread(target=lies_stderr, daemon=True)
    t_err.start()
    if befehl.stdin_text is not None:
        proc.stdin.write(befehl.stdin_text)
        proc.stdin.close()

    beginn = time.time()
    with open(ordner / "log.jsonl", "w", encoding="utf-8") as log:
        for zeile in proc.stdout:
            sauber = schwaerze(zeile, geheimnisse)
            log.write(sauber)
            log.flush()
            for meldung in runner.fortschritt(sauber, zustand):
                print(f"[{int(time.time() - beginn):>4}s] {meldung}", flush=True)
            if zustand["runden"] > rundenlimit and not flags["rundenlimit"]:
                flags["rundenlimit"] = True
                print(f"Rundenlimit überschritten ({zustand['runden']} > {rundenlimit}), Lauf wird beendet.", flush=True)
                threading.Thread(target=beende_gruppe, daemon=True).start()
    exitcode = proc.wait()
    t_err.join(timeout=5)
    timer.cancel()
    for s, h in alte.items():
        signal.signal(s, h)
    # Reste der Prozessgruppe (Kindprozesse) aufräumen
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass

    bericht = ordner / "bericht.md"
    fertig = bericht.is_file() and bericht.stat().st_size > 0
    if fertig:
        endzustand, code = "fertig", EXIT_OK
    elif flags["abgebrochen"]:
        endzustand, code = "abgebrochen", EXIT_LAUF
    elif flags["zeit"]:
        endzustand, code = "fehler", EXIT_ZEIT
    else:
        endzustand, code = "fehler", EXIT_LAUF

    bemerkung = None
    if flags["zeit"] and not fertig:
        bemerkung = f"Zeitlimit {args.zeit}s erreicht"
    elif flags["rundenlimit"]:
        bemerkung = "Rundenlimit überschritten"
    schreibe_status(
        ordner, zustand=endzustand, ende=int(time.time()), exitcode=exitcode,
        runden=zustand["runden"], bemerkung=bemerkung, **kopf,
    )
    print(f"Lauf: {ordner}", flush=True)
    if fertig:
        print(f"Bericht: {bericht}", flush=True)
    else:
        print(f"Kein bericht.md entstanden ({bemerkung or 'Runner-Exit ' + str(exitcode)}). Siehe log.jsonl und fehler.log im Laufordner.", file=sys.stderr, flush=True)
    return code
