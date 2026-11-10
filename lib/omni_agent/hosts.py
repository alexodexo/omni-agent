"""Fernziele: Omni-Agent auf einem anderen Rechner ausführen (Mac mini, Server, Cloud-VM) über SSH.

`--host NAME` leitet den Befehl unverändert an `omni-agent` auf dem Ziel weiter. Dort liegen Schlüssel, Agent-CLIs,
Projekte und Läufe; nichts davon wird übertragen. Tailscale ist nichts Besonderes: jeder Name oder jede Adresse,
die `ssh` erreicht (auch Tailscale-IP, MagicDNS-Name, Tailscale SSH), geht.

Gespeichert wird nur, wie das Ziel zu erreichen ist (`hosts.json`), nie ein Geheimnis.
"""
from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
import sys

from .konfig import KonfigFehler, claude_sitzung, home

NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")
STANDARD_BEFEHL = "omni-agent"
INSTALL_ORDNER = ".omni-agent-app"
REPO = "https://github.com/alexodexo/omni-agent"


def datei():
    return home() / "hosts.json"


def lade() -> dict:
    try:
        d = json.loads(datei().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def speichere(daten: dict) -> None:
    home().mkdir(parents=True, exist_ok=True)
    datei().write_text(json.dumps(daten, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def pruefe_name(name: str) -> str:
    if not NAME.match(name or ""):
        raise KonfigFehler("Zielname: Kleinbuchstaben, Ziffern und Bindestrich, z. B. mini")
    return name


def hole(name: str) -> dict:
    eintraege = lade()
    if name not in eintraege:
        vorhanden = ", ".join(eintraege) or "keine"
        raise KonfigFehler(f"Ziel '{name}' gibt es nicht. Vorhandene: {vorhanden}. Anlegen: omni-agent host add {name} --ssh BENUTZER@ADRESSE")
    return eintraege[name]


def fuege_hinzu(name: str, ssh: str, befehl: str | None = None, ersetzen: bool = False) -> None:
    pruefe_name(name)
    if not ssh or ssh.startswith("-") or any(c.isspace() for c in ssh):
        raise KonfigFehler("--ssh erwartet ein Ziel wie benutzer@adresse (Name, IP oder Tailscale-Name), ohne Leerzeichen und ohne führenden Bindestrich")
    eintraege = lade()
    if name in eintraege and not ersetzen:
        raise KonfigFehler(f"Ziel '{name}' gibt es schon. Überschreiben: --ersetzen")
    eintraege[name] = {"ssh": ssh, "befehl": befehl or STANDARD_BEFEHL}
    speichere(eintraege)


def entferne(name: str) -> None:
    eintraege = lade()
    if name not in eintraege:
        raise KonfigFehler(f"Ziel '{name}' gibt es nicht")
    del eintraege[name]
    speichere(eintraege)


def ssh_argv(eintrag: dict, entfernt: str, tty: bool = False) -> list:
    exe = shutil.which("ssh")
    if not exe:
        raise KonfigFehler("ssh ist nicht installiert (Befehl 'ssh' nicht im PATH)")
    return [
        exe, "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=30",
        *(["-t"] if tty else []), "--", eintrag["ssh"], entfernt,
    ]


def entfernter_befehl(eintrag: dict, argv: list) -> str:
    """Die Zeile, die auf dem Ziel läuft. Die Claude-Sitzung geht mit, damit status/result dort dieselbe Sitzung meinen."""
    vorne = ""
    if claude_sitzung():
        vorne = f"OMNI_AGENT_SITZUNG={shlex.quote(claude_sitzung())} "
    befehl = eintrag.get("befehl") or STANDARD_BEFEHL
    # Der Befehl darf mit ~ oder $HOME beginnen (Pfad zum Skript); die Argumente werden immer zitiert.
    return vorne + befehl + " " + " ".join(shlex.quote(a) for a in argv)


def ohne_host(argv: list) -> list:
    """Entfernt --host NAME / --host=NAME aus der Argumentliste."""
    aus, i = [], 0
    while i < len(argv):
        if argv[i] == "--host":
            i += 2
            continue
        if argv[i].startswith("--host="):
            i += 1
            continue
        aus.append(argv[i])
        i += 1
    return aus


def leite_weiter(name: str, argv: list, args=None) -> int:
    """Führt `omni-agent <argv>` auf dem Ziel aus; Ausgabe und Exit-Code kommen unverändert zurück."""
    eintrag = hole(name)
    argv = ohne_host(argv)
    if args is not None:
        befehl = getattr(args, "befehl", "")
        if getattr(args, "material", None):
            raise KonfigFehler("--material ist ein lokaler Ordner und wird nicht übertragen. Lege das Material auf dem Ziel ab und arbeite dort mit --projekt ORDNER.")
        if befehl == "review":
            raise KonfigFehler("review prüft das Repo im aktuellen Ordner und läuft deshalb nicht mit --host. Auf dem Ziel: omni-agent review im dortigen Checkout (per ssh).")
        # Auftragsdatei liegt lokal: ihren Inhalt als --text mitschicken
        if befehl == "run" and getattr(args, "auftrag", None):
            from pathlib import Path
            quelle = Path(args.auftrag).expanduser()
            if quelle.is_file() and args.auftrag in argv:
                argv.remove(args.auftrag)
                argv += ["--text", quelle.read_text(encoding="utf-8")]
    laeuft = subprocess.run(ssh_argv(eintrag, entfernter_befehl(eintrag, argv)))
    if laeuft.returncode == 255:
        print(f"Fehler: ssh zu '{name}' ({eintrag['ssh']}) ist gescheitert. Erreichbar? Schlüssel hinterlegt (BatchMode, keine Passwortabfrage)? Prüfen: omni-agent host test {name}", file=sys.stderr)
    return laeuft.returncode


def teste(name: str) -> tuple:
    """(ok, Text). Fragt `omni-agent doctor` auf dem Ziel und sagt, was fehlt."""
    eintrag = hole(name)
    try:
        erg = subprocess.run(
            ssh_argv(eintrag, f"{eintrag.get('befehl') or STANDARD_BEFEHL} doctor"),
            capture_output=True, text=True, timeout=60,
        )
    except subprocess.TimeoutExpired:
        return False, "Zeitüberschreitung beim Verbinden"
    if erg.returncode == 255:
        return False, "ssh gescheitert: " + (erg.stderr.strip().splitlines() or ["keine Meldung"])[-1]
    if erg.returncode == 127 or "not found" in erg.stderr or "nicht gefunden" in erg.stderr:
        return False, f"Verbindung steht, aber '{eintrag.get('befehl') or STANDARD_BEFEHL}' gibt es dort nicht. Installieren: omni-agent host install {name}"
    if erg.returncode != 0:
        return False, (erg.stderr.strip() or erg.stdout.strip() or f"Exit-Code {erg.returncode}")[:400]
    return True, erg.stdout


def installiere(name: str) -> str:
    """Holt Omni-Agent per git auf das Ziel (~/.omni-agent-app) und trägt den Pfad als Befehl ein.

    Schlüssel und Anmeldungen richtet man dort selbst ein (omni-agent setup per ssh). Nichts wird übertragen."""
    eintrag = hole(name)
    skript = (
        "set -e; command -v git >/dev/null || { echo 'git fehlt auf dem Ziel' >&2; exit 3; }; "
        "command -v python3 >/dev/null || { echo 'python3 fehlt auf dem Ziel' >&2; exit 3; }; "
        f"python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 4)' || {{ echo 'Python 3.9 oder neuer nötig' >&2; exit 4; }}; "
        f"if [ -d \"$HOME/{INSTALL_ORDNER}/.git\" ]; then git -C \"$HOME/{INSTALL_ORDNER}\" pull --ff-only -q; "
        f"else git clone --depth 1 -q {shlex.quote(REPO)} \"$HOME/{INSTALL_ORDNER}\"; fi; "
        f"echo \"$HOME/{INSTALL_ORDNER}/bin/omni-agent\""
    )
    erg = subprocess.run(ssh_argv(eintrag, skript), capture_output=True, text=True, timeout=180)
    if erg.returncode != 0:
        raise KonfigFehler("Installation auf dem Ziel gescheitert: " + (erg.stderr.strip().splitlines() or [f"Exit-Code {erg.returncode}"])[-1])
    pfad = (erg.stdout.strip().splitlines() or [""])[-1]
    if not pfad.endswith("/bin/omni-agent"):
        raise KonfigFehler("Installation auf dem Ziel lieferte keinen Pfad")
    eintraege = lade()
    eintraege[name]["befehl"] = shlex.quote(pfad)
    speichere(eintraege)
    return pfad
