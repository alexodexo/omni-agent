"""Kommandozeile: omni-agent setup | doctor | run | status | anbieter | runner | extras."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from . import VERSION, extras
from .anbieter import lade_anbieter
from .konfig import (
    EXIT_KONFIG, KonfigFehler, WURZEL, claude_sitzung, review_gate_an, setze_config, setze_standard_anbieter, standard_anbieter,
    env_datei, hole_schluessel, home, lese_schluesseldatei, pruefe_erreichbar,
)
from .lauf import (
    alle_laeufe, dauer_text, drucke_bericht, finde_lauf, fuehre_aus, laeufe_im_blick, lies_status, melde, pruefe_lebt,
    prozess_ist_omni_agent, starte_losgeloest, warte_und_melde,
)
from .runner import RUNNER, passt

SHIM_MARKE = "omni-agent-shim"
SHIM = """#!/usr/bin/env python3
# omni-agent-shim: findet die installierte Plugin-Version, auch nach Updates (Aufruf ändert sich nie)
import glob, json, os, sys
home = os.path.expanduser("~")
ziel = None
try:
    with open(os.path.join(home, ".claude", "plugins", "installed_plugins.json"), encoding="utf-8") as f:
        for eintrag in json.load(f).get("plugins", {}).get("omni-agent@omni-agent", []):
            kandidat = os.path.join(eintrag["installPath"], "bin", "omni-agent")
            if os.path.isfile(kandidat):
                ziel = kandidat
except (OSError, ValueError, KeyError, TypeError):
    pass
if ziel is None:
    treffer = glob.glob(os.path.join(home, ".claude", "plugins", "cache", "omni-agent", "omni-agent", "*", "bin", "omni-agent"))
    ziel = max(treffer, key=os.path.getmtime) if treffer else None
if ziel is None:
    sys.exit("omni-agent: Plugin nicht gefunden. Installieren: claude plugin install omni-agent@omni-agent")
os.execv(sys.executable, [sys.executable, ziel] + sys.argv[1:])
"""

ENV_VORLAGE = """# Omni-Agent: Schlüssel. Eine Zeile je Anbieter, Format NAME=wert, keine Anführungszeichen nötig.
# Diese Datei bleibt auf deinem Rechner (Rechte 600). Nie in Git, nie in einen Chat kopieren.
# Alternativ die Variable in der Shell setzen (export NAME=wert), die Umgebung hat Vorrang.
#
# DEEPSEEK_API_KEY=
# OPENROUTER_API_KEY=
# MOONSHOT_API_KEY=
# EUROUTER_API_KEY=
# NVIDIA_API_KEY=
# ANTHROPIC_API_KEY=            # Claude mit anderem Konto (empfohlen: API-Schlüssel)
# CLAUDE_CODE_OAUTH_TOKEN=      # Abo-Token: Bedingungen für unbeaufsichtigte Läufe nicht belegt
# Ollama (lokal) braucht keinen Schlüssel.
"""


# ---------- doctor ----------

def _login_status(anbieter) -> str:
    """Anmeldung der Agent-CLI (z. B. `codex login status`). Kein Geheimnis wird gelesen oder gezeigt."""
    runner = RUNNER.get(anbieter.runner_zwang or "")
    exe = runner.pfad() if runner else None
    if not exe:
        return "CLI fehlt"
    try:
        erg = subprocess.run([exe, "login", "status"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return "unbekannt"
    return "angemeldet" if erg.returncode == 0 and "logged in" in (erg.stdout + erg.stderr).lower() else "NICHT angemeldet"


def cmd_doctor(args) -> int:
    ok = True
    print(f"Omni-Agent {VERSION}, Python {sys.version_info.major}.{sys.version_info.minor}, Ordner {home()}")
    pfad = env_datei()
    if pfad.exists():
        zu_offen = bool(pfad.stat().st_mode & 0o077)
        print(f"Schlüsseldatei: {pfad} ({'RECHTE ZU OFFEN, chmod 600' if zu_offen else 'Rechte ok'})")
        ok = ok and not zu_offen
    else:
        print(f"Schlüsseldatei: fehlt ({pfad}). Anlegen mit: omni-agent setup")
    try:
        datei = lese_schluesseldatei()
    except KonfigFehler as fehler:
        print(f"  {fehler}")
        datei, ok = {}, False

    print("\nRunner (Agent-CLIs):")
    for r in RUNNER.values():
        v = r.version()
        marke = "EXPERIMENTELL, " if r.experimentell else ""
        print(f"  {r.name:<9} {'installiert ' + str(v) if v else 'nicht installiert':<42} {marke}spricht {', '.join(r.protokolle)}")
    if not any(r.pfad() for r in RUNNER.values() if not r.experimentell):
        print("  -> Mindestens eine Agent-CLI installieren (Standard: Claude Code).")
        ok = False

    print("\nAnbieter:")
    anbieter = lade_anbieter()
    print(f"  {'Anbieter':<14}{'Schlüssel':<13}{'Region':<20}{'geprüft':<9}passende Runner")
    for a in anbieter.values():
        if a.konto_art == "login":
            key = _login_status(a)
        elif not a.braucht_schluessel:
            key = "nicht nötig"
        else:
            key = "gesetzt" if any(hole_schluessel(n, datei) for n in a.key_envs) else "fehlt"
        passende = [n for n, r in RUNNER.items() if passt(a, r)]
        via = [n for n, r in RUNNER.items() if passt(a, r, True) and n not in passende]
        zeile = ", ".join(passende) or "-"
        if via:
            zeile += f"  (+ {', '.join(via)} über LiteLLM)"
        installiert = [n for n in passende if RUNNER[n].pfad()]
        zeile += "" if installiert else "   [keiner davon installiert]"
        print(f"  {a.id:<14}{key:<13}{a.region:<20}{'ja' if a.geprueft else 'nein':<9}{zeile}")
        if args.netz and a.base_url and (key != "fehlt"):
            try:
                pruefe_erreichbar(a.base_url, 4)
                print(f"      Endpunkt erreichbar: {a.base_url}")
            except KonfigFehler as fehler:
                print(f"      Endpunkt NICHT erreichbar: {fehler}")
    print(f"\nReview-Gate: {'AN' if review_gate_an() else 'aus'} | Standard-Anbieter: {standard_anbieter() or 'keiner'} | Claude-Sitzung: {claude_sitzung() or 'nicht erkannt (Hook läuft nur in Claude Code)'}")
    print(f"\n{extras.status_text()}")
    print("\nHinweis: 'geprüft: nein' heißt laut Herstellerdoku gebaut, nicht live ausprobiert. Datenort je Anbieter: omni-agent anbieter")
    return 0 if ok else EXIT_KONFIG


# ---------- setup ----------

def cmd_setup(args) -> int:
    basis = home()
    basis.mkdir(parents=True, exist_ok=True)
    os.chmod(basis, 0o700)
    datei = env_datei()
    if not datei.exists():
        fd = os.open(datei, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(ENV_VORLAGE)
        print(f"Schlüsseldatei angelegt: {datei} (Rechte 600)")
    else:
        os.chmod(datei, 0o600)
        print(f"Schlüsseldatei vorhanden: {datei}")

    bin_ziel = Path.home() / ".local" / "bin"
    link = bin_ziel / "omni-agent"
    vorhanden = shutil.which("omni-agent")
    unsere_datei = link.is_symlink() or (link.is_file() and SHIM_MARKE in link.read_text(encoding="utf-8", errors="ignore"))
    if unsere_datei or not vorhanden:
        try:
            bin_ziel.mkdir(parents=True, exist_ok=True)
            if link.is_symlink() or link.exists():
                link.unlink()
            link.write_text(SHIM, encoding="utf-8")
            os.chmod(link, 0o755)
            print(f"Befehl eingerichtet: {link} (folgt automatisch der installierten Plugin-Version)")
            if str(bin_ziel) not in os.environ.get("PATH", "").split(os.pathsep):
                print(f"Hinweis: {bin_ziel} ist nicht im PATH. In die Shell-Konfiguration: export PATH=\"$HOME/.local/bin:$PATH\"")
        except OSError as fehler:
            print(f"Befehl konnte nicht eingerichtet werden ({fehler}). Direkt aufrufen: {WURZEL / 'bin' / 'omni-agent'}")
    else:
        print(f"Befehl 'omni-agent' ist im PATH: {vorhanden}")

    if args.anbieter:
        a = lade_anbieter().get(args.anbieter)
        if not a:
            raise KonfigFehler(f"Unbekannter Anbieter '{args.anbieter}'")
        print(f"\nAnbieter {a.name} ({a.id})")
        if a.braucht_schluessel:
            print(f"  1. Öffne {datei} in deinem Editor (nicht im Chat).")
            print(f"  2. Trage eine Zeile ein:  {a.key_envs[0]}=dein-schlüssel")
            print(f"  3. Prüfen: omni-agent doctor")
        else:
            print("  Kein Schlüssel nötig. Läuft der Dienst? Prüfen: omni-agent doctor --netz")
        print(f"  Datenort: {a.region}. {a.hinweis}")
    else:
        print("\nNächste Schritte:\n  1. Anbieter wählen (omni-agent anbieter) und Schlüssel in die Datei eintragen: omni-agent setup --anbieter deepseek")
        print("  2. Prüfen: omni-agent doctor")
        print("  3. Erster Lauf: omni-agent run --text \"Fasse in drei Sätzen zusammen, was ein Hintergrund-Agent ist\" --anbieter deepseek")
    if args.review_gate == "an":
        if not standard_anbieter():
            raise KonfigFehler("Review-Gate braucht einen Anbieter: erst `omni-agent konto standard NAME` setzen.")
        setze_config("review_gate", True)
        print(f"Review-Gate AN: Vor dem Beenden einer Claude-Sitzung wird jeder neue Diff ungeprüfter Änderungen an {standard_anbieter()} gesendet "
              "(Kosten und Datenabfluss beachten). Aus: omni-agent setup --review-gate aus")
    elif args.review_gate == "aus":
        setze_config("review_gate", None)
        print("Review-Gate AUS.")
    if args.oeffnen:
        os.system(f"open -t {datei}" if sys.platform == "darwin" else f"${{EDITOR:-nano}} {datei}")
    print()
    return cmd_doctor(argparse.Namespace(netz=False))


# ---------- run ----------

def cmd_run(args) -> int:
    if args.konto and args.anbieter:
        raise KonfigFehler("--konto und --anbieter schließen sich aus.")
    if args.konto:
        from .konten import konto_id
        args.anbieter = konto_id(args.konto)
    if not args.anbieter and args.fortsetzen is None:
        args.anbieter = standard_anbieter()
        if not args.anbieter:
            raise KonfigFehler(
                "Kein Anbieter angegeben und kein Standard gesetzt. Entweder --anbieter/--konto nennen "
                "oder einen Standard festlegen: omni-agent konto standard NAME"
            )
        print(f"Kein Anbieter angegeben, Standard: {args.anbieter}")
    if args.fortsetzen is not None and args.text is None and not args.auftrag:
        raise KonfigFehler("--fortsetzen braucht die Nachfrage: --text \"…\"")
    if args.hintergrund or args.warten is not None:
        return starte_losgeloest(_ohne_flags(args._argv), args.warten)
    return fuehre_aus(args)


def _ohne_flags(argv: list) -> list:
    """Die Argumente des Befehls ohne --hintergrund/--warten (für den losgelösten Kindprozess)."""
    aus, i = [], 0
    while i < len(argv):
        a = argv[i]
        if a == "--hintergrund":
            i += 1
        elif a == "--warten":
            i += 2
        elif a.startswith("--warten="):
            i += 1
        else:
            aus.append(a)
            i += 1
    return aus


# ---------- review / cancel / result ----------

def cmd_review(args) -> int:
    from .review import fuehre_review_aus
    if args.konto and args.anbieter:
        raise KonfigFehler("--konto und --anbieter schließen sich aus.")
    if args.konto:
        from .konten import konto_id
        args.anbieter = konto_id(args.konto)
    if not args.anbieter:
        args.anbieter = standard_anbieter()
        if not args.anbieter:
            raise KonfigFehler("Kein Anbieter angegeben und kein Standard gesetzt (--konto/--anbieter oder: omni-agent konto standard NAME)")
        print(f"Kein Anbieter angegeben, Standard: {args.anbieter}")
    if (args.hintergrund or args.warten is not None) and not args.vorschau:
        return starte_losgeloest(_ohne_flags(args._argv), args.warten)
    return fuehre_review_aus(args)


def cmd_cancel(args) -> int:
    if args.lauf:
        ordner = finde_lauf(args.lauf)
    else:
        laufende = [p for p in laeufe_im_blick() if (lies_status(p) or {}).get("zustand") == "arbeitet"]
        if not laufende:
            print("Kein Lauf arbeitet gerade.")
            return 0
        ordner = laufende[0]
    war_arbeitend = (lies_status(ordner) or {}).get("zustand") == "arbeitet"
    status = pruefe_lebt(ordner)
    if status.get("zustand") != "arbeitet":
        if war_arbeitend:
            print(f"{ordner.name}: Prozess war schon weg, Status auf 'fehler' gesetzt.")
        else:
            print(f"{ordner.name}: läuft nicht ({status.get('zustand', 'unbekannt')}).")
        return 0
    os.kill(int(status["pid"]), signal.SIGTERM)
    for _ in range(40):
        time.sleep(0.5)
        if (lies_status(ordner) or {}).get("zustand") != "arbeitet":
            print(f"{ordner.name}: abgebrochen.")
            return 0
    print(f"{ordner.name}: Abbruch angefordert, der Lauf beendet sich noch.")
    return 0


def cmd_result(args) -> int:
    if args.lauf:
        ordner = finde_lauf(args.lauf)
    else:
        mit_bericht = [p for p in laeufe_im_blick() if (p / "bericht.md").is_file()]
        if not mit_bericht:
            raise KonfigFehler("Noch kein Lauf mit Bericht. Läufe: omni-agent status")
        ordner = mit_bericht[0]
    bericht = ordner / "bericht.md"
    status = pruefe_lebt(ordner)
    if not bericht.is_file():
        raise KonfigFehler(f"{ordner.name}: kein Bericht ({status.get('zustand', 'unbekannt')}). Siehe: omni-agent status {ordner.name}")
    if args.pfad:
        print(bericht)
        return 0
    if status.get("zustand") == "arbeitet":
        print("[Lauf arbeitet noch, dies ist ein Zwischenstand]\n")
    drucke_bericht(ordner, status)
    return 0


def cmd_warte(args) -> int:
    """Wartet auf einen Lauf (höchstens --max Sekunden) und meldet den Stand; für Weiterleiter, die Läufe losgelöst starten."""
    return warte_und_melde(finde_lauf(args.lauf), args.max)


def cmd_fortsetzbar(args) -> int:
    """Gibt es einen Lauf dieser Claude-Sitzung, an den eine Nachfrage gehen könnte? (Für die Rückfrage „fortsetzen oder neu“.)"""
    sitzung = claude_sitzung()
    kandidaten = alle_laeufe(sitzung) if sitzung else []
    for ordner in kandidaten:
        status = pruefe_lebt(ordner)
        if status.get("sitzung") and status.get("zustand") in ("fertig", "fehler", "abgebrochen") and status.get("art", "run") == "run":
            antwort = {"available": True, "lauf": ordner.name, "anbieter": status.get("anbieter"), "modell": status.get("modell"),
                       "zustand": status.get("zustand"), "auftrag": status.get("auftrag")}
            break
    else:
        antwort = {"available": False}
    print(json.dumps(antwort, ensure_ascii=False))
    return 0


# ---------- status ----------

def _zeile(ordner: Path) -> dict:
    s = pruefe_lebt(ordner)
    return {"lauf": ordner.name, "zustand": s.get("zustand", "unbekannt"), "art": s.get("art", "run"), "anbieter": s.get("anbieter"),
            "modell": s.get("modell"), "runden": s.get("runden"), "dauer": dauer_text(s), "auftrag": s.get("auftrag") or "",
            "fortsetzbar": bool(s.get("sitzung")), "projekt": s.get("projekt")}


def cmd_status(args) -> int:
    if args.lauf:
        ordner = finde_lauf(args.lauf)
        status = pruefe_lebt(ordner) or {"zustand": "unbekannt"}
        if args.json:
            print(json.dumps({**status, "ordner": str(ordner), "bericht": str(ordner / "bericht.md") if (ordner / "bericht.md").exists() else None}, ensure_ascii=False))
        else:
            print(f"Lauf:    {ordner}")
            for k in ("zustand", "art", "anbieter", "modell", "runner", "runden", "exitcode", "bemerkung", "projekt", "auftrag"):
                if status.get(k) is not None:
                    print(f"{k.capitalize() + ':':<9}{status[k]}")
            print(f"Dauer:   {dauer_text(status)}")
            print(f"Bericht: {ordner / 'bericht.md' if (ordner / 'bericht.md').exists() else 'noch nicht da'}")
            if status.get("sitzung"):
                print("Fortsetzbar: ja (omni-agent run --fortsetzen LAUF --text \"Nachfrage\")")
            if status.get("zustand") == "arbeitet":
                print("Abbrechen: omni-agent cancel " + ordner.name)
        return 0
    sitzung = claude_sitzung()
    quelle = alle_laeufe() if args.alle or not sitzung else (alle_laeufe(sitzung) or alle_laeufe())
    zeilen = [_zeile(p) for p in quelle[: args.anzahl]]
    if args.json:
        print(json.dumps(zeilen, ensure_ascii=False))
        return 0
    if not zeilen:
        print("Noch keine Läufe.")
        return 0
    if args.md:
        print("| Lauf | Zustand | Anbieter / Modell | Dauer | Auftrag |\n|---|---|---|---|---|")
        for z in zeilen:
            auftrag = z["auftrag"][:70].replace("|", "/")
            print(f"| `{z['lauf']}` | {z['zustand']}{' (Review)' if z['art'] == 'review' else ' (Gate)' if z['art'] == 'gate' else ''} | "
                  f"{z['anbieter'] or '-'} / {z['modell'] or '-'} | {z['dauer'] or '-'} | {auftrag} |")
        print("\nBericht: `omni-agent result LAUF` · Abbrechen: `omni-agent cancel LAUF` · Nachfrage: `omni-agent run --fortsetzen LAUF --text \"…\"`")
        return 0
    for z in zeilen:
        print(f"{z['lauf']:<34}{z['zustand']:<12}{(z['anbieter'] or '-') + ' / ' + (z['modell'] or '-'):<44}{z['dauer']}")
    return 0


def cmd_hook(args) -> int:
    from .haken import fuehre_haken_aus
    return fuehre_haken_aus(args.name)


# ---------- konto ----------

def cmd_konto(args) -> int:
    from . import konten
    if args.aktion == "standard":
        if args.loeschen:
            setze_standard_anbieter(None)
            print("Standard entfernt: ohne --anbieter läuft nichts mehr.")
        elif args.name:
            kid = konten.konto_id(args.name)
            if kid not in lade_anbieter():
                raise KonfigFehler(f"Konto '{args.name}' gibt es nicht. Vorhandene: omni-agent konto list")
            setze_standard_anbieter(kid)
            print(f"Standard ist jetzt {kid}: `omni-agent run …` ohne --anbieter nutzt dieses Konto.")
        else:
            print(f"Standard: {standard_anbieter() or 'keiner gesetzt'}")
        return 0
    if args.aktion == "list":
        alle = konten.liste()
        if not alle:
            print("Noch kein benanntes Konto. Anlegen: omni-agent konto add NAME --art api|token")
            return 0
        for k in alle:
            std = "  [STANDARD]" if k["id"] == standard_anbieter() else ""
            print(f"{k['name']:<12} --anbieter {k['id']:<18} {konten.ARTEN[k['art']][1]}{std}")
            print(f"{'':<12} Schlüssel {k['schluessel']} ({k['env']})")
            if not args.ohne_nutzung:
                print(f"{'':<12} Nutzung: {konten.nutzung(k)}")
        if not args.ohne_nutzung:
            print("\nNutzung = eine Ein-Token-Anfrage je Konto an api.anthropic.com (Haiku); --ohne-nutzung überspringt sie.")
        return 0
    if not args.name:
        raise KonfigFehler("Bitte einen Kontonamen angeben, z. B.: omni-agent konto add felipe --art token")
    if args.aktion == "remove":
        konten.entferne(args.name, args.mit_schluessel)
        print(f"Konto '{args.name}' entfernt." + (" Schlüsselzeile gelöscht." if args.mit_schluessel else f" Die Zeile {konten.konto_env(args.name)} in der Schlüsseldatei bleibt (--mit-schluessel löscht sie)."))
        return 0
    # add
    pfad = konten.lege_an(args.name, args.art, args.titel, args.ersetzen)
    env = konten.konto_env(args.name)
    print(f"Konto '{args.name}' angelegt ({pfad.name}). Aufruf: --anbieter {konten.konto_id(args.name)}")
    if args.uebernehme:
        konten.benenne_schluessel_um(args.uebernehme, env)
        print(f"Schlüssel aus {args.uebernehme} übernommen, jetzt unter {env}.")
    elif sys.stdin.isatty():
        import getpass
        wert = getpass.getpass(f"{konten.ARTEN[args.art][1]} für '{args.name}' (Eingabe unsichtbar, Enter überspringt): ").strip()
        if wert:
            konten.setze_schluessel(env, wert)
            print(f"Schlüssel gespeichert unter {env} (Rechte 600).")
    if not any(k["name"] == args.name and k["schluessel"] == "gesetzt" for k in konten.liste()):
        print(f"Schlüssel fehlt noch. In deinem Terminal (nicht im Chat) erneut: omni-agent konto add {args.name} --art {args.art} --ersetzen")
        print(f"oder in {env_datei()} eine Zeile eintragen:  {env}=dein-schlüssel")
    if args.art == "token":
        print("Hinweis: " + konten.HINWEIS_TOKEN)
    return 0


# ---------- fernziele ----------

def cmd_host(args) -> int:
    from . import hosts
    if args.aktion == "list":
        eintraege = hosts.lade()
        if not eintraege:
            print("Noch kein Ziel. Anlegen: omni-agent host add mini --ssh benutzer@adresse   (Tailscale-Name oder -IP geht auch)")
            return 0
        for name, e in eintraege.items():
            print(f"{name:<12} ssh {e['ssh']:<32} Befehl: {e.get('befehl') or hosts.STANDARD_BEFEHL}")
        print("\nBenutzen: omni-agent run --host NAME ...  (auch status, result, cancel, warte, nutzung, doctor)")
        return 0
    if not args.name:
        raise KonfigFehler("Bitte einen Zielnamen angeben, z. B.: omni-agent host add mini --ssh benutzer@adresse")
    if args.aktion == "add":
        if not args.ssh:
            raise KonfigFehler("--ssh BENUTZER@ADRESSE fehlt (Name, IP oder Tailscale-Name)")
        hosts.fuege_hinzu(args.name, args.ssh, args.befehl, args.ersetzen)
        print(f"Ziel '{args.name}' angelegt ({args.ssh}). Prüfen: omni-agent host test {args.name}")
        return 0
    if args.aktion == "remove":
        hosts.entferne(args.name)
        print(f"Ziel '{args.name}' entfernt.")
        return 0
    if args.aktion == "install":
        pfad = hosts.installiere(args.name)
        print(f"Omni-Agent liegt auf '{args.name}' unter {pfad}. Schlüssel und Anmeldungen dort einrichten: omni-agent host setup {args.name}")
        return 0
    if args.aktion == "setup":
        return hosts.leite_weiter(args.name, ["setup"])
    ok, text = hosts.teste(args.name)
    print(text.rstrip() if ok else f"Ziel '{args.name}': {text}")
    return 0 if ok else EXIT_KONFIG


# ---------- nutzung ----------

def cmd_nutzung(args) -> int:
    """Nutzung und Guthaben, soweit der jeweilige Anbieter sie hergibt. Alle Abfragen laufen parallel."""
    from concurrent.futures import ThreadPoolExecutor
    from . import konten, nutzung
    ziel = (args.ziel or "").lower()
    aufgaben = []  # (Name, Art, Funktion)
    for k in konten.liste():
        if ziel in ("", "konten", "claude", k["name"], k["id"]):
            aufgaben.append((k["id"], "Claude-Konto", lambda k=k: konten.nutzung(k)))
    if ziel in ("", "codex") and RUNNER["codex"].pfad():
        aufgaben.append(("codex", "Anmeldung der Codex-CLI", nutzung.codex_nutzung))
    datei = lese_schluesseldatei()
    for a in lade_anbieter().values():
        if a.konto_art or a.id.startswith("claude-") or (ziel and ziel != a.id) or (not ziel and a.id not in nutzung.ABFRAGEN):
            continue
        schluessel = next((w for n in a.key_envs if (w := hole_schluessel(n, datei))), None)
        if not schluessel and not ziel:
            continue  # ohne Schlüssel nur auf Zuruf melden, sonst Rauschen
        aufgaben.append((a.id, a.name, lambda a=a, s=schluessel: nutzung.guthaben(a.id, s)))
    if not aufgaben:
        print("Nichts zu zeigen: kein Claude-Konto, kein Codex, kein Anbieter mit Schlüssel. Einrichten: omni-agent setup")
        return 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        ergebnisse = list(pool.map(lambda t: t[2](), aufgaben))
    for (name, art, _), text in zip(aufgaben, ergebnisse):
        print(f"{name:<16} {art}")
        print(f"{'':<16} {text}")
    print("\nQuellen: Claude-Konten = Rate-Limit-Header (eine Ein-Token-Anfrage je Konto), Codex = `codex app-server`, "
          "Fremdanbieter = deren Guthaben-Abfrage. Ohne Angabe des Anbieters steht dort nichts.")
    return 0


# ---------- anbieter / runner ----------


def cmd_anbieter(args) -> int:
    for a in lade_anbieter().values():
        print(f"{a.id}  ({a.name})")
        print(f"  Protokoll: {', '.join(a.protokolle)}   Adresse: {a.base_url or 'Standard von Claude Code'}")
        print(f"  Schlüssel: {' oder '.join(a.key_envs) or 'keiner'}   Modelle: {', '.join(f'{k}={v}' for k, v in a.modelle.items()) or 'mit --modell wählen'}")
        print(f"  Datenort:  {a.region}   Live geprüft: {'ja' if a.geprueft else 'nein'}")
        print(f"  {a.hinweis}\n")
    return 0


def cmd_runner(args) -> int:
    for r in RUNNER.values():
        v = r.version()
        print(f"{r.name}  {'installiert ' + str(v) if v else 'nicht installiert'}{'  [experimentell]' if r.experimentell else ''}")
        print(f"  spricht: {', '.join(r.protokolle)}   steuert: {', '.join(sorted(r.kann))}")
        print(f"  {r.hinweis}\n")
    return 0


# ---------- extras ----------

def cmd_extras(args) -> int:
    if args.aktion == "install":
        extras.installieren(args.trotzdem)
    elif args.aktion == "start":
        if not args.anbieter:
            raise KonfigFehler("Anbieter angeben: omni-agent extras litellm start <anbieter> [--modell M]")
        from .lauf import finde_schluessel
        a = lade_anbieter().get(args.anbieter)
        if not a:
            raise KonfigFehler(f"Unbekannter Anbieter '{args.anbieter}'")
        schluessel = next(iter(finde_schluessel(a).values()), "")
        adresse, _ = extras.starte_proxy(a, a.modell_waehlen(args.modell), schluessel)
        print(f"Proxy läuft auf {adresse} (nur lokal)")
    elif args.aktion == "stop":
        print("Proxy gestoppt." if extras.stoppe_proxy() else "Proxy lief nicht.")
    else:
        print(extras.status_text())
    return 0


# ---------- Aufbau ----------

def baue_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="omni-agent",
        description="Hintergrund-Agents mit austauschbarem Anbieter (Modell-Quelle) und Runner (Agent-CLI).",
    )
    p.add_argument("--version", action="version", version=f"omni-agent {VERSION}")
    sub = p.add_subparsers(dest="befehl", required=True)

    s = sub.add_parser("setup", help="Ordner, Schlüsseldatei und Befehl einrichten, dann prüfen")
    s.add_argument("--anbieter", help="Anleitung für diesen Anbieter ausgeben")
    s.add_argument("--oeffnen", action="store_true", help="Schlüsseldatei im Editor öffnen")
    s.add_argument("--review-gate", choices=["an", "aus"], help="Prüfung vor dem Beenden einer Claude-Sitzung ein- oder ausschalten (Standard: aus)")
    s.set_defaults(fn=cmd_setup)

    s = sub.add_parser("doctor", help="Was ist da, was fehlt (Runner, Schlüssel, Passung)")
    s.add_argument("--netz", action="store_true", help="auch die Erreichbarkeit der Endpunkte prüfen")
    s.set_defaults(fn=cmd_doctor)

    s = sub.add_parser("run", help="Auftrag ausführen (blockierend; im Hintergrund starten, wenn Claude es tut)")
    s.add_argument("auftrag", nargs="?", help="Auftragsdatei (Markdown)")
    s.add_argument("--text", help="Auftrag direkt als Text statt als Datei")
    s.add_argument("--anbieter", help="siehe: omni-agent anbieter; ohne Angabe gilt der Standard (omni-agent konto standard)")
    s.add_argument("--konto", help="Kurzform für --anbieter claude-<name>, z. B. --konto felipe")
    s.add_argument("--modell", help="Modellname oder Kurzname (standard, stark, klein)")
    s.add_argument("--runner", help="claude, opencode, codex oder dsh; ohne Angabe der erste passende installierte")
    s.add_argument("--werkzeuge", help="z. B. 'lesen,schreiben', '+shell', '-web_suche' (Standard: lesen,schreiben,web_suche,web_laden)")
    s.add_argument("--max-runden", type=int, default=12, help="Obergrenze für Werkzeugaufrufe laut Auftragsrahmen (Standard 12)")
    s.add_argument("--zeit", type=int, default=900, help="Zeitlimit in Sekunden (Standard 900)")
    s.add_argument("--ordner", help="eigener, leerer Arbeitsordner statt ~/.omni-agent/laeufe/...")
    s.add_argument("--material", help="Ordner, dessen Inhalt vor dem Start in den Arbeitsordner kopiert wird")
    s.add_argument("--ueber-litellm", action="store_true", help="OpenAI-Anbieter für Claude Code über das Extra LiteLLM übersetzen")
    s.add_argument("--fortsetzen", nargs="?", const="", default=None, metavar="LAUF", help="Nachfrage an einen früheren Lauf (ohne Namen: der letzte); --text ist die Nachfrage")
    s.add_argument("--aufwand", choices=["minimal", "low", "medium", "high", "xhigh"], help="Denkaufwand (nur Codex)")
    s.add_argument("--projekt", nargs="?", const="", default=None, metavar="ORDNER", help="im Projektordner arbeiten (ohne Wert: aktuelles Verzeichnis), nur lesen (mit jedem Anbieter, die Entscheidung liegt bei dir)")
    s.add_argument("--schreibend", action="store_true", help="mit --projekt: Dateien im Projekt dürfen geändert werden")
    s.add_argument("--hintergrund", action="store_true", help="als losgelöster Prozess starten und sofort den Laufnamen melden")
    s.add_argument("--warten", type=int, metavar="SEK", help="losgelöst starten und höchstens so lange auf das Ende warten (meldet dann Stand oder Bericht)")
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("review", help="Git-Änderungen von einem anderen Modell prüfen lassen (der Diff verlässt den Rechner)")
    s.add_argument("fokus", nargs="*", help="Schwerpunkt als freier Text, z. B. Rechte und Datenverlust")
    s.add_argument("--base", help="Branch gegen diesen Stand prüfen, z. B. main (ohne Angabe: alle Änderungen gegen HEAD)")
    s.add_argument("--adversarial", action="store_true", help="auch die gewählte Lösung infrage stellen")
    s.add_argument("--anbieter", help="siehe: omni-agent anbieter; ohne Angabe der Standard")
    s.add_argument("--konto", help="Kurzform für --anbieter claude-<name>")
    s.add_argument("--modell")
    s.add_argument("--runner")
    s.add_argument("--aufwand", choices=["minimal", "low", "medium", "high", "xhigh"], help="Denkaufwand (nur Codex)")
    s.add_argument("--max-runden", type=int, default=10)
    s.add_argument("--zeit", type=int, default=900)
    s.add_argument("--hintergrund", action="store_true", help="als losgelöster Prozess starten und sofort den Laufnamen melden")
    s.add_argument("--warten", type=int, metavar="SEK", help="losgelöst starten und höchstens so lange auf das Ende warten")
    s.add_argument("--vorschau", action="store_true", help="nur zeigen, was gesendet würde; nichts senden")
    s.add_argument("--trotzdem", action="store_true", help="auch senden, wenn der Diff mögliche Geheimnisse enthält")
    s.set_defaults(fn=cmd_review)

    s = sub.add_parser("cancel", help="Laufenden Lauf abbrechen (ohne Angabe: den laufenden)")
    s.add_argument("lauf", nargs="?")
    s.set_defaults(fn=cmd_cancel)

    s = sub.add_parser("result", help="Bericht eines Laufs anzeigen (ohne Angabe: der neueste mit Bericht)")
    s.add_argument("lauf", nargs="?")
    s.add_argument("--pfad", action="store_true", help="nur den Pfad zur bericht.md ausgeben")
    s.set_defaults(fn=cmd_result)

    s = sub.add_parser("status", help="Läufe anzeigen (dieser Claude-Sitzung, sonst alle)")
    s.add_argument("lauf", nargs="?", help="Teil des Laufnamens; ohne Angabe die letzten Läufe")
    s.add_argument("--anzahl", type=int, default=10)
    s.add_argument("--alle", action="store_true", help="auch Läufe anderer Sitzungen")
    s.add_argument("--md", action="store_true", help="als Markdown-Tabelle")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("warte", help="Auf einen Lauf warten (höchstens --max Sekunden) und Stand oder Bericht melden")
    s.add_argument("lauf", nargs="?", help="Teil des Laufnamens; ohne Angabe der neueste")
    s.add_argument("--max", type=int, default=540, help="Sekunden (Standard 540, unter dem 10-Minuten-Limit des Bash-Werkzeugs)")
    s.set_defaults(fn=cmd_warte)

    sub.add_parser("fortsetzbar", help="JSON: gibt es einen Lauf dieser Sitzung, der fortgesetzt werden kann?").set_defaults(fn=cmd_fortsetzbar)

    s = sub.add_parser("hook", help="Einstieg für die Hooks des Plugins (liest JSON von stdin)")
    s.add_argument("name", choices=["start", "ende", "stopp"])
    s.set_defaults(fn=cmd_hook)

    sub.add_parser("anbieter", help="Anbieter mit Datenort auflisten").set_defaults(fn=cmd_anbieter)
    s = sub.add_parser("host", help="Fernziele (Mac mini, Server) für --host: add, list, remove, test, install, setup")
    s.add_argument("aktion", nargs="?", default="list", choices=["add", "list", "remove", "test", "install", "setup"])
    s.add_argument("name", nargs="?", help="Zielname, z. B. mini")
    s.add_argument("--ssh", metavar="BENUTZER@ADRESSE", help="Ziel für ssh: Name, IP oder Tailscale-Name")
    s.add_argument("--befehl", help="Pfad zu omni-agent auf dem Ziel (Standard: omni-agent im PATH; host install setzt ihn selbst)")
    s.add_argument("--ersetzen", action="store_true", help="vorhandenes Ziel gleichen Namens überschreiben")
    s.set_defaults(fn=cmd_host)
    s = sub.add_parser("nutzung", help="Nutzung und Guthaben: Claude-Konten, Codex, DeepSeek, Kimi, OpenRouter, EUrouter")
    s.add_argument("ziel", nargs="?", help="nur dieses Konto oder diesen Anbieter zeigen (konten, codex, deepseek, ...)")
    s.set_defaults(fn=cmd_nutzung)
    s = sub.add_parser("konto", help="Benannte Claude-Konten (beliebig viele): add, list, remove, standard")
    s.add_argument("aktion", choices=["add", "list", "remove", "standard"])
    s.add_argument("name", nargs="?", help="Kontoname, z. B. felipe oder fps")
    s.add_argument("--art", choices=["api", "token"], default="api", help="api = ANTHROPIC_API_KEY (empfohlen), token = Abo-Token")
    s.add_argument("--titel", help="Anzeigename, z. B. 'Felipes Konto'")
    s.add_argument("--uebernehme", metavar="ENV_NAME", help="vorhandene Zeile der Schlüsseldatei unter dem Kontonamen weiterverwenden (z. B. CLAUDE_CODE_OAUTH_TOKEN)")
    s.add_argument("--loeschen", action="store_true", help="bei standard den Standard entfernen")
    s.add_argument("--ersetzen", action="store_true", help="vorhandenes Konto gleichen Namens überschreiben")
    s.add_argument("--mit-schluessel", action="store_true", help="bei remove auch die Schlüsselzeile löschen")
    s.add_argument("--ohne-nutzung", action="store_true", help="bei list keine Limit-Abfrage machen (kein Netz)")
    s.set_defaults(fn=cmd_konto)
    sub.add_parser("runner", help="Runner auflisten").set_defaults(fn=cmd_runner)

    s = sub.add_parser("extras", help="Optionale Extras")
    s.add_argument("name", choices=["litellm"])
    s.add_argument("aktion", choices=["install", "start", "stop", "status"])
    s.add_argument("anbieter", nargs="?")
    s.add_argument("--modell")
    s.add_argument("--trotzdem", action="store_true", help="Install trotz anderer Python-Version")
    s.set_defaults(fn=cmd_extras)
    for name in ("run", "review", "status", "result", "cancel", "warte", "doctor", "nutzung"):
        sub.choices[name].add_argument("--host", metavar="ZIEL", help="auf einem Fernziel ausführen (omni-agent host add), per ssh; Schlüssel und Projekte liegen dort")
    return p


def main(argv=None) -> int:
    args = baue_parser().parse_args(argv)
    args._argv = list(argv) if argv is not None else sys.argv[1:]
    if getattr(args, "host", None):
        from . import hosts
        try:
            return hosts.leite_weiter(args.host, args._argv, args)
        except KonfigFehler as fehler:
            print(f"Fehler: {fehler}", file=sys.stderr)
            return fehler.exit_code
    if args.befehl == "run" and not args.auftrag and args.text is None:
        print("Auftragsdatei oder --text angeben", file=sys.stderr)
        return EXIT_KONFIG
    try:
        return args.fn(args)
    except KonfigFehler as fehler:
        print(f"Fehler: {fehler}", file=sys.stderr)
        return fehler.exit_code
    except KeyboardInterrupt:
        return 130
