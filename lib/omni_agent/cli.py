"""Kommandozeile: omni-agent setup | doctor | run | status | anbieter | runner | extras."""
import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

from . import VERSION, extras
from .anbieter import lade_anbieter
from .konfig import (
    EXIT_KONFIG, KonfigFehler, WURZEL, env_datei, hole_schluessel, home, laeufe_ordner,
    lese_schluesseldatei, pruefe_erreichbar,
)
from .lauf import fuehre_aus
from .runner import RUNNER, passt

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
        if not a.braucht_schluessel:
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
    quelle = WURZEL / "bin" / "omni-agent"
    link = bin_ziel / "omni-agent"
    if not shutil.which("omni-agent"):
        try:
            bin_ziel.mkdir(parents=True, exist_ok=True)
            if link.is_symlink() and link.resolve() != quelle.resolve():
                link.unlink()  # zeigt ins Leere oder auf eine alte Fassung (Plugin-Cache wechselt mit jeder Version)
            if not link.exists() and not link.is_symlink():
                link.symlink_to(quelle)
                print(f"Befehl verlinkt: {link}")
            if str(bin_ziel) not in os.environ.get("PATH", "").split(os.pathsep):
                print(f"Hinweis: {bin_ziel} ist nicht im PATH. In die Shell-Konfiguration: export PATH=\"$HOME/.local/bin:$PATH\"")
        except OSError as fehler:
            print(f"Befehl konnte nicht verlinkt werden ({fehler}). Direkt aufrufen: {quelle}")
    else:
        print(f"Befehl 'omni-agent' ist im PATH: {shutil.which('omni-agent')}")

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
    if args.oeffnen:
        os.system(f"open -t {datei}" if sys.platform == "darwin" else f"${{EDITOR:-nano}} {datei}")
    print()
    return cmd_doctor(argparse.Namespace(netz=False))


# ---------- run ----------

def cmd_run(args) -> int:
    return fuehre_aus(args)


# ---------- status ----------

def _lies_status(ordner: Path) -> dict | None:
    try:
        return json.loads((ordner / "status.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _alle_laeufe() -> list:
    basis = laeufe_ordner()
    if not basis.is_dir():
        return []
    return sorted((p for p in basis.iterdir() if p.is_dir()), key=lambda p: p.name, reverse=True)


def cmd_status(args) -> int:
    laeufe = _alle_laeufe()
    if args.lauf:
        treffer = [p for p in laeufe if args.lauf in p.name]
        if not treffer:
            raise KonfigFehler(f"Kein Lauf passt zu '{args.lauf}'")
        ordner = treffer[0]
        status = _lies_status(ordner) or {"zustand": "unbekannt"}
        if args.json:
            print(json.dumps({**status, "ordner": str(ordner), "bericht": str(ordner / "bericht.md") if (ordner / "bericht.md").exists() else None}, ensure_ascii=False))
        else:
            print(f"Lauf:    {ordner}")
            for k in ("zustand", "anbieter", "modell", "runner", "runden", "exitcode", "bemerkung"):
                if status.get(k) is not None:
                    print(f"{k.capitalize() + ':':<9}{status[k]}")
            if status.get("start"):
                ende = status.get("ende") or int(time.time())
                print(f"Dauer:   {ende - status['start']}s")
            print(f"Bericht: {ordner / 'bericht.md' if (ordner / 'bericht.md').exists() else 'noch nicht da'}")
        return 0
    zeilen = []
    for p in laeufe[: args.anzahl]:
        s = _lies_status(p) or {}
        dauer = ""
        if s.get("start"):
            dauer = f"{(s.get('ende') or int(time.time())) - s['start']}s"
        zeilen.append({"lauf": p.name, "zustand": s.get("zustand", "unbekannt"), "anbieter": s.get("anbieter"),
                       "modell": s.get("modell"), "runden": s.get("runden"), "dauer": dauer})
    if args.json:
        print(json.dumps(zeilen, ensure_ascii=False))
        return 0
    if not zeilen:
        print("Noch keine Läufe.")
    for z in zeilen:
        print(f"{z['lauf']:<34}{z['zustand']:<12}{(z['anbieter'] or '-') + ' / ' + (z['modell'] or '-'):<44}{z['dauer']}")
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
    s.set_defaults(fn=cmd_setup)

    s = sub.add_parser("doctor", help="Was ist da, was fehlt (Runner, Schlüssel, Passung)")
    s.add_argument("--netz", action="store_true", help="auch die Erreichbarkeit der Endpunkte prüfen")
    s.set_defaults(fn=cmd_doctor)

    s = sub.add_parser("run", help="Auftrag ausführen (blockierend; im Hintergrund starten, wenn Claude es tut)")
    s.add_argument("auftrag", nargs="?", help="Auftragsdatei (Markdown)")
    s.add_argument("--text", help="Auftrag direkt als Text statt als Datei")
    s.add_argument("--anbieter", required=True, help="siehe: omni-agent anbieter")
    s.add_argument("--modell", help="Modellname oder Kurzname (standard, stark, klein)")
    s.add_argument("--runner", help="claude, opencode, codex oder dsh; ohne Angabe der erste passende installierte")
    s.add_argument("--werkzeuge", help="z. B. 'lesen,schreiben', '+shell', '-web_suche' (Standard: lesen,schreiben,web_suche,web_laden)")
    s.add_argument("--max-runden", type=int, default=12, help="Obergrenze für Werkzeugaufrufe laut Auftragsrahmen (Standard 12)")
    s.add_argument("--zeit", type=int, default=900, help="Zeitlimit in Sekunden (Standard 900)")
    s.add_argument("--ordner", help="eigener, leerer Arbeitsordner statt ~/.omni-agent/laeufe/...")
    s.add_argument("--material", help="Ordner, dessen Inhalt vor dem Start in den Arbeitsordner kopiert wird")
    s.add_argument("--ueber-litellm", action="store_true", help="OpenAI-Anbieter für Claude Code über das Extra LiteLLM übersetzen")
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("status", help="Läufe anzeigen")
    s.add_argument("lauf", nargs="?", help="Teil des Laufnamens; ohne Angabe die letzten Läufe")
    s.add_argument("--anzahl", type=int, default=10)
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_status)

    sub.add_parser("anbieter", help="Anbieter mit Datenort auflisten").set_defaults(fn=cmd_anbieter)
    sub.add_parser("runner", help="Runner auflisten").set_defaults(fn=cmd_runner)

    s = sub.add_parser("extras", help="Optionale Extras")
    s.add_argument("name", choices=["litellm"])
    s.add_argument("aktion", choices=["install", "start", "stop", "status"])
    s.add_argument("anbieter", nargs="?")
    s.add_argument("--modell")
    s.add_argument("--trotzdem", action="store_true", help="Install trotz anderer Python-Version")
    s.set_defaults(fn=cmd_extras)
    return p


def main(argv=None) -> int:
    args = baue_parser().parse_args(argv)
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
